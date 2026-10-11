'use client';

import React from 'react';
import { Trash2, Undo2, Redo2, Save, CheckCircle, Clock } from 'lucide-react';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useSaveEdits } from '@/hooks/useScenario';
import { WORLDCOVER_CLASSES } from '@/lib/scenarios';
import { getHumanErrorMessage } from '@/lib/api/problem';

export function ScenarioEditsList() {
  const { edits, undoStack, redoStack, removeEdit, undo, redo, state } = useScenarioStore();
  const saveMutation = useSaveEdits();

  return (
    <div className="bg-white rounded-lg border border-border p-4 shadow-sm text-xs space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-bold text-ink">Staged Edits ({edits.length})</h3>
          {state === 'saved_revision' && (
            <span className="flex items-center gap-1 text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">
              <CheckCircle className="w-3 h-3" />
              Saved
            </span>
          )}
          {state === 'editing_unsaved' && (
            <span className="flex items-center gap-1 text-[10px] text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded font-medium">
              <Clock className="w-3 h-3" />
              Unsaved
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={undo}
            disabled={undoStack.length === 0}
            className="p-1 text-slate-600 hover:text-ink disabled:opacity-30 rounded hover:bg-slate-100 transition-colors"
            title="Undo staged edit"
            aria-label="Undo staged edit"
          >
            <Undo2 className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={redo}
            disabled={redoStack.length === 0}
            className="p-1 text-slate-600 hover:text-ink disabled:opacity-30 rounded hover:bg-slate-100 transition-colors"
            title="Redo staged edit"
            aria-label="Redo staged edit"
          >
            <Redo2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {edits.length === 0 ? (
        <p className="text-muted text-center py-4 bg-slate-50 rounded border border-border">
          No interventions staged. Use the form above to add an edit.
        </p>
      ) : (
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {edits.map((edit, idx) => {
            if (edit.edit_type === 'LAND_COVER_RECLASSIFY') {
              const fromName = WORLDCOVER_CLASSES[edit.from_class_code]?.name || `Class ${edit.from_class_code}`;
              const toName = WORLDCOVER_CLASSES[edit.to_class_code]?.name || `Class ${edit.to_class_code}`;
              return (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2.5 bg-slate-50 border border-border rounded-lg"
                >
                  <div className="truncate pr-2">
                    <p className="font-semibold text-ink truncate">
                      Reclassify: {fromName} → {toName}
                    </p>
                    <p className="text-[11px] text-muted">
                      Fraction: {(edit.fraction * 100).toFixed(0)}%
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeEdit(idx)}
                    className="text-slate-400 hover:text-rose-600 p-1 rounded transition-colors"
                    title="Remove edit"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            }

            if (edit.edit_type === 'SOLAR_PV_INSTALL') {
              return (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2.5 bg-slate-50 border border-border rounded-lg"
                >
                  <div className="truncate pr-2">
                    <p className="font-semibold text-ink truncate">
                      Solar PV: {edit.installed_kwp} kWp
                    </p>
                    <p className="text-[11px] text-muted">
                      PR: {edit.performance_ratio ?? 0.75} | Tilt: {edit.panel_tilt_deg ?? 0}°
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeEdit(idx)}
                    className="text-slate-400 hover:text-rose-600 p-1 rounded transition-colors"
                    title="Remove edit"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            }

            return null;
          })}
        </div>
      )}

      {saveMutation.isError && (
        <div className="p-2 rounded bg-rose-50 border border-rose-200 text-rose-700 text-[11px]">
          {getHumanErrorMessage(saveMutation.error)}
        </div>
      )}

      <button
        type="button"
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending || state === 'saved_revision' || edits.length === 0}
        className="w-full flex items-center justify-center gap-1.5 bg-forest hover:bg-forest-dark text-white font-semibold py-2 px-3 rounded-lg transition-colors disabled:opacity-50"
      >
        <Save className="w-3.5 h-3.5" />
        {saveMutation.isPending ? 'Saving Revisions (If-Match)...' : 'Save Scenario Edits'}
      </button>
    </div>
  );
}
