'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Download, Info, RotateCcw, SlidersHorizontal, Sparkles, Trash2 } from 'lucide-react';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useRemovalStore } from '@/stores/removalStore';
import { fetchGateway } from '@/lib/api/browser-client';
import { getHumanErrorMessage } from '@/lib/api/problem';
import { formatImpact, removalLocation, replacementColor, type Finding, type RemovalMetric } from '@/lib/removal';
import { exportPlanningReport, planningKind, type PlanningRequest, type PlanningReport, type PlanningAir, type PlanningInventory } from '@/lib/planning';

const AIR_FIELDS: [string, string][] = [['pm2_5', 'PM₂.₅'], ['nitrogen_dioxide', 'NO₂'], ['carbon_dioxide', 'CO₂'], ['ozone', 'O₃']];
const DEFAULTS = { crown_diameter_m: 8, trunk_diameter_cm: 30, road_width_m: 6, road_length_m: 50,
  building_levels: 3, energy_kwh_m2_year: 100, floor_m2_per_person: 40, waste_kg_person_day: 1,
  displaced_fraction: 1, demolition_t_m2: 0.8, recovery_fraction: 0.6, forest_carbon_kg_m2: 7,
  water_depth_m: 1.5, fill_height_m: 0.5, fill_density_t_m3: 1.6, leaf_area_index: 3, deposition_velocity_mm_s: 1 };
type Parameter = keyof typeof DEFAULTS;
const FIELDS: [Parameter, string, string, number, number, string][] = [
  ['crown_diameter_m', 'Assumed crown diameter', 'm', 1, 30, 'tree'],
  ['trunk_diameter_cm', 'Assumed trunk diameter', 'cm', 3, 150, 'tree'],
  ['road_width_m', 'Assumed road width', 'm', 1, 30, 'road'],
  ['road_length_m', 'Road segment length', 'm', 5, 300, 'road'],
  ['building_levels', 'Fallback building floors', 'floors', 1, 60, 'area building'],
  ['energy_kwh_m2_year', 'Operational energy intensity', 'kWh/m²/year', 0, 600, 'area building'],
  ['floor_m2_per_person', 'Floor area per occupant', 'm²/person', 5, 500, 'area building'],
  ['waste_kg_person_day', 'Daily waste per occupant', 'kg/person/day', 0, 10, 'area building'],
  ['displaced_fraction', 'Activity displaced elsewhere', 'fraction (1 = all)', 0, 1, 'area building'],
  ['demolition_t_m2', 'Demolition material intensity', 't/m²', 0, 5, 'area building'],
  ['recovery_fraction', 'Demolition recovery', 'fraction (1 = all)', 0, 1, 'area building'],
  ['forest_carbon_kg_m2', 'Forest aboveground carbon density', 'kg C/m²', 0, 50, 'area park'],
  ['water_depth_m', 'Assumed water depth', 'm', 0, 30, 'fill'],
  ['fill_height_m', 'Land height increase', 'm', 0, 20, 'fill'],
  ['fill_density_t_m3', 'Fill bulk density', 't/m³', 0.5, 3, 'fill'],
  ['leaf_area_index', 'Assumed leaf area index', 'm² leaf/m²', 0, 10, 'tree park area'],
  ['deposition_velocity_mm_s', 'PM deposition velocity proxy', 'mm/s', 0, 10, 'tree park area'],
];

function NumericInput({ label, value, min, max, unit, onChange }: { label: string; value: number; min: number; max: number; unit: string; onChange: (value: number) => void }) {
  return <label className="block"><span className="flex justify-between gap-3 text-xs text-muted mb-1.5"><span>{label}</span><span>{unit}</span></span><input aria-label={label} type="number" className="planning-field" value={value} min={min} max={max} step="any" onChange={event => { const number = Number(event.target.value); if (Number.isFinite(number)) onChange(Math.max(min, Math.min(max, number))); }} /></label>;
}

