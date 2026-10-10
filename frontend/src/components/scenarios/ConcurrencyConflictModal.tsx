'use client';

import React from 'react';
import { AlertCircle, Download, RefreshCw } from 'lucide-react';
import { useScenarioStore } from '@/stores/scenarioStore';

export function ConcurrencyConflictModal() {
  const { conflictData, setConflict, resetScenario } = useScenarioStore();

  if (!conflictData) return null;

  const exportDraft = () => {
    const jsonStr = JSON.stringify(conflictData.draftEdits, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `scenario-draft-backup-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleReload = () => {
    setConflict(null);
    window.location.reload();
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="conflict-title"
    >
      <div className="bg-white rounded-xl max-w-lg w-full border border-border shadow-xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-amber-700">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <h2 id="conflict-title" className="text-base font-bold text-ink">
            Concurrency Conflict (Version Mismatch)
          </h2>
        </div>

        <p className="text-xs text-muted">
          Another session or operator modified this scenario since you loaded it. To prevent overwriting work, the server rejected the update (HTTP 412 Precondition Failed).
        </p>

        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="bg-slate-50 border border-border rounded-lg p-3">
            <h4 className="font-semibold text-ink mb-1">Your Local Draft</h4>
            <p className="text-muted">{conflictData.draftEdits.length} staged edits</p>
          </div>
          <div className="bg-slate-50 border border-border rounded-lg p-3">
            <h4 className="font-semibold text-ink mb-1">Server Saved Revision</h4>
            <p className="text-muted">{conflictData.serverEdits.length} edits currently saved</p>
          </div>
        </div>

        <div className="flex justify-between items-center pt-2">
          <button
            type="button"
            onClick={exportDraft}
            className="flex items-center gap-1.5 text-xs text-primary hover:text-primary-hover font-semibold p-1"
          >
            <Download className="w-3.5 h-3.5" />
            Export Draft Backup (JSON)
          </button>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setConflict(null)}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-ink rounded-lg hover:bg-slate-100 transition-colors"
            >
              Keep Editing Locally
            </button>
            <button
              type="button"
              onClick={handleReload}
              className="px-4 py-1.5 text-xs font-semibold bg-primary hover:bg-primary-hover text-white rounded-lg transition-colors flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reload Latest Server State
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
