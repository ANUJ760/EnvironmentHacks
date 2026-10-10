import { create } from 'zustand';
import type { ScenarioEdit, ScenarioState } from '@/lib/scenarios';

export interface ScenarioStoreState {
  scenarioId: string | null;
  scenarioName: string;
  snapshotId: string | null;
  version: number;
  eTag: string | null;
  edits: ScenarioEdit[];
  undoStack: ScenarioEdit[][];
  redoStack: ScenarioEdit[][];
  state: ScenarioState;
  selectedFeature: any | null;
  activeJobId: string | null;
  conflictData: { serverEdits: any[]; draftEdits: ScenarioEdit[] } | null;

  setScenario: (data: { id: string; name: string; snapshotId: string; version: number; eTag?: string | null; edits?: ScenarioEdit[] }) => void;
  resetScenario: () => void;
  setETag: (eTag: string | null) => void;
  setVersion: (version: number) => void;
  setState: (state: ScenarioState) => void;
  setSelectedFeature: (feature: any | null) => void;
  setActiveJobId: (jobId: string | null) => void;
  setConflict: (data: { serverEdits: any[]; draftEdits: ScenarioEdit[] } | null) => void;

  addEdit: (edit: ScenarioEdit) => void;
  removeEdit: (index: number) => void;
  reorderEdits: (newEdits: ScenarioEdit[]) => void;
  undo: () => void;
  redo: () => void;
  clearEdits: () => void;
}

export const useScenarioStore = create<ScenarioStoreState>((set, get) => ({
  scenarioId: null,
  scenarioName: '',
  snapshotId: null,
  version: 0,
  eTag: null,
  edits: [],
  undoStack: [],
  redoStack: [],
  state: 'viewing_baseline',
  selectedFeature: null,
  activeJobId: null,
  conflictData: null,

  setScenario: ({ id, name, snapshotId, version, eTag = null, edits = [] }) =>
    set({
      scenarioId: id,
      scenarioName: name,
      snapshotId,
      version,
      eTag,
      edits,
      undoStack: [],
      redoStack: [],
      state: 'saved_revision',
    }),

  resetScenario: () =>
    set({
      scenarioId: null,
      scenarioName: '',
      snapshotId: null,
      version: 0,
      eTag: null,
      edits: [],
      undoStack: [],
      redoStack: [],
      state: 'viewing_baseline',
      selectedFeature: null,
      activeJobId: null,
      conflictData: null,
    }),

  setETag: (eTag) => set({ eTag }),
  setVersion: (version) => set({ version }),
  setState: (state) => set({ state }),
  setSelectedFeature: (selectedFeature) => set({ selectedFeature }),
  setActiveJobId: (activeJobId) => set({ activeJobId }),
  setConflict: (conflictData) => set({ conflictData, state: conflictData ? 'conflict' : get().state }),

  addEdit: (edit) => {
    const currentEdits = get().edits;
    set({
      edits: [...currentEdits, edit],
      undoStack: [...get().undoStack, currentEdits],
      redoStack: [],
      state: 'editing_unsaved',
    });
  },

  removeEdit: (index) => {
    const currentEdits = get().edits;
    const newEdits = currentEdits.filter((_, i) => i !== index);
    set({
      edits: newEdits,
      undoStack: [...get().undoStack, currentEdits],
      redoStack: [],
      state: 'editing_unsaved',
    });
  },

  reorderEdits: (newEdits) => {
    const currentEdits = get().edits;
    set({
      edits: newEdits,
      undoStack: [...get().undoStack, currentEdits],
      redoStack: [],
      state: 'editing_unsaved',
    });
  },

  undo: () => {
    const { undoStack, edits, redoStack } = get();
    if (undoStack.length === 0) return;
    const previous = undoStack[undoStack.length - 1];
    set({
      edits: previous,
      undoStack: undoStack.slice(0, -1),
      redoStack: [...redoStack, edits],
      state: 'editing_unsaved',
    });
  },

  redo: () => {
    const { redoStack, edits, undoStack } = get();
    if (redoStack.length === 0) return;
    const next = redoStack[redoStack.length - 1];
    set({
      edits: next,
      redoStack: redoStack.slice(0, -1),
      undoStack: [...undoStack, edits],
      state: 'editing_unsaved',
    });
  },

  clearEdits: () => {
    const currentEdits = get().edits;
    set({
      edits: [],
      undoStack: [...get().undoStack, currentEdits],
      redoStack: [],
      state: 'editing_unsaved',
    });
  },
}));
