'use client';

import React from 'react';
import Link from 'next/link';
import { Loader2, CheckCircle2, XCircle, AlertCircle, ExternalLink, Ban } from 'lucide-react';
import { useJobPolling, useCancelJob } from '@/hooks/useJobPolling';
import { useScenarioStore } from '@/stores/scenarioStore';

export function JobProgressPanel() {
  const { activeJobId, setActiveJobId } = useScenarioStore();
  const { data: job, isLoading } = useJobPolling(activeJobId);
  const cancelMutation = useCancelJob();

  if (!activeJobId) return null;

  const state = (job?.state || 'QUEUED').toUpperCase();
  const isTerminal = ['SUCCEEDED', 'COMPLETED', 'FAILED', 'CANCELED'].includes(state);

  return (
    <div
      className="bg-white rounded-lg border border-border p-4 shadow-sm text-xs space-y-3"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {!isTerminal ? (
            <Loader2 className="w-4 h-4 text-primary animate-spin" />
          ) : state === 'SUCCEEDED' || state === 'COMPLETED' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          ) : state === 'CANCELED' ? (
            <AlertCircle className="w-4 h-4 text-amber-600" />
          ) : (
            <XCircle className="w-4 h-4 text-rose-600" />
          )}
          <span className="font-bold text-ink">
            Simulation Job: <span className="font-mono text-[11px] font-normal">{activeJobId.substring(0, 8)}...</span>
          </span>
        </div>

        <span
          className={`px-2 py-0.5 rounded-full font-semibold text-[10px] uppercase ${
            state === 'SUCCEEDED' || state === 'COMPLETED'
              ? 'bg-emerald-100 text-emerald-800'
              : state === 'FAILED'
              ? 'bg-rose-100 text-rose-800'
              : state === 'CANCELED'
              ? 'bg-amber-100 text-amber-800'
              : 'bg-primary-light text-primary'
          }`}
        >
          {state}
        </span>
      </div>

      {/* Progress Bar */}
      <div>
        <div className="flex justify-between text-[11px] text-muted mb-1">
          <span>Progress</span>
          <span className="font-semibold text-ink">{job?.progress_pct ?? 0}%</span>
        </div>
        <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden border border-slate-200">
          <div
            className={`h-full transition-all duration-300 rounded-full ${
              state === 'FAILED' ? 'bg-rose-500' : 'bg-primary'
            }`}
            style={{ width: `${Math.min(100, Math.max(5, job?.progress_pct ?? 0))}%` }}
          />
        </div>
      </div>

      {job?.error_message && (
        <div className="p-2.5 rounded bg-rose-50 border border-rose-200 text-rose-700 text-[11px]">
          <p className="font-semibold">{job.error_code || 'Simulation Error'}</p>
          <p className="mt-0.5">{job.error_message}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-1">
        {!isTerminal ? (
          <button
            type="button"
            onClick={() => cancelMutation.mutate(activeJobId)}
            disabled={cancelMutation.isPending}
            className="text-rose-600 hover:text-rose-700 font-medium flex items-center gap-1 p-1 rounded"
          >
            <Ban className="w-3.5 h-3.5" />
            {cancelMutation.isPending ? 'Requesting cancel...' : 'Cancel Job'}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setActiveJobId(null)}
            className="text-muted hover:text-ink font-medium"
          >
            Dismiss
          </button>
        )}

        {(state === 'SUCCEEDED' || state === 'COMPLETED') && job?.result_id && (
          <Link
            href={`/results/${job.result_id}`}
            className="flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white font-semibold py-1.5 px-3 rounded-lg shadow-sm transition-colors"
          >
            <span>View Full Report</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        )}
      </div>
    </div>
  );
}
