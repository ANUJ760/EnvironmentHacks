import type { components } from '@/lib/api/api-types';
import type { Geometry } from 'geojson';

export type RemovalRequest = components['schemas']['RemovalRequest'];
export type RemovalReport = components['schemas']['RemovalReport'];
export type RemovalMetric = components['schemas']['RemovalMetric'];

export interface RemovalWeather {
  source: string; complete: boolean; stale: boolean; fetched_at: string;
  age_hours: number; start_at: string; end_at: string; hours_available: number;
  rainfall_mm: number | null; spatial_scope: string; notice?: string | null;
}
export interface Finding { id: string; text: string; source: string }

export function removableKind(feature: any): RemovalRequest['kind'] | null {
  const category = feature?.properties?.category;
  return category === 'mapped_tree' || category === 'tree' ? 'tree' : ['park', 'building', 'road'].includes(category) ? category : null;
}

// Vector tiles may aggregate disjoint footprints into a MultiPolygon. Select
// only the polygon at the click, never the entire tile's building collection.
export function removalLocation(feature: any): [number, number] {
  if (feature.geometry.type === 'Point') return feature.geometry.coordinates;
  if (feature.properties?.clicked_location) return feature.properties.clicked_location;
  const ring = feature.geometry.type === 'Polygon' ? feature.geometry.coordinates[0] : feature.geometry.type === 'LineString' ? feature.geometry.coordinates : [];
  return ring[0] || [0, 0];
}

export function replacementColor(value: string) {
  return value === 'impervious' ? '#d3c8b4' : value === 'bare' ? '#d9be93' : '#b8d398';
}

export function previewGeometry(report: RemovalReport): Geometry {
  return report.affected_geometry as unknown as Geometry;
}

export function formatImpact(value: number, signed = false): string {
  if (Math.abs(value) < 0.0005) return '0';
  const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: Math.abs(value) < 10 ? 2 : 1 }).format(value);
  return signed && value > 0 ? `+${number}` : number;
}
