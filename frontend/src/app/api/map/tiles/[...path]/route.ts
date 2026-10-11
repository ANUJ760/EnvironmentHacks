import { NextRequest, NextResponse } from 'next/server';
import { cachedMapAsset, mapProvider, rewriteTileJson } from '@/lib/map-cache';
export const runtime = 'nodejs';
export async function GET(_request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  let provider;
  try { provider = mapProvider((await params).path); } catch { return NextResponse.json({ detail: 'Unsupported map asset' }, { status: 400 }); }
  try {
    const { bytes, stale } = await cachedMapAsset(provider);
    const body = provider.type === 'application/json' ? rewriteTileJson(bytes) : bytes;
    return new Response(new Uint8Array(body), { headers: { 'Content-Type': provider.type, 'Cache-Control': `public, max-age=${stale ? 60 : Math.min(provider.ttl, 86400)}`, 'X-Map-Cache-Stale': String(stale), 'X-Content-Type-Options': 'nosniff' } });
  } catch { return NextResponse.json({ detail: 'Map provider unavailable; uncached geography needs internet access' }, { status: 502 }); }
}
