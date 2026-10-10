'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { CityRenderer } from '@/lib/rendering/renderer';
import { computeBBoxFromGeometry, isPointInPolygon } from '@/lib/geo';
import { useLayerStore } from '@/stores/layerStore';
import { useScenarioStore } from '@/stores/scenarioStore';
import { MapToolbar } from './MapToolbar';
import { MapLegend } from './MapLegend';
import { SvgMapFallback } from './SvgMapFallback';
import { AccessibleFeatureList } from './AccessibleFeatureList';

interface PixiMapProps {
  cityId: string;
  boundary?: any;
  features: any[];
  onBBoxChange?: (bboxStr: string) => void;
}

export function PixiMap({
  boundary,
  features,
  onBBoxChange,
}: PixiMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<CityRenderer | null>(null);
  const onBBoxChangeRef = useRef(onBBoxChange);
  onBBoxChangeRef.current = onBBoxChange;

  const [readyRenderer, setReadyRenderer] = useState<CityRenderer | null>(null);
  const isReady = readyRenderer !== null;
  const [webGlFailed, setWebGlFailed] = useState(false);
  const [isSvgMode, setIsSvgMode] = useState(false);
  const [showFeatureList, setShowFeatureList] = useState(false);

  const layers = useLayerStore();
  const { selectedFeature, setSelectedFeature, edits } = useScenarioStore();

  // Mouse pan state
  const isDraggingRef = useRef(false);
  const lastMousePosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Initialize Pixi renderer
  useEffect(() => {
    let active = true;
    const container = containerRef.current;
    if (!container || isSvgMode) return;

    const renderer = new CityRenderer(container);
    rendererRef.current = renderer;
    setReadyRenderer(null);

    renderer.init().then((success) => {
      if (!active) {
        renderer.destroy();
        return;
      }
      if (success) {
        setWebGlFailed(false);
        setReadyRenderer(renderer);
        // Initial boundary fit
        if (boundary) {
          const bbox = computeBBoxFromGeometry(boundary);
          renderer.camera.fitBounds(bbox);
          if (onBBoxChangeRef.current) {
            onBBoxChangeRef.current(`${bbox.minLon},${bbox.minLat},${bbox.maxLon},${bbox.maxLat}`);
          }
        }
      } else {
        setWebGlFailed(true);
        setIsSvgMode(true);
      }
    });

    // Resize observer
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        renderer.resize(width, height);
      }
    });
    resizeObserver.observe(container);

    return () => {
      active = false;
      resizeObserver.disconnect();
      renderer.destroy();
      rendererRef.current = null;
    };
  }, [isSvgMode, boundary]);

  // Update rendering when features or layers change
  useEffect(() => {
    const renderer = readyRenderer;
    if (!renderer) return;

    renderer.renderFeatures(features, {
      buildings: layers.buildings,
      roads: layers.roads,
      parks: layers.parks,
      water: layers.water,
      waste: layers.waste,
      air: layers.air,
    });
  }, [features, layers, readyRenderer]);

  // Update selection
  useEffect(() => {
    const renderer = readyRenderer;
    if (!renderer) return;
    renderer.renderSelection(selectedFeature);
  }, [selectedFeature, readyRenderer]);

  // Update scenario edits preview
  useEffect(() => {
    const renderer = readyRenderer;
    if (!renderer) return;
    renderer.renderScenarioEdits(edits);
  }, [edits, readyRenderer]);

  // Handle Pan and Zoom
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return; // Primary button only
    isDraggingRef.current = true;
    lastMousePosRef.current = { x: e.clientX, y: e.clientY };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDraggingRef.current || !rendererRef.current) return;
    const dx = e.clientX - lastMousePosRef.current.x;
    const dy = e.clientY - lastMousePosRef.current.y;
    lastMousePosRef.current = { x: e.clientX, y: e.clientY };

    const renderer = rendererRef.current;
    renderer.camera.pan(dx, dy);

    // Re-render
    renderer.renderFeatures(features, {
      buildings: layers.buildings,
      roads: layers.roads,
      parks: layers.parks,
      water: layers.water,
      waste: layers.waste,
      air: layers.air,
    });
    renderer.renderSelection(selectedFeature);
    renderer.renderScenarioEdits(edits);
  }, [features, layers, selectedFeature, edits]);

  const handleMouseUp = useCallback(() => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      if (rendererRef.current && onBBoxChange) {
        const bbox = rendererRef.current.camera.getVisibleBBox();
        onBBoxChange(`${bbox.minLon},${bbox.minLat},${bbox.maxLon},${bbox.maxLat}`);
      }
    }
  }, [onBBoxChange]);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const renderer = rendererRef.current;
    if (!renderer) return;

    const rect = containerRef.current?.getBoundingClientRect();
    const x = rect ? e.clientX - rect.left : undefined;
    const y = rect ? e.clientY - rect.top : undefined;

    const factor = e.deltaY < 0 ? 1.2 : 0.833;
    renderer.camera.zoomAt(factor, x, y);

    // Re-render
    renderer.renderFeatures(features, {
      buildings: layers.buildings,
      roads: layers.roads,
      parks: layers.parks,
      water: layers.water,
      waste: layers.waste,
      air: layers.air,
    });
    renderer.renderSelection(selectedFeature);
    renderer.renderScenarioEdits(edits);

    if (onBBoxChange) {
      const bbox = renderer.camera.getVisibleBBox();
      onBBoxChange(`${bbox.minLon},${bbox.minLat},${bbox.maxLon},${bbox.maxLat}`);
    }
  }, [features, layers, selectedFeature, edits, onBBoxChange]);

  // Click selection
  const handleClick = useCallback((e: React.MouseEvent) => {
    const renderer = rendererRef.current;
    if (!renderer) return;

    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const screenX = e.clientX - rect.left;
    const screenY = e.clientY - rect.top;

    const [clickLon, clickLat] = renderer.camera.screenToWorld(screenX, screenY);

    // Hit test top-most feature
    let matchedFeature: any = null;
    for (let i = features.length - 1; i >= 0; i--) {
      const feat = features[i];
      if (feat.geometry?.type === 'Polygon' || feat.geometry?.type === 'MultiPolygon') {
        if (isPointInPolygon([clickLon, clickLat], feat.geometry)) {
          matchedFeature = feat;
          break;
        }
      }
    }

    setSelectedFeature(matchedFeature);
  }, [features, setSelectedFeature]);

  // Toolbar Actions
  const handleZoomIn = () => {
    if (!rendererRef.current) return;
    rendererRef.current.camera.zoomAt(1.3);
    rendererRef.current.renderFeatures(features, layers);
    rendererRef.current.renderSelection(selectedFeature);
    rendererRef.current.renderScenarioEdits(edits);
  };

  const handleZoomOut = () => {
    if (!rendererRef.current) return;
    rendererRef.current.camera.zoomAt(0.77);
    rendererRef.current.renderFeatures(features, layers);
    rendererRef.current.renderSelection(selectedFeature);
    rendererRef.current.renderScenarioEdits(edits);
  };

  const handleFitBounds = () => {
    if (!rendererRef.current || !boundary) return;
    const bbox = computeBBoxFromGeometry(boundary);
    rendererRef.current.camera.fitBounds(bbox);
    rendererRef.current.renderFeatures(features, layers);
    rendererRef.current.renderSelection(selectedFeature);
    rendererRef.current.renderScenarioEdits(edits);
  };

  const handleReset = () => {
    handleFitBounds();
  };

  return (
    <div data-map-ready={isReady && !isSvgMode} aria-busy={!isSvgMode && !isReady} className="relative w-full h-full min-h-[500px] overflow-hidden bg-[#F6F8F4] select-none">
      <MapToolbar
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onFitBounds={handleFitBounds}
        onReset={handleReset}
        isSvgMode={isSvgMode || webGlFailed}
        onToggleSvgMode={() => setIsSvgMode(!isSvgMode)}
      />

      <MapLegend />

      {/* Accessible Features Toggle Button */}
      <div className="absolute top-4 right-4 z-10">
        <button
          type="button"
          onClick={() => setShowFeatureList(!showFeatureList)}
          className="text-xs bg-white/95 backdrop-blur border border-border shadow-sm px-2.5 py-1.5 rounded-lg text-ink font-medium hover:bg-slate-50 transition-colors focus:ring-2 focus:ring-primary"
          aria-expanded={showFeatureList}
        >
          {showFeatureList ? 'Hide Feature List' : `View Features (${features.length})`}
        </button>
      </div>

      {/* Collapsible Accessible Feature Directory Overlay */}
      {showFeatureList && (
        <div className="absolute top-14 right-4 z-20 w-80 max-w-[90vw]">
          <AccessibleFeatureList
            features={features}
            selectedFeature={selectedFeature}
            onSelectFeature={(feat) => setSelectedFeature(feat)}
          />
        </div>
      )}

      {/* WebGL Canvas or SVG Fallback */}
      {isSvgMode || webGlFailed ? (
        <SvgMapFallback
          features={features}
          boundary={boundary}
          selectedFeature={selectedFeature}
          onSelectFeature={(feat) => setSelectedFeature(feat)}
          edits={edits}
        />
      ) : (
        <div
          ref={containerRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onWheel={handleWheel}
          onClick={handleClick}
          className="w-full h-full cursor-grab active:cursor-grabbing"
          style={{ touchAction: 'none' }}
        />
      )}
    </div>
  );
}
