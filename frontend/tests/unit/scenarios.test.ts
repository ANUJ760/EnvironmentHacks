import { describe, it, expect } from 'vitest';
import {
  generateUUID,
  validateLandCoverReclassify,
  validateSolarInstall,
  WORLDCOVER_CLASSES,
} from '@/lib/scenarios';

describe('Scenarios Domain & Validation', () => {
  it('generates valid RFC 4122 UUID v4 strings', () => {
    const id1 = generateUUID();
    const id2 = generateUUID();
    expect(id1).not.toBe(id2);
    expect(id1).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  });

  it('validates land cover reclassify edits', () => {
    const validEdit = {
      polygon_geojson: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
      from_class_code: 50,
      to_class_code: 10,
      fraction: 0.5,
    };
    expect(validateLandCoverReclassify(validEdit).valid).toBe(true);

    // Identical from and to
    const sameClasses = { ...validEdit, from_class_code: 10, to_class_code: 10 };
    expect(validateLandCoverReclassify(sameClasses).valid).toBe(false);

    // Invalid fraction
    const invalidFraction = { ...validEdit, fraction: 1.5 };
    expect(validateLandCoverReclassify(invalidFraction).valid).toBe(false);
  });

  it('validates solar install edits', () => {
    const validSolar = {
      footprint_geojson: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
      installed_kwp: 500,
      performance_ratio: 0.75,
      panel_tilt_deg: 20,
      panel_azimuth_deg: 0,
    };
    expect(validateSolarInstall(validSolar).valid).toBe(true);

    const negativeCapacity = { ...validSolar, installed_kwp: -10 };
    expect(validateSolarInstall(negativeCapacity).valid).toBe(false);

    const invalidTilt = { ...validSolar, panel_tilt_deg: 120 };
    expect(validateSolarInstall(invalidTilt).valid).toBe(false);
  });

  it('contains expected ESA WorldCover class codes', () => {
    expect(WORLDCOVER_CLASSES[10]?.name).toBe('Tree cover');
    expect(WORLDCOVER_CLASSES[50]?.name).toBe('Built-up');
    expect(WORLDCOVER_CLASSES[80]?.name).toBe('Permanent water bodies');
  });
});
