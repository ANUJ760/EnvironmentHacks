import { afterEach, describe, expect, it, vi } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { mapProvider, cachedMapAsset, rewriteTileJson } from '@/lib/map-cache';
const directories: string[] = [];
afterEach(async () => { for (const directory of directories.splice(0)) await rm(directory, { recursive: true, force: true }); });

describe('bounded public map cache', () => {
  it('supports only known providers and valid coordinates', () => {
    expect(mapProvider(['vector', '20261004_113936_pt', '15', '17100', '11600.pbf']).url).toContain('tiles.openfreemap.org/planet/');
    expect(mapProvider(['aerial', '15', '17100', '11600.jpeg']).url).toContain('wmts.geo.admin.ch');
    expect(mapProvider(['fonts', 'Noto Sans Regular', '0-255.pbf']).url).toContain('Noto%20Sans%20Regular');
    for (const parts of [['http://localhost'], ['aerial', '20', '0', '0.jpeg'], ['aerial', '2', '5', '0.jpeg'], ['fonts', '../secret', '0-255.pbf']]) expect(() => mapProvider(parts)).toThrow();
  });
  it('rewrites only allowlisted versioned vector templates', () => {
    expect(JSON.parse(rewriteTileJson(Buffer.from(JSON.stringify({ tiles: ['https://tiles.openfreemap.org/planet/20261004_113936_pt/{z}/{x}/{y}.pbf'] }))).toString()).tiles[0]).toBe('/api/map/tiles/vector/20261004_113936_pt/{z}/{x}/{y}.pbf');
    expect(() => rewriteTileJson(Buffer.from(JSON.stringify({ tiles: ['http://169.254.169.254/metadata'] })))).toThrow();
  });
  it('downloads once and deduplicates concurrent requests, then reuses verified disk bytes', async () => {
    const directory = await mkdtemp(path.join(tmpdir(), 'ecotwin-map-cache-test-')); directories.push(directory);
    const fetcher = vi.fn(async () => new Response(new Uint8Array([1, 2, 3]))) as unknown as typeof fetch;
    const provider = mapProvider(['vector', '20261004_113936_pt', '15', '17100', '11600.pbf']);
    const results = await Promise.all([cachedMapAsset(provider, fetcher, directory), cachedMapAsset(provider, fetcher, directory)]);
    expect(results[0].bytes).toEqual(Buffer.from([1, 2, 3]));
    await cachedMapAsset(provider, fetcher, directory);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('does not accept an HTML error page as imagery', async () => {
    const directory = await mkdtemp(path.join(tmpdir(), 'ecotwin-map-cache-test-')); directories.push(directory);
    await expect(cachedMapAsset(mapProvider(['aerial', '15', '17100', '11600.jpeg']), vi.fn(async () => new Response('<html>error</html>')) as unknown as typeof fetch, directory)).rejects.toThrow();
  });
});
