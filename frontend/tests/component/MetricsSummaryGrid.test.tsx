import React from 'react';
import { describe, it, expect } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { MetricsSummaryGrid } from '@/components/reports/MetricsSummaryGrid';
import type { Metric } from '@/hooks/useResult';

describe('MetricsSummaryGrid Component', () => {
  const mockMetrics: Metric[] = [
    {
      name: 'Runoff Volume',
      baseline_value: 12500,
      scenario_value: 9800,
      absolute_delta: -2700,
      percentage_delta: -21.6,
      unit: 'm³/event',
      spatial_scope: 'city_boundary',
      evidence_class: 'SCREENING_ESTIMATE',
      model_id: 'runoff_screen',
      model_version: 'runoff-coeff-v1',
      source_revision_ids: ['rev-1'],
      parameter_digest: 'digest-1',
      limitations: ['Coarse composite rational method', 'Uniform rainfall assumption'],
    },
    {
      name: 'Canopy Area',
      baseline_value: 450,
      scenario_value: 520,
      absolute_delta: 70,
      percentage_delta: 15.55,
      unit: 'ha',
      spatial_scope: 'city_boundary',
      evidence_class: 'DETERMINISTIC_CALCULATION',
      model_id: 'landcover_summary',
      model_version: 'landcover-v1',
      source_revision_ids: ['rev-2'],
      parameter_digest: 'digest-2',
      limitations: [],
    },
  ];

  it('renders metric cards with baseline, scenario, and deltas', () => {
    render(<MetricsSummaryGrid metrics={mockMetrics} />);

    expect(screen.getByText('Runoff Volume')).toBeInTheDocument();
    expect(screen.getByText('12,500 m³/event')).toBeInTheDocument();
    expect(screen.getByText('9,800 m³/event')).toBeInTheDocument();
    expect(screen.getByText('-2,700 m³/event')).toBeInTheDocument();

    expect(screen.getByText('Canopy Area')).toBeInTheDocument();
    expect(screen.getByText('+70 ha')).toBeInTheDocument();
  });

  it('renders correct evidence class badges', () => {
    render(<MetricsSummaryGrid metrics={mockMetrics} />);

    expect(screen.getByText('Screening Estimate')).toBeInTheDocument();
    expect(screen.getByText('Calculated')).toBeInTheDocument();
  });

  it('renders empty message when no metrics available', () => {
    render(<MetricsSummaryGrid metrics={[]} />);
    expect(screen.getByText('No simulation metrics reported.')).toBeInTheDocument();
  });
});
