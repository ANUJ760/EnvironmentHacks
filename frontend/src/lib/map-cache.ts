/** Public visualization cache only. Never exposes arbitrary URLs or scientific objects. */
import { createHash, randomUUID } from 'node:crypto';
import { mkdir, readFile, readdir, rename, stat, unlink, writeFile } from 'node:fs/promises';
import path from 'node:path';

export function mapProvider(parts: string[]) {
  if (parts.length === 1 && parts[0] === 'manifest') return { url: 'https://tiles.openfreemap.org/planet', type: 'application/json', ttl: 86400 };
  if (parts[0] === 'vector' && parts.length === 5 && /^\d{8}_\d{6}_pt$/.test(parts[1]!)) {
    validateTile(parts.slice(2), '.pbf');
    return { url: `https://tiles.openfreemap.org/planet/${parts.slice(1).join('/')}`, type: 'application/x-protobuf', ttl: 31536000 };
  }
  if (parts[0] === 'aerial' && parts.length === 4) {
    validateTile(parts.slice(1), '.jpeg');
    return { url: `https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/3857/${parts.slice(1).join('/')}`, type: 'image/jpeg', ttl: 604800 };
  }
  if (parts[0] === 'fonts' && parts.length === 3 && /^[A-Za-z0-9 ,_-]{1,120}$/.test(parts[1]!) && /^\d{1,5}-\d{1,5}\.pbf$/.test(parts[2]!)) {
    return { url: `https://tiles.openfreemap.org/fonts/${encodeURIComponent(parts[1]!)}/${parts[2]}`, type: 'application/x-protobuf', ttl: 2592000 };
  }
  throw new Error('Unsupported map asset path');
}

function validateTile(parts: string[], extension: string) {
  const [z, x, filename] = parts;
  if (!/^\d{1,2}$/.test(z!) || !/^\d{1,7}$/.test(x!) || !filename?.endsWith(extension)) throw new Error('Invalid tile');
  const y = filename.slice(0, -extension.length);
  if (!/^\d{1,7}$/.test(y) || Number(z) > 19 || Number(x) >= 2 ** Number(z) || Number(y) >= 2 ** Number(z)) throw new Error('Invalid tile coordinates');
}

export function rewriteTileJson(bytes: Buffer) {
  const document = JSON.parse(bytes.toString());
  if (!Array.isArray(document.tiles) || !document.tiles.length) throw new Error('Missing vector tile URLs');
  document.tiles = document.tiles.map((value: string) => {
    if (!/^https:\/\/tiles\.openfreemap\.org\/planet\/\d{8}_\d{6}_pt\/\{z\}\/\{x\}\/\{y\}\.pbf$/.test(value)) throw new Error('Unapproved vector tile template');
    return value.replace('https://tiles.openfreemap.org/planet/', '/api/map/tiles/vector/');
  });
  return Buffer.from(JSON.stringify(document));
}

const pending = new Map<string, Promise<{ bytes: Buffer; stale: boolean }>>();
let lastTrim = 0;
const digest = (bytes: Buffer | string) => createHash('sha256').update(bytes).digest('hex');
const LIMIT = 4 * 1024 * 1024;

export async function cachedMapAsset(provider: ReturnType<typeof mapProvider>, fetcher: typeof fetch = fetch, directory = process.env.MAP_CACHE_DIR || path.resolve(process.cwd(), '../data/cache/maps')) {
  const key = `${directory}:${provider.url}`;
  const existing = pending.get(key);
  if (existing) return existing;
  const promise = readOrDownload(provider, fetcher, directory);
  pending.set(key, promise);
  try { return await promise; } finally { pending.delete(key); }
}

async function readOrDownload(provider: ReturnType<typeof mapProvider>, fetcher: typeof fetch, directory: string) {
  const filename = path.join(directory, digest(provider.url));
  let cached: { bytes: Buffer; captured: number } | undefined;
  try {
    const metadata = JSON.parse(await readFile(`${filename}.json`, 'utf8'));
    const bytes = await readFile(filename);
    if (bytes.length <= LIMIT && digest(bytes) === metadata.sha256 && Number.isFinite(metadata.captured)) cached = { bytes, captured: metadata.captured };
  } catch { /* Missing/evicted/corrupt disposable cache: request the public provider. */ }
  if (cached && Date.now() - cached.captured < provider.ttl * 1000) return { bytes: cached.bytes, stale: false };
  try {
    const response = await fetcher(provider.url, { cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(25000) });
    if (!response.ok || !response.body || Number(response.headers.get('content-length')) > LIMIT) throw new Error('Map provider unavailable or response oversized');
    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.length;
        if (size > LIMIT) throw new Error('Map tile exceeds cache limit');
        chunks.push(value);
      }
    } finally { await reader.cancel(); }
    const bytes = Buffer.concat(chunks);
    if (provider.type === 'application/json') rewriteTileJson(bytes); // Validate before caching.
    if (provider.type === 'image/jpeg' && !(bytes[0] === 0xff && bytes[1] === 0xd8)) throw new Error('Invalid imagery bytes');
    if (provider.type === 'application/x-protobuf' && (!bytes.length || /^\s*</.test(bytes.toString('utf8', 0, 20)))) throw new Error('Invalid vector/font bytes');
    try {
      await mkdir(directory, { recursive: true });
      const temporary = `${filename}.${randomUUID()}.part`;
      try { await writeFile(temporary, bytes); await rename(temporary, filename); } finally { await unlink(temporary).catch(() => {}); }
      await writeFile(`${filename}.json`, JSON.stringify({ source_url: provider.url, sha256: digest(bytes), captured: Date.now(), bytes: bytes.length }));
      await trimCache(directory);
    } catch { /* A read-only cache does not disable the map; ephemeral streaming is allowed. */ }
    return { bytes, stale: false };
  } catch (error) { if (cached) return { bytes: cached.bytes, stale: true }; throw error; }
}

async function trimCache(directory: string) {
  if (Date.now() - lastTrim < 60000) return;
  lastTrim = Date.now();
  const files = (await readdir(directory)).filter(name => /^[a-f0-9]{64}$/.test(name));
  const entries = await Promise.all(files.map(async name => { const info = await stat(path.join(directory, name)); return { name, size: info.size, modified: info.mtimeMs }; }));
  let used = entries.reduce((sum, entry) => sum + entry.size, 0);
  // Cache eviction never touches dataset revisions, raw inputs or model files.
  for (const entry of entries.sort((a, b) => a.modified - b.modified)) {
    if (used <= 1024 * 1024 * 1024) break;
    await unlink(path.join(directory, entry.name)).catch(() => {});
    await unlink(path.join(directory, `${entry.name}.json`)).catch(() => {});
    used -= entry.size;
  }
}
