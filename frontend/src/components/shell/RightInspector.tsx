'use client';
import { PlanningPanel } from '@/components/map/PlanningPanel';
import { useScenarioStore } from '@/stores/scenarioStore';
export function RightInspector({ cityId }: { cityId?: string }) {
  const feature = useScenarioStore(state => state.selectedFeature);
  return <aside className="planning-inspector glass-pane overflow-y-auto shrink-0 p-4" aria-label="Effect specifics">
    <h2 className="text-primary text-lg mb-4">Effects & inputs</h2>
    {cityId && <PlanningPanel cityId={cityId} key={JSON.stringify([feature?.geometry, feature?.properties?.clicked_location])} />}
  </aside>;
}
