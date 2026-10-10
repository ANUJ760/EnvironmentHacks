'use client';

import React, { useEffect, useState } from 'react';
import { Info, MapPin, Wind, CloudSun, Layers, Database, X } from 'lucide-react';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useLandcover, useWeather, useAir, useDatasets } from '@/hooks/useCityData';
import { WORLDCOVER_CLASSES } from '@/lib/scenarios';
import { RemovalPanel } from '@/components/map/RemovalPanel';
import { removableKind } from '@/lib/removal';

interface RightInspectorProps {
  cityId?: string;
}

export function RightInspector({ cityId }: RightInspectorProps) {
  const [activeTab, setActiveTab] = useState<'inspect' | 'removal' | 'environment' | 'sources'>('inspect');
  const { selectedFeature, setSelectedFeature } = useScenarioStore();
  useEffect(() => { if (removableKind(selectedFeature)) setActiveTab('removal'); }, [selectedFeature]);

  const { data: landcover } = useLandcover(cityId);
  const { data: weather } = useWeather(cityId);
  const { data: air } = useAir(cityId);
  const { data: datasets } = useDatasets(cityId);

  return (
    <aside
      className="w-80 border-l border-border bg-white flex flex-col shrink-0 overflow-y-auto"
      aria-label="Contextual Inspector"
    >
      <div className="flex border-b border-border bg-slate-50 text-xs font-semibold">
        <button type="button" onClick={() => setActiveTab('removal')} className={`flex-1 py-2.5 px-2 border-b-2 text-[11px] ${activeTab === 'removal' ? 'border-primary text-primary bg-white' : 'border-transparent text-muted'}`}>Impact</button>
        <button
          type="button"
          onClick={() => setActiveTab('inspect')}
          className={`flex-1 py-2.5 px-2 border-b-2 transition-colors flex items-center justify-center gap-1 ${
            activeTab === 'inspect'
              ? 'border-primary text-primary bg-white'
              : 'border-transparent text-muted hover:text-ink'
          }`}
        >
          <Info className="w-3.5 h-3.5" />
          Feature
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('environment')}
          className={`flex-1 py-2.5 px-2 border-b-2 transition-colors flex items-center justify-center gap-1 ${
            activeTab === 'environment'
              ? 'border-primary text-primary bg-white'
              : 'border-transparent text-muted hover:text-ink'
          }`}
        >
          <CloudSun className="w-3.5 h-3.5" />
          Observations
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('sources')}
          className={`flex-1 py-2.5 px-2 border-b-2 transition-colors flex items-center justify-center gap-1 ${
            activeTab === 'sources'
              ? 'border-primary text-primary bg-white'
              : 'border-transparent text-muted hover:text-ink'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          Sources
        </button>
      </div>

      <div className="p-4 flex-1 text-xs space-y-4">
        {activeTab === 'removal' && cityId && <RemovalPanel cityId={cityId} key={JSON.stringify([selectedFeature?.geometry, selectedFeature?.properties?.clicked_location])} />}
        {/* Tab 1: Feature Inspector */}
        {activeTab === 'inspect' && (
          <div>
            {selectedFeature ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-bold text-sm text-ink">
                      {selectedFeature.properties?.name || 'Unnamed Feature'}
                    </h3>
                    <p className="text-muted capitalize">
                      {selectedFeature.properties?.category || selectedFeature.properties?.class || 'Geographic Feature'}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedFeature(null)}
                    className="p-1 text-muted hover:text-ink rounded"
                    title="Deselect feature"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="bg-slate-50 border border-border rounded-lg p-3 space-y-2">
                  <div className="flex justify-between">
                    <span className="text-muted">Feature ID:</span>
                    <span className="font-mono text-[10px] text-ink truncate max-w-[140px]">
                      {selectedFeature.id || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Geometry Type:</span>
                    <span className="font-medium text-ink">{selectedFeature.geometry?.type || 'Unknown'}</span>
                  </div>
                  {selectedFeature.properties?.source && (
                    <div className="flex justify-between">
                      <span className="text-muted">Dataset Source:</span>
                      <span className="font-medium text-ink">{selectedFeature.properties.source}</span>
                    </div>
                  )}
                  {selectedFeature.properties?.area_m2 && (
                    <div className="flex justify-between">
                      <span className="text-muted">Calculated Area:</span>
                      <span className="font-medium text-ink">
                        {(selectedFeature.properties.area_m2 / 10000).toFixed(2)} ha
                      </span>
                    </div>
                  )}
                </div>

                {selectedFeature.properties && (
                  <div>
                    <h4 className="font-semibold text-muted uppercase text-[10px] mb-1.5">Feature Attributes</h4>
                    <div className="bg-slate-50 border border-border rounded-lg p-2 max-h-40 overflow-y-auto space-y-1">
                      {Object.entries(selectedFeature.properties)
                        .filter(([k]) => !['name', 'category', 'class', 'geometry'].includes(k))
                        .map(([k, v]) => (
                          <div key={k} className="flex justify-between text-[11px] py-0.5 border-b border-border/50 last:border-0">
                            <span className="text-muted font-mono">{k}</span>
                            <span className="text-ink truncate max-w-[120px]">{String(v)}</span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-muted">
                <MapPin className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="font-medium text-ink">No feature selected</p>
                <p className="text-[11px] mt-1">
                  Click any polygon, road, or station on the map to inspect its real geographic attributes.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Environmental Observations */}
        {activeTab === 'environment' && (
          <div className="space-y-4">
            {/* Weather */}
            <div>
              <h4 className="font-bold text-ink flex items-center gap-1.5 mb-2">
                <CloudSun className="w-4 h-4 text-amber-500" />
                Weather Conditions
              </h4>
              {weather?.series?.[0] ? (
                <div className="bg-slate-50 border border-border rounded-lg p-3 space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-muted">Temperature:</span>
                    <span className="font-semibold text-ink">{weather.series[0].temperature_c?.toFixed(1)} °C</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Precipitation:</span>
                    <span className="font-medium text-ink">{weather.series[0].rain_mm ?? 0} mm</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Humidity:</span>
                    <span className="font-medium text-ink">{weather.series[0].humidity_pct}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Solar Irradiance (GHI):</span>
                    <span className="font-medium text-ink">{weather.series[0].ghi_w_m2 ?? 'N/A'} W/m²</span>
                  </div>
                  <p className="text-[10px] text-muted pt-1 border-t border-border mt-1">
                    Valid: {new Date(weather.series[0].valid_at).toLocaleString()}
                  </p>
                </div>
              ) : (
                <p className="text-muted italic bg-slate-50 p-3 rounded border border-border">
                  Weather observation unavailable for this city.
                </p>
              )}
            </div>

            {/* Air Quality */}
            <div>
              <h4 className="font-bold text-ink flex items-center gap-1.5 mb-2">
                <Wind className="w-4 h-4 text-cyan-600" />
                Air Quality Stations
              </h4>
              {air?.readings && air.readings.length > 0 ? (
                <div className="space-y-2">
                  {air.readings.map((reading) => (
                    <div key={reading.station_id} className="bg-slate-50 border border-border rounded-lg p-2.5">
                      <div className="flex justify-between font-medium">
                        <span className="truncate text-ink">{reading.station_name}</span>
                        <span className="text-cyan-800 font-bold shrink-0">
                          {reading.value} {reading.unit}
                        </span>
                      </div>
                      <div className="flex justify-between text-[10px] text-muted mt-1">
                        <span>{reading.parameter.toUpperCase()}</span>
                        <span>{new Date(reading.measured_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted italic bg-slate-50 p-3 rounded border border-border">
                  No active air quality stations within study boundary.
                </p>
              )}
            </div>

            {/* Land Cover Summary */}
            <div>
              <h4 className="font-bold text-ink flex items-center gap-1.5 mb-2">
                <Layers className="w-4 h-4 text-emerald-600" />
                WorldCover Distribution (2021)
              </h4>
              {landcover?.class_percentages ? (
                <div className="space-y-1.5 bg-slate-50 border border-border rounded-lg p-2.5">
                  {Object.entries(landcover.class_percentages)
                    .sort(([, a], [, b]) => b - a)
                    .map(([codeStr, pct]) => {
                      const code = parseInt(codeStr, 10);
                      const classInfo = WORLDCOVER_CLASSES[code];
                      return (
                        <div key={code} className="space-y-0.5">
                          <div className="flex justify-between text-[11px]">
                            <span className="text-ink truncate">{classInfo?.name || `Class ${code}`}</span>
                            <span className="font-semibold text-ink">{pct.toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${Math.min(100, pct)}%`,
                                backgroundColor: classInfo?.color || '#2e7d32',
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              ) : (
                <p className="text-muted italic bg-slate-50 p-3 rounded border border-border">
                  Land cover data loading or not ingested.
                </p>
              )}
            </div>
          </div>
        )}

        {/* Tab 3: Data Sources Register */}
        {activeTab === 'sources' && (
          <div>
            <h4 className="font-bold text-ink flex items-center gap-1.5 mb-2">
              <Database className="w-4 h-4 text-primary" />
              Registered Ingestion Revisions
            </h4>
            {datasets && datasets.length > 0 ? (
              <div className="space-y-2">
                {datasets.map((ds) => (
                  <div key={ds.id} className="bg-slate-50 border border-border rounded-lg p-2.5 space-y-1">
                    <div className="flex justify-between font-semibold text-ink">
                      <span className="uppercase text-[11px]">{ds.kind}</span>
                      <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded font-normal">
                        {ds.status}
                      </span>
                    </div>
                    <p className="text-[11px] text-muted">{ds.provider}</p>
                    <div className="text-[10px] text-muted space-y-0.5 pt-1 border-t border-border/50">
                      <div>License: {ds.source_license}</div>
                      <div>Attribution: {ds.attribution}</div>
                      <div className="truncate font-mono">Digest: {ds.sha256.substring(0, 16)}...</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted italic bg-slate-50 p-3 rounded border border-border">
                No dataset revisions registered for this city.
              </p>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
