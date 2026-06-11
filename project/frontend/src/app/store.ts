import { create } from "zustand";
import { Workspace, TestingMode, LLMConfig } from "./types";

interface AppState {
  workspaces: Workspace[];
  activeWorkspaceId: string | null;
  sidebarOpen: boolean;
  workspaceCounter: number;
  addWorkspace: (name: string | undefined, mode: TestingMode) => string;
  deleteWorkspace: (id: string) => void;
  setActiveWorkspace: (id: string) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  updateWorkspaceLLM: (id: string, llmConfig: LLMConfig) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  workspaces: [],
  activeWorkspaceId: null,
  sidebarOpen: false,
  workspaceCounter: 1,
  addWorkspace: (name, mode) => {
    const state = get();
    const resolvedName = name?.trim() || `Workspace ${state.workspaceCounter}`;
    const newId = Date.now().toString();
    set({
      workspaces: [
        ...state.workspaces,
        { id: newId, name: resolvedName, mode, createdAt: new Date() },
      ],
      activeWorkspaceId: newId,
      workspaceCounter: state.workspaceCounter + 1,
    });
    return newId;
  },
  deleteWorkspace: (id) =>
    set((state) => {
      const remaining = state.workspaces.filter((w) => w.id !== id);
      if (state.activeWorkspaceId !== id) {
        return { workspaces: remaining, activeWorkspaceId: state.activeWorkspaceId };
      }
      // Sidebar shows newest-first (reversed), so "next below" = next in reversed order
      const reversedIds = [...state.workspaces].reverse().map((w) => w.id);
      const idx = reversedIds.indexOf(id);
      const nextId = reversedIds[idx + 1] ?? reversedIds[idx - 1] ?? null;
      return { workspaces: remaining, activeWorkspaceId: nextId };
    }),
  setActiveWorkspace: (id) => set({ activeWorkspaceId: id }),
  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  updateWorkspaceLLM: (id, llmConfig) =>
    set((state) => ({
      workspaces: state.workspaces.map((w) =>
        w.id === id ? { ...w, llmConfig } : w
      ),
    })),
}));
