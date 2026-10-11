import { afterEach, expect, it, vi } from 'vitest';
import { GET } from '@/app/api/removal/explain/route';

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

it.each(['http://169.254.169.254', 'http://unapproved.internal:11434', 'ftp://localhost', 'http://user:password@localhost'])('rejects an untrusted inference origin: %s', async origin => {
  vi.stubEnv('OLLAMA_BASE_URL', origin);
  vi.stubEnv('OLLAMA_ALLOWED_HOSTS', '');
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
  expect((await (await GET()).json()).available).toBe(false);
  expect(fetcher).not.toHaveBeenCalled();
});

it.each([['http://ollama:11434', ''], ['http://inference.private.internal:11434', 'inference.private.internal']])('accepts a configured trusted service: %s', async (origin, allowlist) => {
  vi.stubEnv('OLLAMA_BASE_URL', origin);
  vi.stubEnv('OLLAMA_ALLOWED_HOSTS', allowlist);
  vi.stubEnv('OLLAMA_MODEL', 'qwen2.5:1.5b');
  const fetcher = vi.fn(async () => new Response(JSON.stringify({ models: [{ name: 'qwen2.5:1.5b' }] }))); vi.stubGlobal('fetch', fetcher);
  expect((await (await GET()).json()).available).toBe(true);
  expect(fetcher).toHaveBeenCalledWith(`${origin}/api/tags`, expect.any(Object));
});
