import type { components } from '@/lib/api/api-types';
export type PlanningRequest = components['schemas']['PlanningRequest'];
export type PlanningReport = components['schemas']['PlanningReport'];
export interface PlanningInventory { buildings_count: number; roads_count: number; mapped_trees_count: number; building_area_m2: number; floor_area_m2: number; buildings_with_assumed_levels: number }
export interface PlanningAir { status: string; source: string; stale?: boolean; fetched_at?: string; spatial_scope?: string; current: Record<string, number | string | null>; units: Record<string, string> }

export function planningKind(feature: any): PlanningRequest['selection_type'] | null {
  const category = feature?.properties?.category;
  if (category === 'mapped_tree' || category === 'tree') return 'tree';
  if (['building', 'park', 'road', 'water'].includes(category)) return category;
  return feature?.geometry?.type.includes('Polygon') ? 'area' : null;
}

export function exportPlanningReport(report: PlanningReport) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = `ecotwin-${report.input_sha256.slice(0, 12)}.json`;
  link.click(); URL.revokeObjectURL(url);
}
