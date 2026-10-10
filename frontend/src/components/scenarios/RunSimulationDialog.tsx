'use client';

import React, { useState } from 'react';
import { Play, Check, AlertCircle } from 'lucide-react';
import { useModels } from '@/hooks/useModels';
import { useSimulateScenario } from '@/hooks/useScenario';
import { getHumanErrorMessage } from '@/lib/api/problem';

interface RunSimulationDialogProps {
  cityId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function RunSimulationDialog({
  cityId,
  isOpen,
  onClose,
}: RunSimulationDialogProps) {
  const { data: modelsData, isLoading: modelsLoading } = useModels(cityId);
  const simulateMutation = useSimulateScenario();

  // Selected models
  const [selectedModels, setSelectedModels] = useState<string[]>(['landcover_summary', 'runoff_screen']);
  const [rainfallMm, setRainfallMm] = useState<number>(25);

  if (!isOpen) return null;

  const toggleModel = (id: string) => {
    if (selectedModels.includes(id)) {
      if (selectedModels.length > 1) {
        setSelectedModels(selectedModels.filter((m) => m !== id));
      }
    } else {
      setSelectedModels([...selectedModels, id]);
    }
  };

  const handleRun = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedModels.length === 0) return;

    simulateMutation.mutate(
      {
        requested_models: selectedModels,
        event_rainfall_mm: selectedModels.includes('runoff_screen') ? Number(rainfallMm) : null,
      },
      {
        onSuccess: () => {
          onClose();
        },
      }
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="simulation-title"
    >
      <div className="bg-white rounded-xl max-w-lg w-full border border-border shadow-xl p-6">
        <h2 id="simulation-title" className="text-base font-bold text-ink mb-1">
          Configure & Run Simulation
        </h2>
        <p className="text-xs text-muted mb-4">
          Select runnable scientific models. Only models with valid ingested inputs can be requested.
        </p>

        <form onSubmit={handleRun} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-ink mb-2">Available Models</label>
            {modelsLoading ? (
              <p className="text-xs text-muted">Loading model registry...</p>
            ) : (
              <div className="space-y-2">
                {modelsData?.models?.map((model) => {
                  const isChecked = selectedModels.includes(model.id);
                  return (
                    <div
                      key={model.id}
                      onClick={() => model.available && toggleModel(model.id)}
                      className={`flex items-start justify-between p-3 rounded-lg border text-xs cursor-pointer transition-colors ${
                        !model.available
                          ? 'opacity-50 bg-slate-100 border-slate-200 cursor-not-allowed'
                          : isChecked
                          ? 'bg-primary-light border-primary text-ink'
                          : 'bg-white border-border hover:bg-slate-50'
                      }`}
                    >
                      <div>
                        <div className="flex items-center gap-1.5 font-bold">
                          <span>{model.id}</span>
                          <span className="text-[10px] text-muted font-normal font-mono">
                            v{model.version}
                          </span>
                        </div>
                        <p className="text-[11px] text-muted mt-0.5">
                          Evidence: {model.evidence_class}
                        </p>
                        {!model.available && (
                          <p className="text-[10px] text-rose-600 mt-1">
                            Missing inputs: {model.required_inputs.join(', ')}
                          </p>
                        )}
                      </div>

                      <div
                        className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 mt-0.5 ${
                          isChecked ? 'bg-primary border-primary text-white' : 'border-slate-300'
                        }`}
                      >
                        {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Rainfall parameter for runoff screening */}
          {selectedModels.includes('runoff_screen') && (
            <div className="bg-slate-50 border border-border rounded-lg p-3 space-y-1">
              <label className="block text-xs font-semibold text-ink">
                Runoff Event Rainfall (mm)
              </label>
              <input
                type="number"
                min="1"
                max="1000"
                value={rainfallMm}
                onChange={(e) => setRainfallMm(Number(e.target.value))}
                className="w-full text-xs px-2.5 py-1.5 border border-border rounded bg-white"
              />
              <p className="text-[10px] text-muted">
                Runoff screening estimates total water volume generated based on composite runoff coefficients.
              </p>
            </div>
          )}

          {/* Explicit Unavailable Models Note */}
          {modelsData?.unavailable_models && modelsData.unavailable_models.length > 0 && (
            <div className="bg-slate-50 border border-border rounded-lg p-2.5 text-[11px] text-muted">
              <div className="font-semibold text-ink flex items-center gap-1 mb-1">
                <AlertCircle className="w-3.5 h-3.5 text-slate-400" />
                Scientifically Unavailable Capabilities
              </div>
              <p>
                Urban microclimate temperature (heat_delta), street PM2.5 dispersion (pm25_delta), and biodiversity mortality cannot be simulated without verified physics and local sensor calibration.
              </p>
            </div>
          )}

          {simulateMutation.isError && (
            <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700">
              {getHumanErrorMessage(simulateMutation.error)}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={simulateMutation.isPending}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-ink rounded-lg hover:bg-slate-100 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={simulateMutation.isPending || selectedModels.length === 0}
              className="px-4 py-1.5 text-xs font-semibold bg-primary hover:bg-primary-hover text-white rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              {simulateMutation.isPending ? 'Queuing Simulation...' : 'Submit Simulation Job'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
