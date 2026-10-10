import { create } from 'zustand';

export interface LayerVisibilityState {
  buildings: boolean;
  roads: boolean;
  parks: boolean;
  water: boolean;
  waste: boolean;
  air: boolean;
  weather: boolean;
  landcover: boolean;
  toggleLayer: (name: keyof Omit<LayerVisibilityState, 'toggleLayer' | 'setLayer'>) => void;
  setLayer: (name: keyof Omit<LayerVisibilityState, 'toggleLayer' | 'setLayer'>, visible: boolean) => void;
}

export const useLayerStore = create<LayerVisibilityState>((set) => ({
  buildings: true,
  roads: true,
  parks: true,
  water: true,
  waste: true,
  air: true,
  weather: true,
  landcover: true,
  toggleLayer: (name) => set((state) => ({ [name]: !state[name] })),
  setLayer: (name, visible) => set(() => ({ [name]: visible })),
}));
