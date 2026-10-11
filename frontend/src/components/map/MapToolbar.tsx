'use client';

import React from 'react';
import { ZoomIn, ZoomOut, Maximize2, RotateCcw, Layers, Code2 } from 'lucide-react';

interface MapToolbarProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitBounds: () => void;
  onReset: () => void;
  isSvgMode: boolean;
  onToggleSvgMode: () => void;
}

export function MapToolbar({
  onZoomIn,
  onZoomOut,
  onFitBounds,
  onReset,
  isSvgMode,
  onToggleSvgMode,
}: MapToolbarProps) {
  return (
    <div
      className="absolute top-4 left-4 z-10 flex flex-col gap-1.5 bg-white/95 backdrop-blur border border-border rounded-lg shadow-sm p-1.5"
      role="toolbar"
      aria-label="Map navigation tools"
    >
      <button
        type="button"
        onClick={onZoomIn}
        className="p-2 hover:bg-slate-100 rounded text-ink transition-colors focus:ring-2 focus:ring-primary"
        title="Zoom in"
        aria-label="Zoom in"
      >
        <ZoomIn className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={onZoomOut}
        className="p-2 hover:bg-slate-100 rounded text-ink transition-colors focus:ring-2 focus:ring-primary"
        title="Zoom out"
        aria-label="Zoom out"
      >
        <ZoomOut className="w-4 h-4" />
      </button>
      <div className="h-px bg-border my-0.5" />
      <button
        type="button"
        onClick={onFitBounds}
        className="p-2 hover:bg-slate-100 rounded text-ink transition-colors focus:ring-2 focus:ring-primary"
        title="Fit city boundary"
        aria-label="Fit city boundary"
      >
        <Maximize2 className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={onReset}
        className="p-2 hover:bg-slate-100 rounded text-ink transition-colors focus:ring-2 focus:ring-primary"
        title="Reset camera view"
        aria-label="Reset camera view"
      >
        <RotateCcw className="w-4 h-4" />
      </button>
      <div className="h-px bg-border my-0.5" />
      <button
        type="button"
        onClick={onToggleSvgMode}
        className={`p-2 rounded transition-colors focus:ring-2 focus:ring-primary ${
          isSvgMode ? 'bg-primary text-white' : 'hover:bg-slate-100 text-ink'
        }`}
        title={isSvgMode ? 'Switch to GPU WebGL View' : 'Switch to Accessible DOM/SVG View'}
        aria-label={isSvgMode ? 'Switch to GPU WebGL View' : 'Switch to Accessible DOM/SVG View'}
      >
        <Code2 className="w-4 h-4" />
      </button>
    </div>
  );
}
