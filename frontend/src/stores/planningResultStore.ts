import { create } from 'zustand';
import type { PlanningReport } from '@/lib/planning';
export const selectionKey = (feature: unknown) => JSON.stringify(feature);
export const usePlanningResultStore = create<{
  report: PlanningReport | null; key: string; pending: boolean;
  publish: (report: PlanningReport | null, key: string, pending: boolean) => void;
}>((set) => ({ report: null, key: '', pending: false, publish: (report, key, pending) => set({ report, key, pending }) }));
