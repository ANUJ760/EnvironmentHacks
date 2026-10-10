import createClient from 'openapi-fetch';
import type { paths } from './api-types';
import { parseProblemDetails } from './problem';

export const browserClient = createClient<paths>({
  baseUrl: '/api/gateway',
  headers: {
    Accept: 'application/json',
  },
});

export async function fetchGateway<T>(
  url: string,
  options?: RequestInit & { eTag?: string; idempotencyKey?: string }
): Promise<{ data: T; eTag?: string | null; status: number }> {
  const headers = new Headers(options?.headers || {});
  headers.set('Accept', 'application/json');

  if (options?.eTag) {
    headers.set('If-Match', options.eTag);
  }
  if (options?.idempotencyKey) {
    headers.set('Idempotency-Key', options.idempotencyKey);
  }

  const res = await fetch(url.startsWith('/') ? url : `/${url}`, {
    ...options,
    headers,
  });

  const responseETag = res.headers.get('ETag');

  if (!res.ok) {
    let errorBody: unknown;
    try {
      errorBody = await res.json();
    } catch {
      errorBody = { message: res.statusText };
    }
    throw parseProblemDetails(res.status, errorBody);
  }

  const data = (await res.json()) as T;
  return { data, eTag: responseETag, status: res.status };
}
