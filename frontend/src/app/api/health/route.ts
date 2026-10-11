import { NextResponse } from 'next/server';
import { getServerEnv } from '@/lib/env';

export async function GET() {
  const env = getServerEnv();
  let backendReady = false;
  let backendStatus = 'unknown';

  try {
    const res = await fetch(`${env.ECOTWIN_API_INTERNAL_URL}/readyz`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000),
    });
    backendReady = res.ok;
    backendStatus = res.ok ? 'connected' : `status_${res.status}`;
  } catch (err) {
    backendReady = false;
    backendStatus = 'unreachable';
  }

  return NextResponse.json({
    status: 'healthy',
    version: '0.2.0',
    timestamp: new Date().toISOString(),
    backend: {
      status: backendStatus,
      ready: backendReady,
    },
  });
}
