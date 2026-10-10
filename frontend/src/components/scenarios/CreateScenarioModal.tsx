'use client';

import React, { useState } from 'react';
import { useCreateScenario } from '@/hooks/useScenario';
import { getHumanErrorMessage } from '@/lib/api/problem';

interface CreateScenarioModalProps {
  cityId: string;
  snapshotId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function CreateScenarioModal({
  cityId,
  snapshotId,
  isOpen,
  onClose,
}: CreateScenarioModalProps) {
  const [name, setName] = useState('');
  const createMutation = useCreateScenario();

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    createMutation.mutate(
      { cityId, snapshotId, name: name.trim() },
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
      aria-labelledby="modal-title"
    >
      <div className="bg-white rounded-xl max-w-md w-full border border-border shadow-xl p-6">
        <h2 id="modal-title" className="text-base font-bold text-ink mb-1">
          Create New Scenario
        </h2>
        <p className="text-xs text-muted mb-4">
          Scenarios bind to an immutable city dataset snapshot. All subsequent interventions and simulation runs are isolated.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="scenario-name" className="block text-xs font-semibold text-ink mb-1">
              Scenario Name
            </label>
            <input
              id="scenario-name"
              type="text"
              required
              maxLength={200}
              placeholder="e.g., Downtown Canopy Expansion & Solar 2026"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full text-xs px-3 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="bg-slate-50 border border-border rounded-lg p-2.5 text-[11px] text-muted space-y-1">
            <div className="flex justify-between">
              <span>City ID:</span>
              <span className="font-mono text-ink truncate max-w-[200px]">{cityId}</span>
            </div>
            <div className="flex justify-between">
              <span>Active Snapshot:</span>
              <span className="font-mono text-ink truncate max-w-[200px]">{snapshotId}</span>
            </div>
          </div>

          {createMutation.isError && (
            <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700">
              {getHumanErrorMessage(createMutation.error)}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={createMutation.isPending}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-ink rounded-lg hover:bg-slate-100 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || !name.trim()}
              className="px-4 py-1.5 text-xs font-semibold bg-primary hover:bg-primary-hover text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {createMutation.isPending ? 'Creating...' : 'Create Scenario'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
