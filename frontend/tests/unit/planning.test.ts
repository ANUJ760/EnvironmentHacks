import { describe, expect, it } from 'vitest';
import { planningKind } from '@/lib/planning';
import { usePlanningStore } from '@/stores/planningStore';

describe('custom planning selection', () => {
  it('supports water, vegetation and any polygon without requiring an LLM', () => {
    expect(planningKind({ geometry: { type: 'Polygon' }, properties: { category: 'water' } })).toBe('water');
    expect(planningKind({ geometry: { type: 'Polygon' }, properties: {} })).toBe('area');
    expect(planningKind({ geometry: { type: 'Point' }, properties: { category: 'mapped_tree' } })).toBe('tree');
    expect(planningKind(null)).toBeNull();
  });
  it('bounds drawing complexity and clears vertices on cancellation', () => {
    usePlanningStore.getState().setDrawing(true);
    for (let index = 0; index < 110; index++) usePlanningStore.getState().addPoint([8.54, 47.38]);
    expect(usePlanningStore.getState().points.length).toBe(100);
    usePlanningStore.getState().resetDrawing();
    expect(usePlanningStore.getState().drawing).toBe(false);
    expect(usePlanningStore.getState().points).toEqual([]);
  });
});
