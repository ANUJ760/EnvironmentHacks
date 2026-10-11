'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowDownRight, ArrowUpRight, BookOpen, Bot, Clock3, RotateCcw, Trash2, TreePine } from 'lucide-react';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useRemovalStore } from '@/stores/removalStore';
import { fetchGateway } from '@/lib/api/browser-client';
import { getHumanErrorMessage } from '@/lib/api/problem';
import { formatImpact, previewGeometry, removalLocation, removableKind, replacementColor, type Finding, type RemovalMetric, type RemovalReport, type RemovalRequest, type RemovalWeather } from '@/lib/removal';

function RangeInput({ label, value, min, max, unit, onChange, step = 1 }: { label: string; value: number; min: number; max: number; unit: string; onChange: (value: number) => void; step?: number }) {
  return <label className="block space-y-1.5"><span className="flex justify-between text-[11px] text-muted"><span>{label}</span><strong className="text-ink">{formatImpact(value)} {unit}</strong></span><input aria-label={label} className="w-full accent-emerald-700" type="range" min={min} max={max} step={step} value={value} onChange={event => onChange(Number(event.target.value))} /></label>;
}

function MetricCard({ metric }: { metric: RemovalMetric }) {
  const beneficial = metric.key === 'runoff' && metric.delta < 0;
  return <div className="rounded-xl border border-border bg-white p-3" data-impact-metric={metric.key}>
    <div className="text-[11px] font-semibold text-ink">{metric.label}</div>
    <div className={`mt-1.5 flex items-center gap-1.5 text-xl font-bold ${beneficial ? 'text-emerald-700' : metric.delta === 0 ? 'text-slate-600' : 'text-amber-700'}`}>{metric.delta > 0 ? <ArrowUpRight size={17} /> : metric.delta < 0 ? <ArrowDownRight size={17} /> : null}{formatImpact(metric.delta, true)} <span className="text-xs font-medium text-muted">{metric.unit}</span></div>
    <div className="mt-1 flex gap-2 text-[10px] text-muted"><span>Before {formatImpact(metric.before)}</span><span>→</span><span>After {formatImpact(metric.after)}</span></div>
    {metric.low != null && metric.high != null && <p className="mt-1 text-[10px] text-muted">Sensitivity {formatImpact(metric.low, true)} to {formatImpact(metric.high, true)} {metric.unit}</p>}
    <details className="mt-2 text-[10px] text-muted"><summary className="cursor-pointer">{metric.evidence === 'ASSUMED_INPUT' ? 'Assumed inputs · method & limits' : metric.evidence === 'MAPPED_GEOMETRY' ? 'Mapped geometry · method & limits' : 'Screening estimate · method & limits'}</summary><p className="mt-1 leading-relaxed">{metric.method}. {metric.caveat}</p></details>
  </div>;
}

