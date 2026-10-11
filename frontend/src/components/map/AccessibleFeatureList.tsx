'use client';

import React, { useState } from 'react';
import { Layers, MapPin, Eye } from 'lucide-react';

interface AccessibleFeatureListProps {
  features: any[];
  selectedFeature: any | null;
  onSelectFeature: (feature: any) => void;
}

export function AccessibleFeatureList({
  features,
  selectedFeature,
  onSelectFeature,
}: AccessibleFeatureListProps) {
  const [filter, setFilter] = useState('');

  const filtered = features.filter((f) => {
    if (!filter) return true;
    const name = f.properties?.name || '';
    const cat = f.properties?.category || f.properties?.class || '';
    return (
      name.toLowerCase().includes(filter.toLowerCase()) ||
      cat.toLowerCase().includes(filter.toLowerCase())
    );
  });

  return (
    <div className="bg-white rounded-lg border border-border p-4 shadow-sm" aria-label="Accessible features table">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-ink flex items-center gap-1.5">
          <Layers className="w-4 h-4 text-primary" />
          Map Feature Directory ({features.length})
        </h3>
        <input
          type="search"
          placeholder="Filter features..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="text-xs px-2.5 py-1 border border-border rounded focus:outline-none focus:ring-1 focus:ring-primary w-40"
          aria-label="Filter features by name or category"
        />
      </div>

      <div className="max-h-60 overflow-y-auto divide-y divide-border text-xs">
        {filtered.length === 0 ? (
          <p className="text-muted py-3 text-center">No matching features in current view.</p>
        ) : (
          filtered.slice(0, 50).map((feat, idx) => {
            const isSelected = selectedFeature?.id === feat.id;
            const name = feat.properties?.name || feat.properties?.category || `Feature #${idx + 1}`;
            const category = feat.properties?.category || feat.properties?.class || feat.geometry?.type || 'Geometry';

            return (
              <div
                key={feat.id || idx}
                className={`py-2 px-2 flex items-center justify-between hover:bg-slate-50 transition-colors ${
                  isSelected ? 'bg-primary-light font-medium' : ''
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <MapPin className="w-3.5 h-3.5 text-muted shrink-0" />
                  <span className="truncate text-ink">{name}</span>
                  <span className="text-[10px] bg-slate-100 text-muted px-1.5 py-0.5 rounded uppercase">
                    {category}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => onSelectFeature(feat)}
                  className="ml-2 text-primary hover:text-forest text-xs flex items-center gap-1 shrink-0 font-medium focus:ring-2 focus:ring-primary rounded p-1"
                  aria-label={`Select ${name}`}
                >
                  <Eye className="w-3 h-3" />
                  {isSelected ? 'Selected' : 'Select'}
                </button>
              </div>
            );
          })
        )}
      </div>
      {features.length > 50 && (
        <p className="text-[10px] text-muted mt-2">Showing first 50 of {features.length} visible features.</p>
      )}
    </div>
  );
}
