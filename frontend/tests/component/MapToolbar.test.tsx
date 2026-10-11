import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MapToolbar } from '@/components/map/MapToolbar';

describe('MapToolbar Component', () => {
  it('triggers zoom, fit, and reset callbacks on click', () => {
    const onZoomIn = vi.fn();
    const onZoomOut = vi.fn();
    const onFitBounds = vi.fn();
    const onReset = vi.fn();
    const onToggleSvgMode = vi.fn();

    render(
      <MapToolbar
        onZoomIn={onZoomIn}
        onZoomOut={onZoomOut}
        onFitBounds={onFitBounds}
        onReset={onReset}
        isSvgMode={false}
        onToggleSvgMode={onToggleSvgMode}
      />
    );

    fireEvent.click(screen.getByLabelText('Zoom in'));
    expect(onZoomIn).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByLabelText('Zoom out'));
    expect(onZoomOut).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByLabelText('Fit city boundary'));
    expect(onFitBounds).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByLabelText('Reset camera view'));
    expect(onReset).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByLabelText('Switch to Accessible DOM/SVG View'));
    expect(onToggleSvgMode).toHaveBeenCalledTimes(1);
  });
});
