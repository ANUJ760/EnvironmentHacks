import React from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { PlanningSummary } from '@/components/map/PlanningSummary';
import { useScenarioStore } from '@/stores/scenarioStore';
import { selectionKey, usePlanningResultStore } from '@/stores/planningResultStore';
import type { PlanningReport } from '@/lib/planning';

afterEach(() => { cleanup(); useScenarioStore.getState().setSelectedFeature(null); usePlanningResultStore.getState().publish(null, '', false); });
describe('synchronized summary', () => {
  const feature = { type: 'Feature' as const, geometry: { type: 'Point' as const, coordinates: [8.54, 47.38] }, properties: { category: 'mapped_tree' } };
  const report = { findings: [{ id: 'carbon', text: 'Vegetation carbon is lost.' }], within_analysis_area: true, coverage_fraction: 1 } as unknown as PlanningReport;
  it('does not show a report from an earlier selection', () => {
    useScenarioStore.getState().setSelectedFeature(feature);
    usePlanningResultStore.getState().publish(report, 'previous-selection', false);
    render(<PlanningSummary />);
    expect(screen.queryByText('Vegetation carbon is lost.')).toBeNull();
    act(() => usePlanningResultStore.getState().publish(report, selectionKey(feature), false));
    expect(screen.getByText('Vegetation carbon is lost.')).toBeVisible();
  });
  it('hides prior findings while changed assumptions are calculating', () => {
    useScenarioStore.getState().setSelectedFeature(feature);
    usePlanningResultStore.getState().publish(report, selectionKey(feature), true);
    render(<PlanningSummary />);
    expect(screen.queryByText('Vegetation carbon is lost.')).toBeNull();
    expect(screen.getByText(/Updating the before-and-after/)).toBeVisible();
  });
});
