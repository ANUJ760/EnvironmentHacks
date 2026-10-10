import { describe, it, expect } from 'vitest';
import {
  formatMetricValue,
  formatDelta,
  formatPercentageDelta,
  EVIDENCE_BADGES,
} from '@/lib/reports';

describe('Reports Formatting Utilities', () => {
  it('formats values and units correctly', () => {
    expect(formatMetricValue(1234.56, 'm²')).toBe('1,234.56 m²');
    expect(formatMetricValue(1500000, 'm³')).toBe('1.5 M m³');
    expect(formatMetricValue(0, '%')).toBe('0 %');
  });

  it('keeps null and undefined values as N/A, never 0', () => {
    expect(formatMetricValue(null)).toBe('N/A');
    expect(formatMetricValue(undefined)).toBe('N/A');
    expect(formatMetricValue(NaN)).toBe('N/A');
  });

  it('formats delta numbers with explicit +/- sign', () => {
    const positive = formatDelta(45.2, 'ha');
    expect(positive.text).toBe('+45.2 ha');
    expect(positive.className).toContain('text-emerald-700');

    const negative = formatDelta(-12.8, 'ha');
    expect(negative.text).toBe('-12.8 ha');

    const zero = formatDelta(0, 'kWh');
    expect(zero.text).toBe('0 kWh');
  });

  it('formats percentage deltas', () => {
    expect(formatPercentageDelta(15.234)).toBe('+15.23%');
    expect(formatPercentageDelta(-5.5)).toBe('-5.50%');
    expect(formatPercentageDelta(null)).toBe('N/A');
  });

  it('contains badge definitions for all six evidence tiers', () => {
    const expectedTiers = [
      'OBSERVED',
      'DETERMINISTIC_CALCULATION',
      'SCREENING_ESTIMATE',
      'CALIBRATED_PREDICTION',
      'ASSUMED_INPUT',
      'UNAVAILABLE',
    ];
    for (const tier of expectedTiers) {
      expect(EVIDENCE_BADGES[tier as keyof typeof EVIDENCE_BADGES]).toBeDefined();
    }
  });
});
