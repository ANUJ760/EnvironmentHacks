'use client';

import React, { useState } from 'react';
import { Plus, Sliders, Sun, TreePine, AlertTriangle } from 'lucide-react';
import { useScenarioStore } from '@/stores/scenarioStore';
import {
  WORLDCOVER_CLASSES,
  validateLandCoverReclassify,
  validateSolarInstall,
  type ScenarioEdit,
} from '@/lib/scenarios';

interface InterventionEditorProps {
  boundary?: any;
}

export function InterventionEditor({ boundary }: InterventionEditorProps) {
  const [activeForm, setActiveForm] = useState<'reclassify' | 'solar'>('reclassify');
  const { selectedFeature, addEdit } = useScenarioStore();

  // Reclassify Form State
  const [fromClass, setFromClass] = useState<number>(50); // Built-up default
  const [toClass, setToClass] = useState<number>(10); // Tree cover default
  const [fractionPct, setFractionPct] = useState<number>(50); // 50%

  // Solar PV Form State
  const [installedKwp, setInstalledKwp] = useState<number>(250);
  const [performanceRatio, setPerformanceRatio] = useState<number>(0.75);
  const [panelTilt, setPanelTilt] = useState<number>(15);
  const [panelAzimuth, setPanelAzimuth] = useState<number>(0);

  const [formError, setFormError] = useState<string | null>(null);

  // Selected polygon or boundary fallback
  const targetGeometry = selectedFeature?.geometry || boundary;

  const handleAddReclassify = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!targetGeometry) {
      setFormError('Please select a polygon feature on the map to apply this intervention.');
      return;
    }

    const edit: ScenarioEdit = {
      edit_type: 'LAND_COVER_RECLASSIFY',
      polygon_geojson: targetGeometry,
      from_class_code: fromClass,
      to_class_code: toClass,
      fraction: Number((fractionPct / 100).toFixed(2)),
    };

    const validation = validateLandCoverReclassify(edit);
    if (!validation.valid) {
      setFormError(validation.error || 'Invalid reclassification');
      return;
    }

    addEdit(edit);
  };

  const handleAddSolar = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!targetGeometry) {
      setFormError('Please select a footprint on the map to install solar PV.');
      return;
    }

    const edit: ScenarioEdit = {
      edit_type: 'SOLAR_PV_INSTALL',
      footprint_geojson: targetGeometry,
      installed_kwp: Number(installedKwp),
      performance_ratio: Number(performanceRatio),
      panel_tilt_deg: Number(panelTilt),
      panel_azimuth_deg: Number(panelAzimuth),
    };

    const validation = validateSolarInstall(edit);
    if (!validation.valid) {
      setFormError(validation.error || 'Invalid solar installation parameters');
      return;
    }

    addEdit(edit);
  };

  return (
    <div className="bg-white rounded-lg border border-border p-4 shadow-sm text-xs space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-ink flex items-center gap-1.5">
          <Sliders className="w-4 h-4 text-primary" />
          Stage Interventions
        </h3>
        <div className="flex gap-1 bg-slate-100 p-0.5 rounded-md">
          <button
            type="button"
            onClick={() => {
              setActiveForm('reclassify');
              setFormError(null);
            }}
            className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors flex items-center gap-1 ${
              activeForm === 'reclassify' ? 'bg-white text-primary shadow-xs' : 'text-muted hover:text-ink'
            }`}
          >
            <TreePine className="w-3.5 h-3.5" />
            Land Cover
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveForm('solar');
              setFormError(null);
            }}
            className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors flex items-center gap-1 ${
              activeForm === 'solar' ? 'bg-white text-primary shadow-xs' : 'text-muted hover:text-ink'
            }`}
          >
            <Sun className="w-3.5 h-3.5" />
            Solar PV
          </button>
        </div>
      </div>

      {!selectedFeature && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-amber-800 flex items-start gap-1.5 text-[11px]">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-600" />
          <span>
            No map feature selected. Interventions will apply to the active city boundary study area.
          </span>
        </div>
      )}

      {/* Form A: Land Cover Reclassification */}
      {activeForm === 'reclassify' && (
        <form onSubmit={handleAddReclassify} className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-medium text-muted mb-1">Source Class</label>
              <select
                value={fromClass}
                onChange={(e) => setFromClass(Number(e.target.value))}
                className="w-full text-xs px-2 py-1.5 border border-border rounded focus:ring-1 focus:ring-primary"
              >
                {Object.entries(WORLDCOVER_CLASSES).map(([code, item]) => (
                  <option key={code} value={code}>
                    {code}: {item.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-medium text-muted mb-1">Target Class</label>
              <select
                value={toClass}
                onChange={(e) => setToClass(Number(e.target.value))}
                className="w-full text-xs px-2 py-1.5 border border-border rounded focus:ring-1 focus:ring-primary"
              >
                {Object.entries(WORLDCOVER_CLASSES).map(([code, item]) => (
                  <option key={code} value={code}>
                    {code}: {item.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-[11px] font-medium text-muted mb-1">
              <span>Conversion Fraction</span>
              <span className="font-bold text-ink">
                {fractionPct}% ({(fractionPct / 100).toFixed(2)})
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="100"
              value={fractionPct}
              onChange={(e) => setFractionPct(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          {formError && <p className="text-rose-600 text-[11px]">{formError}</p>}

          <button
            type="submit"
            className="w-full flex items-center justify-center gap-1.5 bg-primary hover:bg-primary-hover text-white font-semibold py-1.5 px-3 rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Stage Land Cover Reclassification
          </button>
        </form>
      )}

      {/* Form B: Solar PV Installation */}
      {activeForm === 'solar' && (
        <form onSubmit={handleAddSolar} className="space-y-3">
          <div>
            <label className="block text-[11px] font-medium text-muted mb-1">
              Installed Capacity (kWp)
            </label>
            <input
              type="number"
              min="1"
              max="1000000"
              value={installedKwp}
              onChange={(e) => setInstalledKwp(Number(e.target.value))}
              className="w-full text-xs px-2.5 py-1.5 border border-border rounded focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-[10px] font-medium text-muted mb-1">Perf. Ratio</label>
              <input
                type="number"
                step="0.01"
                min="0.1"
                max="1.0"
                value={performanceRatio}
                onChange={(e) => setPerformanceRatio(Number(e.target.value))}
                className="w-full text-xs px-2 py-1.5 border border-border rounded"
              />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-muted mb-1">Tilt (deg)</label>
              <input
                type="number"
                min="0"
                max="90"
                value={panelTilt}
                onChange={(e) => setPanelTilt(Number(e.target.value))}
                className="w-full text-xs px-2 py-1.5 border border-border rounded"
              />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-muted mb-1">Azimuth (deg)</label>
              <input
                type="number"
                min="-180"
                max="180"
                value={panelAzimuth}
                onChange={(e) => setPanelAzimuth(Number(e.target.value))}
                className="w-full text-xs px-2 py-1.5 border border-border rounded"
              />
            </div>
          </div>

          {formError && <p className="text-rose-600 text-[11px]">{formError}</p>}

          <button
            type="submit"
            className="w-full flex items-center justify-center gap-1.5 bg-primary hover:bg-primary-hover text-white font-semibold py-1.5 px-3 rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Stage Solar PV Intervention
          </button>
        </form>
      )}
    </div>
  );
}
