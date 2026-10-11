'use client';

import React, { useState } from 'react';
import { Info, ChevronDown, ChevronUp } from 'lucide-react';
import { WORLDCOVER_CLASSES } from '@/lib/scenarios';

export function MapLegend() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="absolute bottom-4 left-4 z-10 max-w-xs bg-white/95 backdrop-blur border border-border rounded-lg shadow-sm text-xs text-ink overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 font-medium bg-slate-50 hover:bg-slate-100 transition-colors focus:ring-2 focus:ring-primary"
        aria-expanded={isOpen}
      >
        <span className="flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5 text-primary" />
          Map Legend & Attribution
        </span>
        {isOpen ? <ChevronDown className="w-3.5 h-3.5 text-muted" /> : <ChevronUp className="w-3.5 h-3.5 text-muted" />}
      </button>

      {isOpen && (
        <div className="p-3 space-y-3 max-h-72 overflow-y-auto">
          <div>
            <h4 className="font-semibold text-[11px] text-muted uppercase tracking-wider mb-1.5">
              Feature Classes
            </h4>
            <div className="grid grid-cols-2 gap-1.5">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-[#1e88e5] border border-blue-600 inline-block" />
                <span>Water Bodies</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-[#81c784] border border-green-600 inline-block" />
                <span>Parks & Canopy</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-[#d7ccc8] border border-stone-500 inline-block" />
                <span>Buildings</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-1 bg-[#37474f] inline-block" />
                <span>Road Network</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-[#00acc1] border border-cyan-700 inline-block" />
                <span>Air Station</span>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-semibold text-[11px] text-muted uppercase tracking-wider mb-1.5">
              ESA WorldCover (2021)
            </h4>
            <div className="space-y-1">
              {Object.entries(WORLDCOVER_CLASSES).slice(0, 5).map(([code, item]) => (
                <div key={code} className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="truncate">{item.name}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-border text-[10px] text-muted space-y-1">
            <p>© OpenStreetMap contributors (ODbL)</p>
            <p>ESA WorldCover 10m 2021 (CC-BY 4.0)</p>
            <p>Air Quality: OpenAQ / Local Environment Sensor Network</p>
          </div>
        </div>
      )}
    </div>
  );
}
