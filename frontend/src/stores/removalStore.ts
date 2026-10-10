import { create } from 'zustand';
import type { Geometry } from 'geojson';

interface RemovalPreview {
  geometry: Geometry;
  color: string;
  kind: string;
  area: number;
}

export const useRemovalStore = create<{
  preview: RemovalPreview | null;
  showingAfter: boolean;
  setPreview: (preview: RemovalPreview | null) => void;
  setShowingAfter: (value: boolean) => void;
}>((set) => ({
  preview: null,
  showingAfter: true,
  setPreview: (preview) => set(state => ({ preview, showingAfter: preview ? state.showingAfter : true })),
  setShowingAfter: (showingAfter) => set({ showingAfter }),
}));
