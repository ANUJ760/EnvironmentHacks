import { describe, it, expect } from 'vitest';
import {
  formatBBox,
  parseBBox,
  computeBBoxFromGeometry,
  isPointInPolygon,
  validatePolygon,
  projectCoordinates,
} from '@/lib/geo';

describe('Geo Utilities', () => {
  it('formats and parses bounding boxes', () => {
    const bbox = { minLon: 77.1, minLat: 28.5, maxLon: 77.3, maxLat: 28.7 };
    const str = formatBBox(bbox);
    expect(str).toBe('77.100000,28.500000,77.300000,28.700000');

    const parsed = parseBBox(str);
    expect(parsed).not.toBeNull();
    expect(parsed?.minLon).toBeCloseTo(77.1);
    expect(parsed?.minLat).toBeCloseTo(28.5);
    expect(parsed?.maxLon).toBeCloseTo(77.3);
    expect(parsed?.maxLat).toBeCloseTo(28.7);
  });

  it('computes bounding box from GeoJSON Polygon geometry', () => {
    const polygon = {
      type: 'Polygon',
      coordinates: [
        [
          [10, 20],
          [15, 20],
          [15, 25],
          [10, 25],
          [10, 20],
        ],
      ],
    };
    const bbox = computeBBoxFromGeometry(polygon);
    expect(bbox.minLon).toBe(10);
    expect(bbox.minLat).toBe(20);
    expect(bbox.maxLon).toBe(15);
    expect(bbox.maxLat).toBe(25);
  });

  it('detects point in polygon correctly', () => {
    const polygon = {
      type: 'Polygon',
      coordinates: [
        [
          [0, 0],
          [10, 0],
          [10, 10],
          [0, 10],
          [0, 0],
        ],
      ],
    };

    expect(isPointInPolygon([5, 5], polygon)).toBe(true);
    expect(isPointInPolygon([15, 15], polygon)).toBe(false);
  });

  it('validates polygon ring closures', () => {
    const valid = [
      [
        [0, 0],
        [1, 0],
        [1, 1],
        [0, 0],
      ],
    ];
    expect(validatePolygon(valid).valid).toBe(true);

    const unclosed = [
      [
        [0, 0],
        [1, 0],
        [1, 1],
        [0, 1],
      ],
    ];
    expect(validatePolygon(unclosed).valid).toBe(false);
    expect(validatePolygon(unclosed).error).toContain('closed');

    const tooFew = [
      [
        [0, 0],
        [1, 0],
        [0, 0],
      ],
    ];
    expect(validatePolygon(tooFew).valid).toBe(false);
  });

  it('projects coordinates between EPSG definitions', () => {
    const wgs84: [number, number] = [0, 0];
    const mercator = projectCoordinates(wgs84, 'EPSG:4326', 'EPSG:3857');
    expect(mercator[0]).toBeCloseTo(0);
    expect(mercator[1]).toBeCloseTo(0);
  });
});
