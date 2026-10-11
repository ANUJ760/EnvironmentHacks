export type EvidenceClass =
  | 'OBSERVED'
  | 'DETERMINISTIC_CALCULATION'
  | 'SCREENING_ESTIMATE'
  | 'CALIBRATED_PREDICTION'
  | 'ASSUMED_INPUT'
  | 'UNAVAILABLE';

export interface EvidenceBadgeConfig {
  label: string;
  className: string;
  description: string;
}

export const EVIDENCE_BADGES: Record<EvidenceClass, EvidenceBadgeConfig> = {
  OBSERVED: {
    label: 'Measured / Recorded',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    description: 'Direct empirical measurement or recorded observation. Baseline context, not a causal prediction.',
  },
  DETERMINISTIC_CALCULATION: {
    label: 'Calculated',
    className: 'bg-blue-100 text-blue-800 border-blue-300',
    description: 'Exact physical or mathematical formula applied deterministically from input data.',
  },
  SCREENING_ESTIMATE: {
    label: 'Screening Estimate',
    className: 'bg-amber-100 text-amber-800 border-amber-300',
    description: 'Coarse initial approximation for screening purposes; not a detailed calibrated simulation.',
  },
  CALIBRATED_PREDICTION: {
    label: 'Calibrated Model',
    className: 'bg-purple-100 text-purple-800 border-purple-300',
    description: 'Statistical or physical model calibrated against historical local observations.',
  },
  ASSUMED_INPUT: {
    label: 'Analyst Assumption',
    className: 'bg-slate-100 text-slate-800 border-slate-300',
    description: 'User-specified input or default parameter assumption.',
  },
  UNAVAILABLE: {
    label: 'Not Simulated',
    className: 'bg-rose-100 text-rose-800 border-rose-300',
    description: 'Scientific model or required input data unavailable for this study area.',
  },
};

export function formatMetricValue(val: number | null | undefined, unit?: string): string {
  if (val === null || val === undefined) return 'N/A';
  if (isNaN(val)) return 'N/A';

  let formatted: string;
  const abs = Math.abs(val);

  if (abs >= 1_000_000) {
    formatted = (val / 1_000_000).toLocaleString('en-US', { maximumFractionDigits: 2 }) + ' M';
  } else if (abs >= 10_000) {
    formatted = val.toLocaleString('en-US', { maximumFractionDigits: 1 });
  } else if (abs >= 10) {
    formatted = val.toLocaleString('en-US', { maximumFractionDigits: 2 });
  } else if (abs > 0) {
    formatted = val.toLocaleString('en-US', { maximumFractionDigits: 3 });
  } else {
    formatted = '0';
  }

  return unit ? `${formatted} ${unit}` : formatted;
}

export function formatDelta(
  val: number | null | undefined,
  unit?: string,
  invertSentiment: boolean = false
): { text: string; className: string } {
  if (val === null || val === undefined || isNaN(val)) {
    return { text: 'N/A', className: 'text-slate-500' };
  }

  const sign = val > 0 ? '+' : '';
  const text = `${sign}${formatMetricValue(val, unit)}`;

  if (val === 0) {
    return { text, className: 'text-slate-600' };
  }

  const isPositiveDirection = val > 0;
  const isGood = invertSentiment ? !isPositiveDirection : isPositiveDirection;

  return {
    text,
    className: isGood ? 'text-emerald-700 font-semibold' : 'text-amber-700 font-semibold',
  };
}

export function formatPercentageDelta(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return 'N/A';
  const sign = val > 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}%`;
}
