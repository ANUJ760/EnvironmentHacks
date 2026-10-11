'use client';
import Link from 'next/link';
import { useScenarioStore } from '@/stores/scenarioStore';
import { selectionKey, usePlanningResultStore } from '@/stores/planningResultStore';
import type { Finding } from '@/lib/removal';
export function PlanningSummary() {
  const feature = useScenarioStore(state => state.selectedFeature);
  const { report, key, pending } = usePlanningResultStore();
  const current = key === selectionKey(feature) ? report : null;
  const findings = current?.findings as unknown as Finding[] | undefined;
  const unavailable = !!feature && key === selectionKey(feature) && !pending && !current;
  return <section className="planning-summary glass-pane p-5 overflow-y-auto" aria-label="Results summary" aria-live="polite">
    <div className="flex justify-between gap-3 mb-3"><h2 className="text-lg text-primary font-bold">Consequence summary</h2><span className="text-xs">{current ? 'Screening · not a calibrated prediction' : unavailable ? 'Results unavailable' : feature ? 'Calculating…' : 'Select a feature or draw an area'}</span></div>
    {current && !pending ? <><div className="grid gap-3 summary-findings">{findings?.slice(0, 4).map(finding => <p key={finding.id} className="text-sm">{finding.text}</p>)}</div><p className="text-xs text-primary mt-3">{current.within_analysis_area ? 'Within the published study area' : 'Outside study: incomplete evidence'} · {Math.round(current.coverage_fraction * 100)}% land-cover coverage</p><details className="mt-3 text-xs"><summary>Accuracy & validation</summary><p className="mt-2">Mapped geometry is not a field measurement. Tree inventory is incomplete; crown and trunk assumptions drive carbon estimates. Regional air is not street-level pollution. Model tests check consistency, not measured predictive accuracy.</p><p className="mt-2">Improve with surveyed trees, metered building energy, waste records and local rain/runoff sensors. Evaluate on held-out sites and dates using location precision/recall, MAE/RMSE, bias and interval coverage. See the accuracy guide.</p></details></> : <p className="text-sm">{feature ? 'Updating the before-and-after comparison. Previous results are hidden while inputs change.' : 'Remove trees, buildings or roads; clear, fill or green a selected area. Quantified effects appear on the right.'}</p>}
    {unavailable && <p className="text-sm mt-2">See the effects panel for the error. No quantities have been invented.</p>}
    <Link href="/data-methodology#accuracy" className="text-xs text-primary underline mt-3 inline-block">Accuracy evidence</Link>
  </section>;
}
