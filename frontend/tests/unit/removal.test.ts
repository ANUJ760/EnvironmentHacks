import { describe, expect, it } from 'vitest';
import { formatImpact, removableKind, removalLocation, replacementColor } from '@/lib/removal';
import { useRemovalStore } from '@/stores/removalStore';

describe('removal selection and preview', () => {
  it('allows only supported mapped features, not monitoring stations or water', () => {
    for (const category of ['tree', 'mapped_tree', 'building', 'park', 'road']) {
      expect(removableKind({ properties: { category } })).toBe(category === 'mapped_tree' ? 'tree' : category);
    }
    for (const category of ['water', 'air_station', undefined]) expect(removableKind({ properties: { category } })).toBeNull();
    expect(removableKind(null)).toBeNull();
  });

  it('uses the actual tree point and clicked location for area features', () => {
    expect(removalLocation({ geometry: { type: 'Point', coordinates: [8.54, 47.38] }, properties: { clicked_location: [8.55, 47.39] } })).toEqual([8.54, 47.38]);
    expect(removalLocation({ geometry: { type: 'Polygon', coordinates: [[[0, 0]]] }, properties: { clicked_location: [8.54, 47.38] } })).toEqual([8.54, 47.38]);
  });

  it('formats zero, small values and signed consequences without negative zero', () => {
    expect(formatImpact(-0.00001, true)).toBe('0');
    expect(formatImpact(1.234, true)).toBe('+1.23');
    expect(formatImpact(-1.234, true)).toBe('-1.23');
    expect(replacementColor('impervious')).not.toBe(replacementColor('grass'));
  });

  it('restores before/after state when switching features without saving scenario edits', () => {
    useRemovalStore.getState().setPreview({ geometry: { type: 'Point', coordinates: [8.54, 47.38] }, kind: 'tree', area: 50, color: '#abc' });
    useRemovalStore.getState().setShowingAfter(false);
    expect(useRemovalStore.getState().showingAfter).toBe(false);
    useRemovalStore.getState().setPreview({ geometry: { type: 'Point', coordinates: [8.54, 47.38] }, kind: 'tree', area: 60, color: '#abc' });
    expect(useRemovalStore.getState().showingAfter).toBe(false);
    useRemovalStore.getState().setPreview(null);
    expect(useRemovalStore.getState().preview).toBeNull();
    expect(useRemovalStore.getState().showingAfter).toBe(true);
  });
});
