import { create } from 'zustand';
export const usePlanningStore = create<{
  drawing: boolean; points: [number, number][];
  highlighted: { name: string; category: string; id?: string | number } | null;
  setHighlighted: (value: { name: string; category: string; id?: string | number } | null) => void;
  setDrawing: (value: boolean) => void; addPoint: (point: [number, number]) => void; resetDrawing: () => void;
}>((set) => ({
  drawing: false, points: [], setDrawing: drawing => set({ drawing, points: [] }),
  highlighted: null, setHighlighted: highlighted => set(state => JSON.stringify(state.highlighted) === JSON.stringify(highlighted) ? state : { highlighted }),
  addPoint: point => set(state => ({ points: [...state.points, point].slice(0, 100) })),
  resetDrawing: () => set({ drawing: false, points: [] }),
}));
