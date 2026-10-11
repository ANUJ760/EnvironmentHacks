import { NextRequest, NextResponse } from 'next/server';
import { getServerEnv } from '@/lib/env';

// Allowlist regex patterns for backend endpoints
const ALLOWED_PATTERNS: Array<{ pattern: RegExp; methods: string[]; authRequired: boolean }> = [
  { pattern: /^readyz$/, methods: ['GET'], authRequired: false },
  { pattern: /^livez$/, methods: ['GET'], authRequired: false },
  { pattern: /^v1\/cities$/, methods: ['GET'], authRequired: false },
  { pattern: /^v1\/cities\/[a-zA-Z0-9_-]+$/, methods: ['GET'], authRequired: false },
  { pattern: /^v1\/cities\/[a-zA-Z0-9_-]+\/features$/, methods: ['GET'], authRequired: false },
  { pattern: /^v1\/cities\/[a-zA-Z0-9_-]+\/landcover$/, methods: ['GET'], authRequired: false },
  { pattern: /^v1\/cities\/[a-zA-Z0-9_-]+\/observations\/weather$/, methods: ['GET'], authRequired: false },
  { pattern: /^v1\/cities\/[a-zA-Z0-9_-]+\/observations\/air$/, methods: ['GET'], authRequired: false },
  { pattern: /^v1\/cities\/[a-zA-Z0-9_-]+\/datasets$/, methods: ['GET'], authRequired: false },
  { pattern: /^v1\/cities\/[a-zA-Z0-9_-]+\/removal-preview$/, methods: ['POST'], authRequired: false },
  { pattern: /^v1\/cities\/[a-zA-Z0-9_-]+\/planning-preview$/, methods: ['POST'], authRequired: false },
  { pattern: /^v1\/cities\/[a-zA-Z0-9_-]+\/environment-baseline$/, methods: ['GET'], authRequired: false },
  { pattern: /^v1\/models$/, methods: ['GET'], authRequired: false },
  { pattern: /^v1\/scenarios$/, methods: ['POST'], authRequired: true },
  { pattern: /^v1\/scenarios\/[a-zA-Z0-9_-]+$/, methods: ['GET'], authRequired: true },
  { pattern: /^v1\/scenarios\/[a-zA-Z0-9_-]+\/edits$/, methods: ['PUT'], authRequired: true },
  { pattern: /^v1\/scenarios\/[a-zA-Z0-9_-]+\/simulate$/, methods: ['POST'], authRequired: true },
  { pattern: /^v1\/scenarios\/[a-zA-Z0-9_-]+\/reports$/, methods: ['GET'], authRequired: true },
  { pattern: /^v1\/jobs\/[a-zA-Z0-9_-]+$/, methods: ['GET'], authRequired: true },
  { pattern: /^v1\/jobs\/[a-zA-Z0-9_-]+\/cancel$/, methods: ['POST'], authRequired: true },
  { pattern: /^v1\/results\/[a-zA-Z0-9_-]+$/, methods: ['GET'], authRequired: true },
];

async function handleGatewayRequest(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const env = getServerEnv();
  const { path } = await params;
  const normalizedPath = (path || []).join('/');

  // Reject path traversal and double-encoding
  if (normalizedPath.includes('..') || normalizedPath.includes('%2e') || normalizedPath.includes('%2f')) {
    return NextResponse.json(
      { code: 'INVALID_PATH', detail: 'Invalid path navigation rejected' },
      { status: 400, headers: { 'Content-Type': 'application/problem+json' } }
    );
  }

  const method = req.method.toUpperCase();
  const matchedRoute = ALLOWED_PATTERNS.find(
    (rule) => rule.pattern.test(normalizedPath) && rule.methods.includes(method)
  );

  if (!matchedRoute) {
    return NextResponse.json(
      { code: 'NOT_FOUND', detail: `Endpoint ${method} /${normalizedPath} is not permitted on this gateway` },
      { status: 404, headers: { 'Content-Type': 'application/problem+json' } }
    );
  }

  // The public planner never forwards a privileged service token.
  // Retired account-owned workflows remain protected at the backend.
  if (matchedRoute.authRequired) {
    return NextResponse.json(
      {
        code: 'WORKFLOW_RETIRED',
        detail: 'Use the public city planner. Saved account workflows have been retired from this application.',
      },
      { status: 410, headers: { 'Content-Type': 'application/problem+json' } }
    );
  }

  // Construct target URL
  const searchParams = req.nextUrl.search;
  const targetUrl = `${env.ECOTWIN_API_INTERNAL_URL}/${normalizedPath}${searchParams}`;

  // Forward select headers
  const forwardHeaders = new Headers();
  forwardHeaders.set('Accept', 'application/json');


  const ifMatch = req.headers.get('if-match');
  if (ifMatch) {
    forwardHeaders.set('If-Match', ifMatch);
  }

  const idempotencyKey = req.headers.get('idempotency-key');
  if (idempotencyKey) {
    forwardHeaders.set('Idempotency-Key', idempotencyKey);
  }

  const requestId = req.headers.get('x-request-id');
  if (requestId) {
    forwardHeaders.set('X-Request-ID', requestId);
  }

  // Check body size limit (1 MB)
  let requestBody: BodyInit | undefined = undefined;
  if (['POST', 'PUT', 'PATCH'].includes(method)) {
    forwardHeaders.set('Content-Type', 'application/json');
    const bodyText = await req.text();
    if (bodyText.length > 1024 * 1024) {
      return NextResponse.json(
        { code: 'PAYLOAD_TOO_LARGE', detail: 'Request body exceeds 1 MB limit' },
        { status: 413, headers: { 'Content-Type': 'application/problem+json' } }
      );
    }
    requestBody = bodyText;
  }

  try {
    const backendRes = await fetch(targetUrl, {
      method,
      headers: forwardHeaders,
      body: requestBody,
      signal: AbortSignal.timeout(30000),
    });

    const responseHeaders = new Headers();
    const contentType = backendRes.headers.get('content-type') || 'application/json';
    responseHeaders.set('Content-Type', contentType);

    const etag = backendRes.headers.get('etag');
    if (etag) {
      responseHeaders.set('ETag', etag);
    }

    const resRequestId = backendRes.headers.get('x-request-id');
    if (resRequestId) {
      responseHeaders.set('X-Request-ID', resRequestId);
    }

    // Set secure cache control on API gateway responses
    responseHeaders.set('Cache-Control', 'private, no-cache, no-store, must-revalidate');

    const resBody = await backendRes.text();
    return new NextResponse(resBody, {
      status: backendRes.status,
      headers: responseHeaders,
    });
  } catch (err: any) {
    return NextResponse.json(
      {
        code: 'GATEWAY_ERROR',
        detail: `Failed to connect to backend service: ${err.message || 'connection error'}`,
      },
      { status: 503, headers: { 'Content-Type': 'application/problem+json' } }
    );
  }
}

export const GET = handleGatewayRequest;
export const POST = handleGatewayRequest;
export const PUT = handleGatewayRequest;