function ImpactCard({ metric }: { metric: RemovalMetric }) {
  return <div className="planning-card" data-impact-metric={metric.key}><h4 className="text-sm font-semibold">{metric.label}</h4><div className="flex items-center gap-2 mt-2 text-sm text-muted"><span>{formatImpact(metric.before)}</span><ArrowRight size={14} /><span>{formatImpact(metric.after)}</span><span className="ml-auto text-xs">{metric.unit}</span></div><div className={`mt-2 text-2xl font-bold ${metric.delta === 0 ? 'text-slate-600' : 'text-primary'}`}>{formatImpact(metric.delta, true)} <span className="text-sm font-normal">{metric.unit}</span></div><details className="mt-2 text-xs text-muted"><summary className="cursor-pointer">{metric.evidence === 'ASSUMED_INPUT' ? 'Assumption-based · details' : metric.evidence === 'MAPPED_GEOMETRY' ? 'Mapped data · details' : 'Screening model · details'}</summary><p className="mt-2">{metric.method}. {metric.caveat}</p>{metric.low != null && metric.high != null && <p className="mt-2">Sensitivity: {formatImpact(metric.low)} to {formatImpact(metric.high)} {metric.unit}</p>}</details></div>;
}

export function PlanningPanel({ cityId }: { cityId: string }) {
  const feature = useScenarioStore(state => state.selectedFeature);
  const kind = planningKind(feature);
  const { preview, showingAfter, setPreview, setShowingAfter } = useRemovalStore();
  const [action, setAction] = useState<PlanningRequest['action']>('remove');
  const [replacement, setReplacement] = useState<PlanningRequest['replacement']>(kind === 'tree' ? 'unchanged' : 'grass');
  const [soil, setSoil] = useState<PlanningRequest['soil_group']>('B');
  const [hours, setHours] = useState(24);
  const [designStorm, setDesignStorm] = useState(false);
  const [storm, setStorm] = useState(30);
  const [parameters, setParameters] = useState(DEFAULTS);
  const [previewEnabled, setPreviewEnabled] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState('');
  const [ai, setAi] = useState<{ heading: string; findings: Finding[]; model: string } | null>(null);
  const request = useMemo<PlanningRequest | null>(() => kind ? ({ geometry: feature.geometry, selection_type: kind,
    location: removalLocation(feature), action, replacement: action === 'green' ? 'grass' : replacement,
    soil_group: soil, forecast_hours: hours, rainfall_mm: designStorm ? storm : null, ...parameters }) : null,
  [kind, feature, action, replacement, soil, hours, designStorm, storm, parameters]);
  const requestRef = useRef(request); requestRef.current = request;
  const [debounced, setDebounced] = useState(request);
  useEffect(() => { const timer = setTimeout(() => setDebounced(request), 400); return () => clearTimeout(timer); }, [request]);
  const current = JSON.stringify(request) === JSON.stringify(debounced);
  const { data: report, error, isFetching } = useQuery({ queryKey: ['planning-preview', cityId, debounced], enabled: !!debounced && current,
    queryFn: async ({ signal }) => (await fetchGateway<PlanningReport>(`/api/gateway/v1/cities/${cityId}/planning-preview`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(debounced), signal })).data,
    staleTime: 45000, refetchInterval: 60000, retry: 1 });
  const { data: localAi } = useQuery<{ available: boolean; model: string | null }>({ queryKey: ['local-removal-ai'], queryFn: async () => (await fetch('/api/removal/explain')).json(), staleTime: 60000 });
  useEffect(() => () => setPreview(null), [setPreview]);
  useEffect(() => { setAi(null); setAiError(''); }, [request]);
  useEffect(() => {
    if (previewEnabled && report && current) setPreview({ geometry: report.affected_geometry as any, color: replacementColor(action === 'green' ? 'grass' : replacement || 'grass'), kind: kind || 'area', area: report.area_m2 });
    else setPreview(null);
  }, [previewEnabled, report, current, replacement, action, kind, setPreview]);
  async function explain() {
    const key = JSON.stringify(request); setAiBusy(true); setAiError('');
    try {
      const response = await fetch('/api/removal/explain', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cityId, request, mode: 'planning' }), signal: AbortSignal.timeout(60000) });
      const result = await response.json(); if (!response.ok) throw new Error(result.detail);
      if (key === JSON.stringify(requestRef.current)) setAi(result);
    } catch (error) { if (key === JSON.stringify(requestRef.current)) setAiError(error instanceof Error ? error.message : 'Explanation unavailable'); }
    finally { setAiBusy(false); }
  }
  if (!kind) return <div className="planning-card light-surface bg-sky-50"><h2 className="text-xl font-bold">Plan a city change</h2><p className="mt-3 text-sm text-muted">Click a feature, or draw any area. Compare energy, waste, water and vegetation effects.</p><div className="mt-5 flex flex-wrap gap-2 text-xs">{['Energy', 'Waste', 'Water', 'Environment'].map(label => <span key={label} className="rounded-full bg-white px-3 py-1 border border-sky-200">{label}</span>)}</div><p className="mt-4 text-xs text-muted">Screening estimates, with sources and uncertainty.</p></div>;
  const inventory = report?.inventory as unknown as PlanningInventory | undefined;
  const air = report?.air as unknown as PlanningAir | undefined;
  const findings = report?.findings as unknown as Finding[] | undefined;
  const primaryKeys = ['runoff', 'energy_system', 'waste_system', 'demolition', 'residual', 'fill_volume', 'water_area', 'carbon', 'vegetation', 'pm_deposition'];
  const primaryMetrics = report?.metrics.filter(metric => primaryKeys.includes(metric.key)) || [];
  const secondary = report?.metrics.filter(metric => !primaryKeys.includes(metric.key)) || [];
  const weather = report?.weather as Record<string, any> | undefined;
  const solar = (report?.hourly as unknown as { key: string; valid_at: string; delta_kwh: number }[] | undefined)?.filter(row => row.key === (kind === 'tree' ? 'solar_exposure' : 'roof_solar')) || [];
  const solarMax = Math.max(0.001, ...solar.map(row => Math.abs(row.delta_kwh)));
  return <div className="space-y-4 light-surface" data-removal-panel={kind} data-planning-panel={kind}>
    <div className="planning-card bg-sky-100 border-sky-200"><h2 className="text-lg font-bold capitalize">{kind === 'area' ? 'Custom area' : kind} intervention</h2><p className="mt-1 text-sm text-muted">Before → after, under the same conditions.</p></div>
    <div className="planning-card space-y-3"><label className="block text-sm font-semibold">Change<select aria-label="Intervention action" className="planning-field mt-1" value={action} onChange={event => setAction(event.target.value as PlanningRequest['action'])}><option value="remove">Remove / clear</option><option value="fill">Fill / raise ground</option><option value="green">Convert to grass</option></select></label>
      {action !== 'green' && <label className="block text-sm font-semibold">Replacement<select aria-label="Ground after removal" className="planning-field mt-1" value={replacement} onChange={event => setReplacement(event.target.value as PlanningRequest['replacement'])}><option value="unchanged">Keep ground surface</option><option value="grass">Grass / open space</option><option value="bare">Bare disturbed soil</option><option value="impervious">Paved / sealed ground</option></select></label>}
      <div className="grid grid-cols-2 gap-3"><label className="text-xs">Forecast<select aria-label="Forecast window" className="planning-field mt-1" value={hours} onChange={event => setHours(Number(event.target.value))}>{[12, 24, 48, 72].map(value => <option key={value} value={value}>{value} hours</option>)}</select></label><label className="text-xs">Soil group<select aria-label="Assumed soil group" className="planning-field mt-1" value={soil} onChange={event => setSoil(event.target.value as PlanningRequest['soil_group'])}>{['A', 'B', 'C', 'D'].map(value => <option key={value}>{value}</option>)}</select></label></div>
      <label className="flex gap-2 items-center text-xs text-muted"><input type="checkbox" checked={designStorm} onChange={event => setDesignStorm(event.target.checked)} />Test a design storm instead of forecast rain</label>
      {designStorm && <NumericInput label="Design storm rainfall" value={storm} min={0} max={300} unit="mm" onChange={setStorm} />}
      <details><summary className="flex gap-2 items-center cursor-pointer text-sm font-semibold"><SlidersHorizontal size={16} />Assumptions</summary><p className="text-xs text-muted mt-2">Defaults are scenarios, not field measurements.</p><div className="space-y-3 mt-3">{FIELDS.filter(field => field[5].split(' ').includes(kind) || field[5] === action).map(([key, label, unit, min, max]) => <NumericInput key={key} label={label} value={parameters[key]} min={min} max={max} unit={unit} onChange={value => setParameters(previous => ({ ...previous, [key]: value }))} />)}</div></details>
    </div>
    <div role="status" aria-live="polite" className="text-xs text-slate-300 px-1">{!current || isFetching ? 'Calculating city impacts…' : error ? getHumanErrorMessage(error) : report ? `${formatImpact(report.area_m2)} m² · updated ${new Date(report.computed_at).toLocaleTimeString()}` : 'Preparing selection…'}</div>
    {report && current && <>
      {!report.within_analysis_area && <div className="planning-card bg-sky-50 text-sm">Exploratory selection: outside the verified study area. Missing data are not extrapolated.</div>}
      <button className="w-full rounded-xl bg-primary text-white py-3 font-semibold text-sm flex items-center justify-center gap-2 disabled:opacity-50" disabled={isFetching} onClick={() => setPreviewEnabled(value => !value)}>{previewEnabled ? <RotateCcw size={17} /> : <Trash2 size={17} />}{previewEnabled ? 'Restore feature' : 'Preview removal on map'}</button>
      {preview && previewEnabled && <div className="flex gap-2">{[false, true].map(after => <button key={String(after)} aria-pressed={showingAfter === after} className={`flex-1 rounded-xl py-2 text-sm border ${showingAfter === after ? 'bg-sky-100 text-primary border-sky-300' : 'bg-white text-muted border-border'}`} onClick={() => setShowingAfter(after)}>{after ? 'After removal' : 'Before'}</button>)}</div>}
      {inventory && <div className="planning-card"><h3 className="text-sm font-semibold">Detected from mapped data</h3><div className="grid grid-cols-3 gap-2 mt-3 text-center">{[[inventory.buildings_count, 'Buildings'], [inventory.mapped_trees_count, 'Mapped trees'], [inventory.roads_count, 'Roads']].map(([value, label]) => <div key={label}><strong className="text-xl">{value}</strong><p className="text-xs text-muted">{label}</p></div>)}</div><p className="text-xs text-muted mt-3">Land-cover coverage {Math.round(report.coverage_fraction * 100)}% · 2021 reference</p></div>}
      <section aria-label="Before and after consequences" className="space-y-3" data-removal-results>{primaryMetrics.length ? primaryMetrics.map(metric => <ImpactCard key={metric.key} metric={metric} />) : <div className="planning-card text-sm">No quantified change available. See evidence gaps below.</div>}</section>
      {secondary.length > 0 && <details className="planning-card"><summary className="cursor-pointer text-sm font-semibold">Energy, materials & all metrics ({secondary.length})</summary><div className="space-y-3 mt-3">{secondary.map(metric => <ImpactCard key={metric.key} metric={metric} />)}</div></details>}
      {air && <div className="planning-card bg-sky-50" data-air-baseline><h3 className="text-sm font-semibold">Regional air baseline</h3>{air.status === 'AVAILABLE' ? <><div className="grid grid-cols-2 gap-3 mt-3">{AIR_FIELDS.map(([key, label]) => <div key={key}><p className="text-xs text-muted">{label}</p><strong>{typeof air.current[key] === 'number' ? formatImpact(air.current[key] as number) : '—'}</strong><span className="text-xs ml-1">{air.units[key]}</span></div>)}</div><p className="text-xs text-muted mt-3">CAMS model · regional, not street-level{air.stale ? ' · stale' : ''}</p></> : <p className="text-sm text-muted mt-2">Unavailable. No fabricated concentrations.</p>}<p className="text-xs text-muted mt-2">O₂ and water chemistry: unavailable</p></div>}
      {weather && <div className="planning-card text-sm"><h3 className="font-semibold">{weather.source === 'live_forecast' ? 'Live Open-Meteo forecast' : weather.source === 'pinned_forecast' ? 'Published weather fallback' : 'Weather unavailable'}</h3><p className="text-xs text-muted mt-2">{weather.hours_available} hourly samples · {weather.rainfall_mm == null ? 'rain incomplete' : `${formatImpact(weather.rainfall_mm)} mm rain`}{designStorm ? ` · runoff uses ${storm} mm design storm` : ''}{weather.stale ? ' · stale' : ''}</p><p className="text-xs text-muted mt-1">Coarse grid · {new Date(weather.fetched_at).toLocaleString()}</p></div>}
      {solar.length > 0 && <details className="planning-card"><summary className="cursor-pointer text-sm font-semibold">Hourly solar consequence</summary><div role="img" aria-label="Hourly weather-dependent consequence chart" className="flex items-end gap-1 h-16 mt-4">{solar.map(row => <div key={row.valid_at} className="flex-1 bg-sky-400 rounded-t" style={{ height: `${Math.max(2, Math.abs(row.delta_kwh) / solarMax * 100)}%` }} title={`${row.valid_at}: ${formatImpact(row.delta_kwh)} kWh`} />)}</div></details>}
      {findings && findings.length > 0 && <details className="planning-card"><summary className="cursor-pointer text-sm font-semibold">Trade-offs & consequences</summary><div className="mt-3 space-y-3">{findings.map(finding => <p key={finding.id} className="text-sm text-muted">{finding.text}</p>)}</div></details>}
      <details className="planning-card"><summary className="cursor-pointer flex items-center gap-2 text-sm font-semibold"><Info size={16} />Evidence & limits</summary><p className="text-xs text-muted mt-3">{report.geometry_source}</p><ul className="list-disc pl-4 mt-3 space-y-2 text-xs text-muted">{report.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul><div className="mt-3 space-y-2">{(report.sources as unknown as { id: string; title: string; url: string }[]).map(source => <a key={source.id} href={source.url} target="_blank" rel="noreferrer" className="block text-xs text-primary underline">{source.title}</a>)}</div></details>
      <details className="planning-card"><summary className="cursor-pointer flex gap-2 items-center text-sm font-semibold"><Sparkles size={16} />Local AI explanation</summary><p className="text-xs text-muted mt-2">Organizes verified findings. Never changes the physics.</p><button disabled={aiBusy || !localAi?.available || !findings?.length} className="mt-3 rounded-lg bg-sky-100 text-primary px-3 py-2 text-sm font-semibold disabled:opacity-50" onClick={explain}>{aiBusy ? 'Explaining…' : localAi?.available ? `Explain with ${localAi.model}` : 'Ollama unavailable'}</button>{aiError && <p role="alert" className="text-xs text-rose-700 mt-2">{aiError}</p>}{ai && <div data-local-ai-explanation className="mt-3 space-y-2"><strong className="text-sm">{ai.heading}</strong>{ai.findings.map(finding => <p key={finding.id} className="text-sm text-muted">{finding.text}</p>)}<p className="text-xs text-muted">{ai.model} · All quantities are computed by the deterministic screening model.</p></div>}</details>
      <button onClick={() => exportPlanningReport(report)} className="w-full flex justify-center gap-2 rounded-xl border border-sky-300 bg-white text-primary py-3 text-sm font-semibold"><Download size={17} />Export research report</button><p className="text-xs text-slate-300 text-center">Pinned sources · inputs · model version · checksums</p>
    </>}
  </div>;
}
