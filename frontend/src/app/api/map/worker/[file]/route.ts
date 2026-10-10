import { readFile } from 'node:fs/promises';
import path from 'node:path';

export const runtime = 'nodejs';

// MapLibre 6 uses ESM workers. Serve both vendor modules at a stable same-origin
// URL because Next's client chunk URLs do not preserve their relative imports.
export async function GET(_request: Request, { params }: { params: Promise<{ file: string }> }) {
  const { file } = await params;
  if (!['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs'].includes(file)) {
    return new Response('Not found', { status: 404 });
  }
  const module = await readFile(path.join(process.cwd(), 'node_modules', 'maplibre-gl', 'dist', file));
  return new Response(module, { headers: { 'Content-Type': 'text/javascript; charset=utf-8', 'Cache-Control': 'public, max-age=3600' } });
}
