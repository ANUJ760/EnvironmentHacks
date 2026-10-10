'use client';

import React from 'react';
import { computeBBoxFromGeometry } from '@/lib/geo';
import { WORLDCOVER_CLASSES, type ScenarioEdit } from '@/lib/scenarios';

interface SvgMapFallbackProps {
  features: any[];
  boundary?: any;
  selectedFeature: any | null;
  onSelectFeature: (feature: any) => void;
  edits?: ScenarioEdit[];
}

export function SvgMapFallback({
  features,
  boundary,
  selectedFeature,
  onSelectFeature,
  edits = [],
}: SvgMapFallbackProps) {
  const bbox = boundary ? computeBBoxFromGeometry(boundary) : { minLon: 0, minLat: 0, maxLon: 1, maxLat: 1 };
  const lonDiff = Math.max(0.0001, bbox.maxLon - bbox.minLon);
  const latDiff = Math.max(0.0001, bbox.maxLat - bbox.minLat);

  const viewBoxWidth = 800;
  const viewBoxHeight = 600;

  function toSvgCoords(lon: number, lat: number): [number, number] {
    const x = ((lon - bbox.minLon) / lonDiff) * (viewBoxWidth - 40) + 20;
    const y = viewBoxHeight - (((lat - bbox.minLat) / latDiff) * (viewBoxHeight - 40) + 20);
    return [x, y];
  }

  function renderGeometry(geom: any, isSelected: boolean) {
    if (!geom) return null;

    if (geom.type === 'Polygon' || geom.type === 'MultiPolygon') {
      const polys = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates;
      return polys.map((poly: any, pIdx: number) => {
        const exterior = poly[0];
        if (!exterior) return null;
        const pointsStr = exterior.map((pt: [number, number]) => toSvgCoords(pt[0], pt[1]).join(',')).join(' ');
        return (
          <polygon
            key={pIdx}
            points={pointsStr}
            className={`transition-colors cursor-pointer ${
              isSelected
                ? 'fill-amber-300 fill-opacity-60 stroke-amber-600 stroke-2'
                : 'fill-emerald-200 fill-opacity-40 stroke-emerald-600 stroke-1 hover:fill-opacity-70'
            }`}
          />
        );
      });
    }

    if (geom.type === 'LineString' || geom.type === 'MultiLineString') {
      const lines = geom.type === 'LineString' ? [geom.coordinates] : geom.coordinates;
      return lines.map((line: any, lIdx: number) => {
        const pointsStr = line.map((pt: [number, number]) => toSvgCoords(pt[0], pt[1]).join(',')).join(' ');
        return (
          <polyline
            key={lIdx}
            points={pointsStr}
            className="stroke-slate-700 stroke-2 fill-none"
          />
        );
      });
    }

    if (geom.type === 'Point') {
      const [x, y] = toSvgCoords(geom.coordinates[0], geom.coordinates[1]);
      return (
        <circle
          cx={x}
          cy={y}
          r={isSelected ? 8 : 5}
          className={`${isSelected ? 'fill-amber-500 stroke-white stroke-2' : 'fill-cyan-600 stroke-cyan-800'}`}
        />
      );
    }

    return null;
  }

  return (
    <div className="relative w-full h-full bg-slate-50 flex flex-col items-center justify-center p-2">
      <div className="absolute top-2 left-2 bg-white/90 backdrop-blur px-2 py-1 rounded text-xs text-slate-600 border border-slate-200">
        Accessible SVG View (DOM Fallback)
      </div>
      <svg
        viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
        className="w-full h-full max-h-[700px] border border-slate-200 rounded bg-[#f6f8f4]"
        role="region"
        aria-label="City geographic features map"
      >
        {/* Features */}
        {features.map((feat, idx) => {
          const isSelected = selectedFeature?.id === feat.id;
          return (
            <g
              key={feat.id || idx}
              onClick={() => onSelectFeature(feat)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectFeature(feat);
                }
              }}
              tabIndex={0}
              role="button"
              aria-label={`Feature: ${feat.properties?.name || feat.properties?.category || feat.id}`}
              className="focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {renderGeometry(feat.geometry, isSelected)}
            </g>
          );
        })}

        {/* Staged Scenario Edits */}
        {edits.map((edit, idx) => {
          if (edit.edit_type === 'LAND_COVER_RECLASSIFY') {
            const classInfo = WORLDCOVER_CLASSES[edit.to_class_code];
            const coords = edit.polygon_geojson?.coordinates?.[0] || [];
            const pointsStr = coords.map((pt: [number, number]) => toSvgCoords(pt[0], pt[1]).join(',')).join(' ');
            return (
              <polygon
                key={`edit-${idx}`}
                points={pointsStr}
                fill={classInfo?.color || '#2e7d32'}
                fillOpacity={0.6}
                stroke="#1b5e20"
                strokeWidth={2}
                strokeDasharray="4 2"
              />
            );
          }
          return null;
        })}
      </svg>
    </div>
  );
}
