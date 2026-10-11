import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PixiMap } from '@/components/map/PixiMap';

const { instances } = vi.hoisted(() => ({ instances: [] as any[] }));

vi.mock('@/lib/rendering/renderer', () => ({
  CityRenderer: class {
    camera = { fitBounds: vi.fn() };
    init = vi.fn().mockResolvedValue(true);
    resize = vi.fn();
    destroy = vi.fn();
    renderFeatures = vi.fn();
    renderSelection = vi.fn();
    renderScenarioEdits = vi.fn();
    constructor() { instances.push(this); }
  },
}));

describe('PixiMap lifecycle', () => {
  it('keeps the renderer for callback updates and redraws features after SVG mode', async () => {
    const features = [{ id: 'building', geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] } }];
    const boundary = features[0]!.geometry;
    const { rerender, unmount } = render(<PixiMap cityId="city" boundary={boundary} features={features} onBBoxChange={() => {}} />);
    await waitFor(() => expect(instances[0].renderFeatures).toHaveBeenCalledWith(features, expect.any(Object)));
    rerender(<PixiMap cityId="city" boundary={boundary} features={features} onBBoxChange={() => {}} />);
    expect(instances).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Switch to Accessible DOM/SVG View' }));
    fireEvent.click(screen.getByRole('button', { name: 'Switch to GPU WebGL View' }));
    await waitFor(() => expect(instances).toHaveLength(2));
    await waitFor(() => expect(instances[1].renderFeatures).toHaveBeenCalledWith(features, expect.any(Object)));
    unmount();
  });
});
