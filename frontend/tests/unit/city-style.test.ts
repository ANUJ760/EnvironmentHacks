import { describe, expect, it } from 'vitest';
import { validateStyleMin } from '@maplibre/maplibre-gl-style-spec';
import { createCityStyle, cityVisualConfig, CITY_LAYER_GROUPS, ZURICH_BOUNDS } from '@/lib/rendering/city-style';

describe('Illustrated 2D city', () => {
  it('uses a valid style without 3D geometry, terrain, or animations', () => {
    const style = createCityStyle(true);
    expect(validateStyleMin(style)).toEqual([]);
    expect(style.layers.some(layer => layer.type === 'fill-extrusion')).toBe(false);
    expect(style.terrain).toBeUndefined();
    const ids = new Set(style.layers.map(layer => layer.id));
    expect(ids.size).toBe(style.layers.length);
    for (const id of Object.values(CITY_LAYER_GROUPS).flat()) expect(ids.has(id)).toBe(true);
  });

  it('provides complete-city geography independently of the smaller analysis boundary', () => {
    const boundary = { type: 'Polygon', coordinates: [[[8.53, 47.37], [8.55, 47.37], [8.55, 47.39], [8.53, 47.39], [8.53, 47.37]]] };
    const config = cityVisualConfig('zurich-center', boundary);
    expect(config.bounds).toEqual(ZURICH_BOUNDS);
    expect(config.bounds[0]).toBeLessThan(8.53);
    expect(config.bounds[2]).toBeGreaterThan(8.55);
    expect(config.treesUrl).toBe('/maps/zurich-trees.geojson');
    expect(createCityStyle(false).sources.imagery).toBeUndefined();
    expect(validateStyleMin(createCityStyle(false))).toEqual([]);
  });
});
