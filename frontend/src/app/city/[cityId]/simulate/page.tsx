'use client';

import React, { useState, use } from 'react';
import Link from 'next/link';
import { useCity } from '@/hooks/useCities';
import { useCityFeatures } from '@/hooks/useCityData';
import { PixiMap } from '@/components/map/PixiMap';
import { LeftRail } from '@/components/shell/LeftRail';
import { InterventionEditor } from '@/components/scenarios/InterventionEditor';
import { ScenarioEditsList } from '@/components/scenarios/ScenarioEditsList';
import { CreateScenarioModal } from '@/components/scenarios/CreateScenarioModal';
import { RunSimulationDialog } from '@/components/scenarios/RunSimulationDialog';
import { JobProgressPanel } from '@/components/scenarios/JobProgressPanel';
import { ConcurrencyConflictModal } from '@/components/scenarios/ConcurrencyConflictModal';
import { useScenarioStore } from '@/stores/scenarioStore';
import { computeBBoxFromGeometry, formatBBox } from '@/lib/geo';
import { Plus, Play, Sparkles, AlertCircle, ArrowLeft, Layers, Sliders } from 'lucide-react';

export default function ScenarioLabPage({ params }: { params: Promise<{ cityId: string }> }) {
  const { cityId } = use(params);
  const { data: city, isLoading, isError } = useCity(cityId);

  const [currentBbox, setCurrentBbox] = useState<string>('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isRunModalOpen, setIsRunModalOpen] = useState(false);

  const { scenarioId, scenarioName, snapshotId, edits, state } = useScenarioStore();

  const defaultBbox = city?.boundary ? formatBBox(computeBBoxFromGeometry(city.boundary)) : '';
  const effectiveBbox = currentBbox || defaultBbox;

  const { data: featureCollection } = useCityFeatures(cityId, effectiveBbox);
  const features = featureCollection?.features || [];

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="text-center space-y-2">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-muted">Initializing Scenario Lab...</p>
        </div>
      </div>
    );
  }

  if (isError || !city) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <AlertCircle className="w-8 h-8 text-rose-600 mb-2" />
        <h2 className="text-lg font-bold text-ink mb-1">City Not Found</h2>
        <Link
          href="/explore"
          className="flex items-center gap-1.5 bg-primary text-white text-xs font-semibold px-4 py-2 rounded-lg mt-4"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to City Directory
        </Link>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Top Scenario Control Bar */}
      <div className="h-12 bg-white border-b border-border px-4 md:px-6 flex items-center justify-between text-xs shrink-0 z-20">
        <div className="flex items-center gap-3">
          <Link
            href={`/city/${cityId}`}
            className="text-muted hover:text-ink flex items-center gap-1 font-medium"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Back to Viewer</span>
          </Link>
          <div className="h-4 w-px bg-border" />
          <div>
            <span className="text-muted">Scenario: </span>
            <span className="font-bold text-ink">
              {scenarioName || 'No Scenario Active (Baseline View)'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!scenarioId ? (
            <button
              type="button"
              onClick={() => setIsCreateModalOpen(true)}
              className="flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white font-semibold py-1.5 px-3 rounded-lg transition-colors shadow-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Scenario</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setIsRunModalOpen(true)}
              disabled={edits.length === 0}
              className="flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white font-semibold py-1.5 px-4 rounded-lg transition-colors shadow-xs disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run Simulation</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Layer Rail */}
        <LeftRail cityId={cityId} cityName={city.display_name} isSimulatePage={true} />

        {/* Center Canvas Viewport */}
        <div className="flex-1 flex flex-col relative overflow-hidden">
          <PixiMap
            cityId={cityId}
            boundary={city.boundary}
            features={features}
            onBBoxChange={(bbox) => setCurrentBbox(bbox)}
          />
        </div>

        {/* Right Scenario Editor Rail */}
        <div className="w-96 border-l border-border bg-slate-50 flex flex-col shrink-0 overflow-y-auto p-4 space-y-4">
          {/* Active Job Progress */}
          <JobProgressPanel />

          {/* Staging Controls (Enabled only if scenario created) */}
          {scenarioId ? (
            <>
              <InterventionEditor boundary={city.boundary} />
              <ScenarioEditsList />
            </>
          ) : (
            <div className="bg-white border border-border rounded-xl p-6 text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-primary-light text-primary flex items-center justify-center mx-auto">
                <Sliders className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-sm text-ink">Create a Scenario to Edit</h3>
              <p className="text-xs text-muted leading-relaxed">
                Create a scenario to start testing interventions like land cover reclassification and solar PV installations against the city baseline.
              </p>
              <button
                type="button"
                onClick={() => setIsCreateModalOpen(true)}
                className="w-full flex items-center justify-center gap-1.5 bg-primary hover:bg-primary-hover text-white font-semibold py-2 px-3 rounded-lg text-xs transition-colors shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                Create New Scenario
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <CreateScenarioModal
        cityId={cityId}
        snapshotId={city.active_snapshot_id || ''}
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
      />

      <RunSimulationDialog
        cityId={cityId}
        isOpen={isRunModalOpen}
        onClose={() => setIsRunModalOpen(false)}
      />

      <ConcurrencyConflictModal />
    </div>
  );
}
