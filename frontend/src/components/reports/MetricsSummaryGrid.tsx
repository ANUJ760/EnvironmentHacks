'use client';

import React from 'react';
import type { Metric } from '@/hooks/useResult';
import {
  EVIDENCE_BADGES,
  formatMetricValue,
  formatDelta,
  formatPercentageDelta,
} from '@/lib/reports';
import { AlertCircle } from 'lucide-react';

interface MetricsSummaryGridProps {
  metrics: Metric[];
}

export function MetricsSummaryGrid({ metrics }: MetricsSummaryGridProps) {
  if (!metrics || metrics.length === 0) {
    return (
      <div className="bg-slate-50 border border-border rounded-xl p-8 text-center text-muted text-xs">
        No simulation metrics reported.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {metrics.map((metric) => {
        const badge = EVIDENCE_BADGES[metric.evidence_class as keyof typeof EVIDENCE_BADGES] || EVIDENCE_BADGES.DETERMINISTIC_CALCULATION;
        const delta = formatDelta(metric.absolute_delta, metric.unit);
        const pctDelta = formatPercentageDelta(metric.percentage_delta);

        return (
          <div
            key={metric.name}
            className="bg-white border border-border rounded-xl p-4 shadow-sm flex flex-col justify-between space-y-3"
          >
            <div>
              <div className="flex items-start justify-between gap-2 mb-2">
                <h4 className="font-bold text-sm text-ink truncate">{metric.name}</h4>
                <span
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border shrink-0 ${badge.className}`}
                  title={badge.description}
                >
                  {badge.label}
                </span>
              </div>

              {/* Baseline vs Scenario */}
              <div className="grid grid-cols-2 gap-2 bg-slate-50 border border-border rounded-lg p-2.5 text-xs">
                <div>
                  <span className="text-[11px] text-muted block">Baseline</span>
                  <span className="font-semibold text-ink">
                    {formatMetricValue(metric.baseline_value, metric.unit)}
                  </span>
                </div>
                <div>
                  <span className="text-[11px] text-muted block">Scenario</span>
                  <span className="font-bold text-ink">
                    {formatMetricValue(metric.scenario_value, metric.unit)}
                  </span>
                </div>
              </div>

              {/* Deltas */}
              <div className="flex items-center justify-between text-xs mt-2 px-1">
                <div>
                  <span className="text-muted block text-[10px]">Absolute Delta</span>
                  <span className={delta.className}>{delta.text}</span>
                </div>
                <div className="text-right">
                  <span className="text-muted block text-[10px]">Relative Change</span>
                  <span className="font-semibold text-ink">{pctDelta}</span>
                </div>
              </div>
            </div>

            {/* Model & Limitations */}
            <div className="pt-2 border-t border-border text-[10px] text-muted space-y-1">
              <div className="flex justify-between">
                <span>Model: {metric.model_id}</span>
                <span className="font-mono">v{metric.model_version}</span>
              </div>
              {metric.limitations && metric.limitations.length > 0 && (
                <div className="flex items-start gap-1 text-slate-500 bg-slate-50 p-1.5 rounded">
                  <AlertCircle className="w-3 h-3 text-amber-500 shrink-0 mt-0.5" />
                  <span className="line-clamp-2">{metric.limitations.join('; ')}</span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
