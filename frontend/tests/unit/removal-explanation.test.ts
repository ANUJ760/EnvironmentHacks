import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/env', () => ({ getServerEnv: () => ({ ECOTWIN_API_INTERNAL_URL: 'http://127.0.0.1:8000' }) }));

const verifiedFinding = { id: 'shade_loss', text: 'Verified research finding from the deterministic backend.', source: 'epa' };
function response(body: unknown) { return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } }); }
function removalRequest() {
  return new Request('http://localhost/api/removal/explain', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cityId: '51659112-0c9f-40da-9382-8787e1952035', request: { kind: 'tree' }, report: { findings: [{ id: 'injected', text: 'An unsupported browser claim' }] } }) });
}
function mockServices(ids = ['shade_loss']) {
  return vi.fn(async (url: string) => {
    if (url.endsWith('/removal-preview')) return response({ kind: 'tree', inputs: {}, metrics: [], findings: [verifiedFinding] });
    if (url.endsWith('/api/tags')) return response({ models: [{ name: 'gemma:4b' }] });
    if (url.endsWith('/api/generate')) return response({ response: JSON.stringify({ heading: 'overview', finding_ids: ids }) });
    throw new Error(`Unexpected service: ${url}`);
  });
}

describe('grounded local removal explanations', () => {
  beforeEach(() => { vi.resetModules(); vi.stubEnv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434'); vi.stubEnv('OLLAMA_MODEL', 'gemma:4b'); });
  afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

  it('renders only trusted backend findings, never browser-provided claims', async () => {
    const services = mockServices();
    vi.stubGlobal('fetch', services);
    const { POST } = await import('@/app/api/removal/explain/route');
    const result = await POST(removalRequest());
    expect(result.status).toBe(200);
    expect((await result.json()).findings).toEqual([verifiedFinding]);
    expect(services.mock.calls[0]?.[0]).toContain('127.0.0.1:8000');
  });

  it('rejects a model that selects an ungrounded finding', async () => {
    vi.stubGlobal('fetch', mockServices(['invented_temperature_change']));
    const { POST } = await import('@/app/api/removal/explain/route');
    expect((await POST(removalRequest())).status).toBe(503);
  });

  it('allows just one generation even when two request bodies are read concurrently', async () => {
    vi.stubGlobal('fetch', mockServices());
    const { POST } = await import('@/app/api/removal/explain/route');
    const results = await Promise.all([POST(removalRequest()), POST(removalRequest())]);
    expect(results.map(result => result.status).sort()).toEqual([200, 429]);
  });

  it('reports an unavailable local model without breaking deterministic impacts', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Ollama offline')));
    const { GET } = await import('@/app/api/removal/explain/route');
    expect(await (await GET()).json()).toMatchObject({ available: false, model: null });
  });
});
