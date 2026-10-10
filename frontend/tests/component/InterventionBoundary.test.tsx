import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { InterventionEditor } from '@/components/scenarios/InterventionEditor';
import { useScenarioStore } from '@/stores/scenarioStore';

afterEach(() => { cleanup(); useScenarioStore.getState().resetScenario(); });

describe('Full-city exploration and bounded science', () => {
  it('prevents staging solar and land-cover interventions outside the verified analysis area', () => {
    const geometry = { type: 'Polygon', coordinates: [[[8.53, 47.37], [8.54, 47.37], [8.54, 47.38], [8.53, 47.37]]] };
    useScenarioStore.getState().setSelectedFeature({ geometry, properties: { within_analysis_area: false } });
    render(<InterventionEditor boundary={geometry} />);
    fireEvent.click(screen.getByRole('button', { name: 'Stage Land Cover Reclassification' }));
    expect(screen.getByText(/Select a feature inside the dashed analysis area/)).toBeVisible();
    expect(useScenarioStore.getState().edits).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: /^Solar PV$/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Stage Solar PV Intervention' }));
    expect(screen.getByText(/Select a building inside the dashed analysis area/)).toBeVisible();
    expect(useScenarioStore.getState().edits).toHaveLength(0);
  });
});
