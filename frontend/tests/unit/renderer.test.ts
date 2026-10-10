import { describe, expect, it } from 'vitest';
import { Graphics } from 'pixi.js';
import { CityRenderer } from '@/lib/rendering/renderer';

const layers = { buildings: true, roads: true, parks: true, water: true, waste: true, air: true };

describe('CityRenderer geometry', () => {
  it('renders waterway lines and highway points without treating them as polygons or roads', () => {
    const renderer = new CityRenderer(document.createElement('div'));
    renderer.app = {} as NonNullable<CityRenderer['app']>;
    renderer.renderFeatures([
      { properties: { category: 'water' }, geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1]] } },
      { properties: { category: 'road' }, geometry: { type: 'Point', coordinates: [0, 0] } },
    ], layers);
    expect(renderer.terrainContainer.children).toHaveLength(1);
    expect(renderer.roadsContainer.children).toHaveLength(1);
  });
  it('creates fill and stroke instructions for polygons and roads in Pixi v8', () => {
    const renderer = new CityRenderer(document.createElement('div'));
    // Rendering geometry does not need a GPU; initialization owns the real app.
    renderer.app = {} as NonNullable<CityRenderer['app']>;
    renderer.renderFeatures([
      { properties: { category: 'building' }, geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] } },
      { properties: { category: 'road' }, geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1]] } },
    ], layers);
    const polygon = renderer.buildingsContainer.children[0] as Graphics;
    const road = renderer.roadsContainer.children[0] as Graphics;
    expect(polygon.context.instructions.map((instruction) => instruction.action)).toEqual(['fill', 'stroke']);
    expect(road.context.instructions.map((instruction) => instruction.action)).toEqual(['stroke']);
    renderer.renderFeatures([], layers);
    expect(polygon.destroyed).toBe(true);
    expect(road.destroyed).toBe(true);
  });
});
