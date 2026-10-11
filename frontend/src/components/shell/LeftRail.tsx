'use client';

import React from 'react';
import { Layers, Eye, EyeOff, TreePine, Building2, Droplets, Car, Trash2, Wind, CloudSun, Play } from 'lucide-react';
import { useLayerStore } from '@/stores/layerStore';
import { useScenarioStore } from '@/stores/scenarioStore';
import { usePlanningStore } from '@/stores/planningStore';
import { selectionKey, usePlanningResultStore } from '@/stores/planningResultStore';
import type { PlanningInventory } from '@/lib/planning';

interface LeftRailProps {
  cityId?: string;
  cityName?: string;
  isSimulatePage?: boolean;
}

export function LeftRail({ cityId, cityName, isSimulatePage = false }: LeftRailProps) {
  const { buildings, roads, parks, water, waste, air, weather, landcover, toggleLayer } = useLayerStore();
  const feature = useScenarioStore(state => state.selectedFeature);
  const highlighted = usePlanningStore(state => state.highlighted);
  const result = usePlanningResultStore();
  const inventory = result.key === selectionKey(feature) ? result.report?.inventory as unknown as PlanningInventory | undefined : undefined;

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
      className="layer-rail w-56 border-r border-slate-800 bg-background flex flex-col shrink-0 overflow-y-auto"
      aria-label="Layer and intervention controls"
    >
      <div className="p-4 border-b border-slate-800">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Planning workspace</h2>
        <p className="text-base font-bold text-ink truncate mt-0.5">{cityName || 'Overview'}</p>

        <section className="planning-card mt-4" aria-label="Highlighted elements">
          <h3 className="text-primary text-sm">{highlighted ? 'Under pointer' : 'Selected element'}</h3>
          <p className="mt-2 text-base break-words">{highlighted?.name || feature?.properties?.name || 'Nothing selected'}</p>
          <p className="text-xs mt-2 capitalize">{highlighted?.category || feature?.properties?.category || 'Hover or click the map'}</p>
          {feature && <div className="text-xs mt-3 space-y-2"><p>Selected: {feature.properties?.name}</p>{feature.properties?.species && <p>{feature.properties.species}</p>}<p>{feature.properties?.source}</p>{feature.properties?.crown_note && <p>{feature.properties.crown_note}</p>}</div>}
        </section>
        {inventory && <section className="planning-card mt-3 text-sm" aria-label="Selected inventory"><h3 className="text-primary mb-2">Inside selection</h3><p>{inventory.buildings_count} buildings</p><p>{inventory.mapped_trees_count} mapped trees</p><p>{inventory.roads_count} roads</p><p className="text-xs mt-2">Mapped counts, not a complete census.</p></section>}
      </div>

      <div className="p-4 flex-1">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-primary" />
            Map layers
          </h3>
        </div>

        <div className="space-y-1.5">
          {layerItems.map((layer) => {
            const Icon = layer.icon;
            return (
              <button
                key={layer.id}
                type="button"
                aria-label={layer.label}
                onClick={() => toggleLayer(layer.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-colors border ${
                  layer.active
                    ? 'bg-sky-100 border-sky-200 text-ink'
                    : 'bg-white border-transparent text-slate-500 hover:bg-slate-50'
                }`}
                aria-pressed={layer.active}
              >
                <div className="flex items-center gap-2.5 truncate">
                  <Icon className={`w-4 h-4 shrink-0 ${layer.active ? 'text-primary' : 'text-slate-400'}`} />
                  <span className="truncate">{layer.label.split(' (')[0]?.replace('Road Network', 'Roads').replace('Parks & Canopy', 'Parks & trees').replace('Weather Forecast', 'Weather').replace('Waste Facilities', 'Waste facilities')}</span>
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
