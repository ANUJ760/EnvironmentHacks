import { NextResponse } from 'next/server';
import { getServerEnv } from '@/lib/env';
import type { RemovalReport, Finding } from '@/lib/removal';

export const runtime = 'nodejs';
export const maxDuration = 60;
let busy = false;

function ollamaUrl() {
  const url = new URL(process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434');
  if (!['localhost', '127.0.0.1', 'host.docker.internal', 'ollama'].includes(url.hostname) || !['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Use a configured local Ollama service');
  return url.origin;
}

async function localModel() {
  const response = await fetch(`${ollamaUrl()}/api/tags`, { cache: 'no-store', signal: AbortSignal.timeout(3000) });
  if (!response.ok) throw new Error('Ollama model list unavailable');
  const names: string[] = ((await response.json()).models || []).map((model: { name: string }) => model.name);
  const preferred = process.env.OLLAMA_MODEL;
  const model = preferred && names.includes(preferred) ? preferred : ['gemma:4b', 'gemma4:e4b', 'qwen2.5:3b', 'qwen2.5-coder:7b'].find(name => names.includes(name)) || names.find(name => /^(gemma|qwen)/.test(name));
  if (!model) throw new Error('No local Gemma or Qwen model is installed');
  return model;
}

export async function GET() {
  try { return NextResponse.json({ available: true, model: await localModel(), busy }); }
  catch { return NextResponse.json({ available: false, model: null, busy: false }); }
}

export async function POST(req: Request) {
  if (busy) return NextResponse.json({ detail: 'Local AI is already explaining another preview. Try again shortly.' }, { status: 429 });
  let body: { cityId: string; request: unknown };
  try {
    const text = await req.text();
    if (text.length > 300000) throw new Error('Request too large');
    body = JSON.parse(text);
    if (!/^[a-f0-9-]{36}$/i.test(body.cityId) || !body.request) throw new Error('Invalid city');
  } catch { return NextResponse.json({ detail: 'A valid city and removal request are required.' }, { status: 400 }); }
  busy = true;
  try {
    const env = getServerEnv();
    // Recompute from the validated backend. Never trust a browser-supplied report
    // or feed OSM names/free-form prompt text to the model.
    const calculation = await fetch(`${env.ECOTWIN_API_INTERNAL_URL}/v1/cities/${body.cityId}/removal-preview`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body.request), signal: AbortSignal.timeout(15000) });
    if (!calculation.ok) return NextResponse.json({ detail: 'Calculate a valid removal preview before requesting an explanation.' }, { status: calculation.status });
    const report: RemovalReport = await calculation.json();
    const findings = report.findings as unknown as Finding[];
    const ids = findings.map(finding => finding.id);
    const schema = { type: 'object', additionalProperties: false, properties: { heading: { type: 'string', enum: ['overview', 'tradeoffs', 'uncertainty'] }, finding_ids: { type: 'array', minItems: 1, maxItems: 4, uniqueItems: true, items: { type: 'string', enum: ids } } }, required: ['heading', 'finding_ids'] };
    const model = await localModel();
    const generation = await fetch(`${ollamaUrl()}/api/generate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: AbortSignal.timeout(45000),
      body: JSON.stringify({ model, stream: false, think: false, keep_alive: '2m', format: schema, options: { temperature: 0, num_predict: 120, num_ctx: 2048, num_thread: 4 }, system: 'You organize environmental screening findings. Select and rank up to four of the supplied finding IDs for a clear explanation of this removal. Use only IDs and headings allowed by the JSON schema. You do not calculate, invent facts, or add quantitative claims.', prompt: JSON.stringify({ kind: report.kind, inputs: report.inputs, metrics: report.metrics.map(metric => ({ key: metric.key, delta: metric.delta, unit: metric.unit, evidence: metric.evidence })), findings, schema }) }),
    });
    if (!generation.ok) throw new Error('Local generation failed');
    const raw = await generation.json();
    const organized = JSON.parse(raw.response);
    if (!['overview', 'tradeoffs', 'uncertainty'].includes(organized.heading) || !Array.isArray(organized.finding_ids) || !organized.finding_ids.length || organized.finding_ids.length > 4 || !organized.finding_ids.every((id: unknown) => typeof id === 'string' && ids.includes(id))) throw new Error('Ungrounded response rejected');
    const selected = [...new Set(organized.finding_ids)] as string[];
    return NextResponse.json({ provider: 'ollama', model, heading: { overview: 'What changes when this feature is removed', tradeoffs: 'The environmental trade-offs', uncertainty: 'What the evidence can and cannot tell us' }[organized.heading as 'overview' | 'tradeoffs' | 'uncertainty'], findings: selected.map(id => findings.find(finding => finding.id === id)), note: 'Local AI organized verified findings. All quantities are computed by the deterministic screening model.', generated_at: new Date().toISOString() });
  } catch {
    return NextResponse.json({ detail: 'Local AI could not finish a grounded explanation. The calculated impacts and research findings remain available.' }, { status: 503 });
  } finally { busy = false; }
}
