import { create } from 'zustand';
export const usePlanningStore = create<{
  drawing: boolean; points: [number, number][];
  setDrawing: (value: boolean) => void; addPoint: (point: [number, number]) => void; resetDrawing: () => void;
}>((set) => ({
  drawing: false, points: [], setDrawing: drawing => set({ drawing, points: [] }),
  addPoint: point => set(state => ({ points: [...state.points, point].slice(0, 100) })),
  resetDrawing: () => set({ drawing: false, points: [] }),
}));
