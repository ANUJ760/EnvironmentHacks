'use client';

import React, { use } from 'react';
import Link from 'next/link';
import { useResult } from '@/hooks/useResult';
import { MetricsSummaryGrid } from '@/components/reports/MetricsSummaryGrid';
import { EvidenceProvenanceCard } from '@/components/reports/EvidenceProvenanceCard';
import { Download, ArrowLeft, ShieldCheck, AlertCircle } from 'lucide-react';
import { getHumanErrorMessage } from '@/lib/api/problem';

export default function ResultReportPage({ params }: { params: Promise<{ resultId: string }> }) {
  const { resultId } = use(params);
  const { data: result, isLoading, isError, error } = useResult(resultId);

  const handleExportJson = () => {
    if (!result) return;
    const jsonStr = JSON.stringify(result, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ecotwin-simulation-result-${result.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-12">
        <div className="text-center space-y-2">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-muted">Retrieving immutable simulation report...</p>
        </div>
      </div>
    );
  }

  if (isError || !result) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
        <AlertCircle className="w-8 h-8 text-rose-600 mb-2" />
        <h2 className="text-lg font-bold text-ink mb-1">Result Report Not Available</h2>
        <p className="text-xs text-muted mb-4">{getHumanErrorMessage(error)}</p>
        <Link href="/explore" className="text-xs font-semibold text-primary">
          Back to Cities Directory
        </Link>
      </div>
    );
  }

  return (
    <div className="flex-1 max-w-6xl w-full mx-auto p-6 md:p-8 space-y-8">
      {/* Report Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-ink">Simulation Outcome Report</h1>
            <span className="text-xs bg-emerald-100 text-emerald-800 font-semibold px-2 py-0.5 rounded-full">
              Immutable Record
            </span>
          </div>
          <p className="text-xs text-muted">
            Result ID: <span className="font-mono text-ink">{result.id}</span> • Job ID:{' '}
            <span className="font-mono text-ink">{result.job_id}</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/explore"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-ink bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Explore Cities
          </Link>
          <button
            type="button"
            onClick={handleExportJson}
            className="flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white text-xs font-semibold py-1.5 px-3.5 rounded-lg shadow-sm transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Export Report (JSON)
          </button>
        </div>
      </div>

      {/* Metrics Summary Grid */}
      <section className="space-y-3">
        <div>
          <h2 className="text-base font-bold text-ink">Simulated Indicators & Baselines</h2>
          <p className="text-xs text-muted">
            All metrics are labeled with their authoritative evidence class. Unavailable models remain explicitly reported as unsimulated.
          </p>
        </div>
        <MetricsSummaryGrid metrics={result.metrics} />
      </section>

      {/* Provenance Card */}
      <section className="space-y-3">
        <EvidenceProvenanceCard result={result} />
      </section>
    </div>
  );
}
