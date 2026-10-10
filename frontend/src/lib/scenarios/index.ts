export const WORLDCOVER_CLASSES: Record<number, { name: string; color: string; description: string }> = {
  10: { name: 'Tree cover', color: '#006400', description: 'Canopy cover > 10%' },
  20: { name: 'Shrubland', color: '#ffbb22', description: 'Woody perennial with persistent stems' },
  30: { name: 'Grassland', color: '#ffff4c', description: 'Natural herbaceous cover' },
  40: { name: 'Cropland', color: '#f096ff', description: 'Cultivated and managed terrestrial lands' },
  50: { name: 'Built-up', color: '#fa0000', description: 'Artificial surfaces and buildings' },
  60: { name: 'Bare / sparse vegetation', color: '#b4b4b4', description: 'Lands with exposed soil, sand, or rocks' },
  70: { name: 'Snow and ice', color: '#f0f0f0', description: 'Permanent snow and ice fields' },
  80: { name: 'Permanent water bodies', color: '#0064c8', description: 'Lakes, reservoirs, rivers' },
  90: { name: 'Herbaceous wetland', color: '#0096a0', description: 'Wetlands dominated by herbaceous species' },
  95: { name: 'Mangroves', color: '#00cf75', description: 'Coastal salt-tolerant vegetation' },
  100: { name: 'Moss and lichen', color: '#fae6a0', description: 'Tundra and alpine areas' },
};

export type ScenarioEdit =
  | {
      edit_type: 'LAND_COVER_RECLASSIFY';
      polygon_geojson: Record<string, any>;
      from_class_code: number;
      to_class_code: number;
      fraction: number;
    }
  | {
      edit_type: 'SOLAR_PV_INSTALL';
      footprint_geojson: Record<string, any>;
      installed_kwp: number;
      performance_ratio?: number;
      panel_tilt_deg?: number;
      panel_azimuth_deg?: number;
    }
  | {
      edit_type: 'WASTE_ROUTING_OVERRIDE';
      stream_category: string;
      origin_id: string;
      facility_id: string;
      allocation_fraction: number;
    };

export type ScenarioState =
  | 'viewing_baseline'
  | 'editing_unsaved'
  | 'validating'
  | 'saving'
  | 'saved_revision'
  | 'submitting'
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'canceled'
  | 'conflict'
  | 'auth_expired';

export function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function validateLandCoverReclassify(edit: {
  polygon_geojson: any;
  from_class_code: number;
  to_class_code: number;
  fraction: number;
}): { valid: boolean; error?: string } {
  if (!edit.polygon_geojson || !edit.polygon_geojson.coordinates) {
    return { valid: false, error: 'A valid polygon geometry is required.' };
  }
  if (!WORLDCOVER_CLASSES[edit.from_class_code]) {
    return { valid: false, error: 'Invalid source land cover class.' };
  }
  if (!WORLDCOVER_CLASSES[edit.to_class_code]) {
    return { valid: false, error: 'Invalid target land cover class.' };
  }
  if (edit.from_class_code === edit.to_class_code) {
    return { valid: false, error: 'Source and target land cover classes must differ.' };
  }
  if (edit.fraction <= 0 || edit.fraction > 1.0) {
    return { valid: false, error: 'Reclassification fraction must be between 0.01 and 1.00.' };
  }
  return { valid: true };
}

export function validateSolarInstall(edit: {
  footprint_geojson: any;
  installed_kwp: number;
  performance_ratio?: number;
  panel_tilt_deg?: number;
  panel_azimuth_deg?: number;
}): { valid: boolean; error?: string } {
  if (!edit.footprint_geojson || !edit.footprint_geojson.coordinates) {
    return { valid: false, error: 'A valid solar installation footprint is required.' };
  }
  if (edit.installed_kwp <= 0 || edit.installed_kwp > 1000000) {
    return { valid: false, error: 'Installed capacity must be greater than 0 kWp and at most 1,000,000 kWp.' };
  }
  if (edit.performance_ratio !== undefined && (edit.performance_ratio <= 0 || edit.performance_ratio > 1)) {
    return { valid: false, error: 'Performance ratio must be between 0.01 and 1.00.' };
  }
  if (edit.panel_tilt_deg !== undefined && (edit.panel_tilt_deg < 0 || edit.panel_tilt_deg > 90)) {
    return { valid: false, error: 'Panel tilt must be between 0° and 90°.' };
  }
  if (edit.panel_azimuth_deg !== undefined && (edit.panel_azimuth_deg < -180 || edit.panel_azimuth_deg > 180)) {
    return { valid: false, error: 'Panel azimuth must be between -180° and 180°.' };
  }
  return { valid: true };
}
