'use client';

import React, { use } from 'react';
import Link from 'next/link';
import { useScenario, useScenarioReports } from '@/hooks/useScenario';
import { WORLDCOVER_CLASSES } from '@/lib/scenarios';
import { ArrowLeft, Play, FileText, CheckCircle, Clock, ExternalLink } from 'lucide-react';

export default function ScenarioReviewPage({ params }: { params: Promise<{ scenarioId: string }> }) {
  const { scenarioId } = use(params);
  const { data, isLoading, isError } = useScenario(scenarioId);
  const { data: reports } = useScenarioReports(scenarioId);

  const scenario = data?.scenario;

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isError || !scenario) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
        <h2 className="text-lg font-bold text-ink mb-1">Scenario Not Found</h2>
        <p className="text-xs text-muted mb-4">You may not have permission to view this scenario.</p>
        <Link href="/explore" className="text-xs font-semibold text-primary">
          Back to Cities
        </Link>
      </div>
    );
  }

  return (
    <div className="flex-1 max-w-4xl w-full mx-auto p-6 md:p-8 space-y-6">
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-ink">{scenario.name}</h1>
            <span className="text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-mono">
              v{scenario.version}
            </span>
          </div>
          <p className="text-xs text-muted font-mono">Snapshot: {scenario.snapshot_id}</p>
        </div>

        <Link
          href="/explore"
          className="text-xs font-semibold text-muted hover:text-ink flex items-center gap-1"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Directory
        </Link>
      </div>

      {/* Scenario Edits */}
      <div className="bg-white border border-border rounded-xl p-6 shadow-sm space-y-4">
        <h2 className="font-bold text-sm text-ink">
          Recorded Scenario Edits ({scenario.edits?.length || 0})
        </h2>

        {(!scenario.edits || scenario.edits.length === 0) ? (
          <p className="text-xs text-muted">No edits recorded for this scenario.</p>
        ) : (
          <div className="divide-y divide-border text-xs">
            {scenario.edits.map((edit: any, idx: number) => (
              <div key={idx} className="py-2.5 flex items-center justify-between">
                <div>
                  <span className="font-semibold text-ink">{edit.edit_type}</span>
                  {edit.edit_type === 'LAND_COVER_RECLASSIFY' && (
                    <span className="text-muted ml-2">
                      {WORLDCOVER_CLASSES[edit.from_class_code]?.name} → {WORLDCOVER_CLASSES[edit.to_class_code]?.name} ({(edit.fraction * 100).toFixed(0)}%)
                    </span>
                  )}
                  {edit.edit_type === 'SOLAR_PV_INSTALL' && (
                    <span className="text-muted ml-2">
                      {edit.installed_kwp} kWp (PR: {edit.performance_ratio || 0.75})
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Historical Simulation Reports */}
      <div className="bg-white border border-border rounded-xl p-6 shadow-sm space-y-4">
        <h2 className="font-bold text-sm text-ink flex items-center gap-2">
          <FileText className="w-4 h-4 text-primary" />
          Simulation Run History
        </h2>

        {(!reports || reports.length === 0) ? (
          <p className="text-xs text-muted">No simulation runs executed yet for this scenario.</p>
        ) : (
          <div className="space-y-2">
            {reports.map((rep: any) => (
              <div
                key={rep.id}
                className="flex items-center justify-between p-3 bg-slate-50 border border-border rounded-lg text-xs"
              >
                <div>
                  <span className="font-semibold text-ink">Result #{rep.id.substring(0, 8)}</span>
                  <p className="text-[11px] text-muted">
                    Created: {new Date(rep.created_at).toLocaleString()}
                  </p>
                </div>
                <Link
                  href={`/results/${rep.id}`}
                  className="flex items-center gap-1 text-primary hover:text-forest font-semibold"
                >
                  <span>View Report</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
