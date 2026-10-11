import { describe, it, expect } from 'vitest';
import { nearestTree } from '@/lib/rendering/tree-picking';
describe('tree selection', () => {
  const point = (x: number, properties = {}) => ({ geometry: { type: 'Point', coordinates: [x, 0] }, properties });
  const project = ([x, y]: [number, number]) => ({ x, y });
  it('picks the nearest individual tree, not the first rendering layer', () => { const a = point(7), b = point(3); expect(nearestTree([a, b], { x: 0, y: 0 }, project)).toBe(b); });
  it('does not snap to distant trees or interpret a cluster as one tree', () => { expect(nearestTree([point(10), point(0, { point_count: 20 })], { x: 0, y: 0 }, project)).toBeUndefined(); });
  it('has a fixed nine CSS-pixel tolerance at every zoom', () => { expect(nearestTree([point(9)], { x: 0, y: 0 }, project)).toBeDefined(); });
});