export function RemovalPanel({ cityId }: { cityId: string }) {
  const selected = useScenarioStore(state => state.selectedFeature);
  const kind = removableKind(selected);
  const { preview, showingAfter, setPreview, setShowingAfter } = useRemovalStore();
  const [replacement, setReplacement] = useState<RemovalRequest['replacement']>('grass');
  const [soil, setSoil] = useState<RemovalRequest['soil_group']>('B');
  const [crown, setCrown] = useState(8);
  const [trunk, setTrunk] = useState(30);
  const [shade, setShade] = useState(80);
  const [width, setWidth] = useState(6);
  const [length, setLength] = useState(50);
  const [roof, setRoof] = useState(50);
  const [hours, setHours] = useState(24);
  const [storm, setStorm] = useState(30);
  const [designStorm, setDesignStorm] = useState(false);
  const [ai, setAi] = useState<{ heading: string; model: string; findings: Finding[]; note: string } | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState('');
  const signature = JSON.stringify([kind, selected?.geometry, selected?.properties?.clicked_location]);
  useEffect(() => {
    setReplacement(kind === 'tree' ? 'unchanged' : kind === 'park' ? 'bare' : 'grass');
    setPreview(null); setAi(null); setAiError('');
  }, [signature, kind, setPreview]);
  useEffect(() => () => setPreview(null), [setPreview]);

  const request = useMemo<RemovalRequest | null>(() => kind && selected?.geometry ? ({ kind, geometry: selected.geometry, location: removalLocation(selected), replacement, baseline_cover: 'grass', soil_group: soil, forecast_hours: hours, rainfall_mm: designStorm ? storm : null, crown_diameter_m: crown, trunk_diameter_cm: trunk, shade_fraction: shade / 100, road_width_m: width, road_length_m: length, roof_usable_fraction: roof / 100 }) : null, [selected, kind, replacement, soil, hours, storm, designStorm, crown, trunk, shade, width, length, roof]);
  const requestRef = useRef(request);
  requestRef.current = request;
  const [debounced, setDebounced] = useState(request);
  useEffect(() => { const timer = setTimeout(() => setDebounced(request), 300); return () => clearTimeout(timer); }, [request]);
  const current = JSON.stringify(debounced) === JSON.stringify(request);
  const { data: report, error, isFetching } = useQuery({ queryKey: ['removal-preview', cityId, debounced], queryFn: async ({ signal }) => (await fetchGateway<RemovalReport>(`/api/gateway/v1/cities/${cityId}/removal-preview`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(debounced), signal })).data, enabled: !!debounced && current, staleTime: 45000, refetchInterval: 60000, retry: 1 });
  const { data: localAi } = useQuery<{ available: boolean; model: string | null }>({ queryKey: ['local-removal-ai'], queryFn: async () => (await fetch('/api/removal/explain')).json(), staleTime: 60000 });
  const [previewEnabled, setPreviewEnabled] = useState(false);
  useEffect(() => { setPreviewEnabled(false); }, [signature]);
  useEffect(() => {
    if (previewEnabled && report && current) setPreview({ geometry: previewGeometry(report), color: replacementColor(replacement || 'grass'), kind: report.kind, area: report.area_m2 });
    else setPreview(null);
  }, [previewEnabled, report, current, replacement, setPreview]);
  useEffect(() => { setAi(null); setAiError(''); }, [request]);

  async function explain() {
    if (!request) return;
    setAiBusy(true); setAiError('');
    const key = JSON.stringify(request);
    try {
      const response = await fetch('/api/removal/explain', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cityId, request }), signal: AbortSignal.timeout(60000) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Local explanation unavailable');
      // A changed request unmounts the keyed panel at feature changes. Sliders
      // clear the previous explanation and the following guard rejects stale work.
      if (key === JSON.stringify(requestRef.current)) setAi(result);
    } catch (error) { if (key === JSON.stringify(requestRef.current)) setAiError(error instanceof Error ? error.message : 'Local explanation unavailable'); }
    finally { setAiBusy(false); }
  }

  if (!kind) return <div className="rounded-xl border border-dashed border-border bg-slate-50 p-5 text-center"><TreePine className="mx-auto text-primary" size={25} /><h3 className="font-semibold text-ink mt-2">Explore a removal</h3><p className="text-xs text-muted mt-2 leading-relaxed">Click a tree, building, park or road to estimate what changes if it is removed. Water and monitoring stations are observational features.</p></div>;
  const weather = report?.weather as unknown as RemovalWeather | undefined;
  const findings = report?.findings as unknown as Finding[] | undefined;
  const sources = report?.sources as unknown as { id: string; title: string; url: string }[] | undefined;
  const hourly = report?.hourly as unknown as { valid_at: string; delta_kwh: number }[] | undefined;
  const maximum = Math.max(...(hourly?.map(sample => Math.abs(sample.delta_kwh)) || [0]), 0.001);
  return <div className="space-y-4" data-removal-panel={kind}>
    <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3"><div className="flex items-center gap-2 text-emerald-900 font-bold"><Trash2 size={15} /> What if this {kind} is removed?</div><p className="text-[11px] text-emerald-800 mt-1.5 leading-relaxed">Adjust the assumptions below. Estimates update automatically; the real city and saved scenarios stay unchanged.</p></div>
    <button disabled={!report || !current || isFetching} onClick={() => { setPreviewEnabled(!previewEnabled); if (previewEnabled) setPreview(null); }} className="w-full rounded-xl bg-primary px-3 py-2.5 text-white text-xs font-semibold disabled:opacity-40 flex items-center justify-center gap-2">{previewEnabled ? <RotateCcw size={14} /> : <Trash2 size={14} />}{previewEnabled ? 'Restore feature' : 'Preview removal on map'}</button>
    {preview && previewEnabled && <div className="flex gap-1 p-1 bg-slate-100 rounded-lg">{[false, true].map(after => <button key={String(after)} onClick={() => setShowingAfter(after)} aria-pressed={showingAfter === after} className={`flex-1 rounded-md py-1.5 text-xs ${showingAfter === after ? 'bg-white shadow-sm text-primary font-bold' : 'text-muted'}`}>{after ? 'After removal' : 'Before'}</button>)}</div>}
    <div className="space-y-3 rounded-xl border border-border bg-slate-50 p-3"><h4 className="text-[10px] uppercase tracking-wide font-bold text-muted">Removal assumptions</h4>
      <label className="block text-[11px] text-muted">Ground after removal<select aria-label="Ground after removal" value={replacement} onChange={event => setReplacement(event.target.value as RemovalRequest['replacement'])} className="mt-1 block w-full p-2 rounded-lg border border-border bg-white text-ink"><option value="unchanged">Keep existing ground</option><option value="grass">Grass / planted open space</option><option value="bare">Bare, disturbed soil</option><option value="impervious">Paved / sealed ground</option></select></label>
      {kind === 'tree' && <><RangeInput label="Assumed crown diameter" value={crown} min={1} max={20} unit="m" onChange={setCrown} /><RangeInput label="Assumed trunk diameter (DBH)" value={trunk} min={3} max={100} unit="cm" onChange={setTrunk} /><RangeInput label="Assumed foliage shade" value={shade} min={0} max={100} unit="%" onChange={setShade} /><p className="text-[10px] text-muted">Tree sizes are not measured in this dataset. Use field measurements when available.</p></>}
      {kind === 'road' && <><RangeInput label="Assumed road width" value={width} min={1} max={20} unit="m" onChange={setWidth} /><RangeInput label="Road segment length" value={length} min={5} max={200} unit="m" onChange={setLength} /></>}
      {kind === 'building' && <RangeInput label="Assumed usable roof area" value={roof} min={0} max={100} unit="%" onChange={setRoof} />}
      <label className="block text-[11px] text-muted">Assumed soil group<select aria-label="Assumed soil group" value={soil} onChange={event => setSoil(event.target.value as RemovalRequest['soil_group'])} className="mt-1 block w-full p-2 rounded-lg border border-border bg-white text-ink">{['A', 'B', 'C', 'D'].map((group, index) => <option key={group} value={group}>{group} · {['High infiltration', 'Moderate infiltration', 'Low infiltration', 'Very low infiltration'][index]}</option>)}</select></label>
      <label className="block text-[11px] text-muted">Forecast window<select aria-label="Forecast window" value={hours} onChange={event => setHours(Number(event.target.value))} className="mt-1 block w-full p-2 rounded-lg border border-border bg-white text-ink">{[12, 24, 48, 72].map(hour => <option key={hour} value={hour}>Next {hour} hours</option>)}</select></label>
      <label className="flex items-center gap-2 text-[11px] text-muted"><input type="checkbox" checked={designStorm} onChange={event => setDesignStorm(event.target.checked)} className="accent-emerald-700" />Test a design storm instead of forecast rain</label>
      {designStorm && <RangeInput label="Design storm rainfall" value={storm} min={0} max={150} unit="mm" onChange={setStorm} />}
    </div>
    <div role="status" aria-live="polite" className="text-[11px] text-muted">{isFetching || !current ? <span className="flex items-center gap-1.5"><Clock3 size={12} /> Updating consequences…</span> : error ? getHumanErrorMessage(error) : report ? `Updated ${new Date(report.computed_at).toLocaleTimeString()} · ${formatImpact(report.area_m2)} m² affected` : 'Preparing the preview…'}</div>
    {report && current && <>
      <div className="space-y-2" data-removal-results>{report.metrics.map(metric => <MetricCard key={metric.key} metric={metric} />)}</div>
      {weather && <div className="rounded-xl border border-border p-3 text-[10px] text-muted space-y-1"><strong className="text-ink">{weather.source === 'live_forecast' ? 'Live Open-Meteo forecast' : weather.source === 'pinned_forecast' ? 'Published forecast fallback' : 'Weather unavailable'}</strong><p>{weather.hours_available} hourly samples · {weather.rainfall_mm == null ? 'rainfall incomplete' : `${formatImpact(weather.rainfall_mm)} mm forecast rain`}{designStorm ? ` · runoff uses ${storm} mm design storm` : ''}</p><p>Fetched {new Date(weather.fetched_at).toLocaleString()}{weather.stale ? ' · STALE' : ''}</p><p>{weather.spatial_scope}. Refreshed at most every 5 minutes.</p>{weather.notice && <p>{weather.notice}</p>}</div>}
      {hourly && hourly.length > 0 && <div className="rounded-xl border border-border p-3"><h4 className="text-[11px] font-semibold text-ink">{kind === 'tree' ? 'Potential extra sunlight at ground' : 'Foregone roof-solar opportunity'}</h4><div className="flex items-end gap-[2px] h-16 mt-3" role="img" aria-label="Hourly weather-dependent consequence chart">{hourly.map(sample => <div key={sample.valid_at} className="flex-1 rounded-t-sm bg-amber-400 min-w-0" style={{ height: `${Math.max(2, Math.abs(sample.delta_kwh) / maximum * 100)}%` }} title={`${new Date(sample.valid_at).toLocaleString()}: ${formatImpact(sample.delta_kwh, true)} kWh`} />)}</div><p className="text-[9px] text-muted mt-1">Hourly · next {hours} hours · kWh</p></div>}
      <div className="space-y-2"><h4 className="font-semibold text-ink text-[11px]">Consequences supported by the evidence</h4>{findings?.map(finding => <p key={finding.id} className="text-[11px] text-muted leading-relaxed">{finding.text}</p>)}</div>
      <div className="rounded-xl border border-violet-200 bg-violet-50 p-3"><button onClick={explain} disabled={aiBusy || !localAi?.available} className="w-full flex items-center justify-center gap-2 text-xs font-semibold text-violet-800 disabled:opacity-50"><Bot size={15} />{aiBusy ? 'Local model is explaining…' : localAi?.available ? `Explain with ${localAi.model}` : 'Local Gemma / Qwen unavailable'}</button><p className="mt-2 text-[10px] text-violet-700">Optional local AI organizes the research findings. It cannot change the calculated numbers.</p>{aiError && <p role="alert" className="text-[10px] text-rose-700 mt-2">{aiError}</p>}{ai && <div className="mt-3 space-y-2" data-local-ai-explanation><strong className="text-[11px] text-violet-900">{ai.heading}</strong>{ai.findings.map(finding => <p key={finding.id} className="text-[11px] leading-relaxed text-violet-900">{finding.text}</p>)}<p className="text-[9px] text-violet-700">{ai.model} · {ai.note}</p></div>}</div>
      <details className="text-[10px] text-muted"><summary className="cursor-pointer font-semibold">Evidence, sources & limitations</summary><p className="mt-2">{report.geometry_source}</p><p className="mt-1">{report.within_analysis_area ? 'Inside the verified study area.' : 'Outside the verified study area: exploratory assumptions apply.'}</p><ul className="list-disc pl-4 mt-2 space-y-1">{report.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul><div className="mt-3 space-y-2">{sources?.map(source => <a key={source.id} href={source.url} target="_blank" rel="noreferrer" className="flex items-start gap-1 text-primary underline"><BookOpen size={11} className="shrink-0 mt-0.5" />{source.title}</a>)}</div></details>
    </>}
  </div>;
}
