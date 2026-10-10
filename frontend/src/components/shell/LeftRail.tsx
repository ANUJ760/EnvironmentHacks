'use client';

import React from 'react';
import Link from 'next/link';
import { Layers, Eye, EyeOff, TreePine, Building2, Droplets, Car, Trash2, Wind, CloudSun, Play } from 'lucide-react';
import { useLayerStore } from '@/stores/layerStore';

interface LeftRailProps {
  cityId?: string;
  cityName?: string;
  isSimulatePage?: boolean;
}

export function LeftRail({ cityId, cityName, isSimulatePage = false }: LeftRailProps) {
  const { buildings, roads, parks, water, waste, air, weather, landcover, toggleLayer } = useLayerStore();

  const layerItems = [
    { id: 'buildings', label: 'Buildings (OSM)', icon: Building2, active: buildings },
    { id: 'roads', label: 'Road Network', icon: Car, active: roads },
    { id: 'parks', label: 'Parks & Canopy', icon: TreePine, active: parks },
    { id: 'water', label: 'Water Bodies', icon: Droplets, active: water },
    { id: 'landcover', label: 'Land Cover (WorldCover)', icon: Layers, active: landcover },
    { id: 'air', label: 'Air Stations (OpenAQ)', icon: Wind, active: air },
    { id: 'weather', label: 'Weather Forecast', icon: CloudSun, active: weather },
    { id: 'waste', label: 'Waste Facilities', icon: Trash2, active: waste },
  ] as const;

  return (
    <aside
      className="w-72 border-r border-border bg-white flex flex-col shrink-0 overflow-y-auto"
      aria-label="Layer and intervention controls"
    >
      <div className="p-4 border-b border-border">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Study Area</h2>
        <p className="text-base font-bold text-ink truncate mt-0.5">{cityName || 'Overview'}</p>

        {cityId && !isSimulatePage && (
          <Link
            href={`/city/${cityId}/simulate`}
            className="mt-3 w-full flex items-center justify-center gap-2 bg-primary hover:bg-primary-hover text-white text-xs font-semibold py-2 px-3 rounded-lg shadow-sm transition-colors"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            Launch Scenario Lab
          </Link>
        )}
      </div>

      <div className="p-4 flex-1">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-primary" />
            Environmental Layers
          </h3>
        </div>

        <div className="space-y-1.5">
          {layerItems.map((layer) => {
            const Icon = layer.icon;
            return (
              <button
                key={layer.id}
                type="button"
                onClick={() => toggleLayer(layer.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-colors border ${
                  layer.active
                    ? 'bg-slate-50 border-slate-200 text-ink'
                    : 'bg-white border-transparent text-slate-400 hover:bg-slate-50'
                }`}
                aria-pressed={layer.active}
              >
                <div className="flex items-center gap-2.5 truncate">
                  <Icon className={`w-4 h-4 shrink-0 ${layer.active ? 'text-primary' : 'text-slate-400'}`} />
                  <span className="truncate">{layer.label}</span>
                </div>
                {layer.active ? (
                  <Eye className="w-3.5 h-3.5 text-primary shrink-0" />
                ) : (
                  <EyeOff className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
