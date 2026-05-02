import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { ChatMessage } from "@/types/chat";
import type {
  AnalysisStreamEvent,
  DocumentUploadResponse,
  OperationRecord,
  TechnologyMention,
  TechnologyReport,
} from "@/types/contracts";
import type { Workspace, WorkspaceCreateInput, WorkspaceStatus } from "@/types/workspace";

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function makeWorkspace(input: WorkspaceCreateInput): Workspace {
  const now = Date.now();
  return {
    id: generateId(),
    name: input.name || "Nuevo workspace",
    status: input.status || "borrador",
    createdAt: now,
    updatedAt: now,
    events: [],
    chatMessages: [],
    researchParams: { depth: 2, breadth: 3, contextFiles: [] },
    currentOperation: null,
    currentDocument: null,
    mentions: [],
    report: null,
    isAnalyzing: false,
    errorMessage: null,
  };
}

interface WorkspaceState {
  workspaces: Workspace[];
  activeWorkspaceId: string | null;

  createWorkspace: (input: WorkspaceCreateInput) => string;
  deleteWorkspace: (id: string) => void;
  setActiveWorkspace: (id: string) => void;
  updateWorkspace: (id: string, patch: Partial<Omit<Workspace, "id">>) => void;
  setWorkspaceStatus: (id: string, status: WorkspaceStatus) => void;

  addEvent: (event: AnalysisStreamEvent) => void;
  resetEvents: () => void;
  addChatMessage: (message: ChatMessage) => void;
  setResearchParam: <K extends keyof Workspace["researchParams"]>(
    key: K,
    value: Workspace["researchParams"][K],
  ) => void;
  setCurrentDocument: (doc: DocumentUploadResponse | null) => void;
  setMentions: (mentions: TechnologyMention[]) => void;
  addMentions: (mentions: TechnologyMention[]) => void;
  setReport: (report: TechnologyReport | null) => void;
  setIsAnalyzing: (val: boolean) => void;
  setErrorMessage: (msg: string | null) => void;
  setCurrentOperation: (op: OperationRecord | null) => void;
  resetSession: () => void;
}

function updateActive<T extends keyof Workspace>(
  state: WorkspaceState,
  key: T,
  value: Workspace[T],
): Partial<WorkspaceState> {
  if (!state.activeWorkspaceId) return {};
  return {
    workspaces: state.workspaces.map((w) =>
      w.id === state.activeWorkspaceId ? { ...w, [key]: value, updatedAt: Date.now() } : w,
    ),
  };
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      workspaces: [],
      activeWorkspaceId: null,

      createWorkspace: (input) => {
        const ws = makeWorkspace(input);
        set((state) => ({
          workspaces: [...state.workspaces, ws],
          activeWorkspaceId: ws.id,
        }));
        return ws.id;
      },

      deleteWorkspace: (id) =>
        set((state) => {
          const filtered = state.workspaces.filter((w) => w.id !== id);
          return {
            workspaces: filtered,
            activeWorkspaceId:
              state.activeWorkspaceId === id
                ? filtered[0]?.id ?? null
                : state.activeWorkspaceId,
          };
        }),

      setActiveWorkspace: (id) => set({ activeWorkspaceId: id }),

      updateWorkspace: (id, patch) =>
        set((state) => ({
          workspaces: state.workspaces.map((w) =>
            w.id === id ? { ...w, ...patch, updatedAt: Date.now() } : w,
          ),
        })),

      setWorkspaceStatus: (id, status) =>
        set((state) => ({
          workspaces: state.workspaces.map((w) =>
            w.id === id ? { ...w, status, updatedAt: Date.now() } : w,
          ),
        })),

      addEvent: (event) =>
        set((state) => {
          const active = state.workspaces.find((w) => w.id === state.activeWorkspaceId);
          if (!active) return state;
          if (active.events.some((e) => e.event_id === event.event_id)) return state;
          return updateActive(state, "events", [...active.events, event]);
        }),

      resetEvents: () =>
        set((state) => updateActive(state, "events", [])),

      addChatMessage: (message) =>
        set((state) => {
          const active = state.workspaces.find((w) => w.id === state.activeWorkspaceId);
          if (!active) return state;
          return updateActive(state, "chatMessages", [...active.chatMessages, message]);
        }),

      setResearchParam: (key, value) =>
        set((state) => {
          const active = state.workspaces.find((w) => w.id === state.activeWorkspaceId);
          if (!active) return state;
          return updateActive(state, "researchParams", { ...active.researchParams, [key]: value });
        }),

      setCurrentDocument: (doc) =>
        set((state) => updateActive(state, "currentDocument", doc)),

      setMentions: (mentions) =>
        set((state) => updateActive(state, "mentions", mentions)),

      addMentions: (mentions) =>
        set((state) => {
          const active = state.workspaces.find((w) => w.id === state.activeWorkspaceId);
          if (!active) return state;
          const existingIds = new Set(active.mentions.map((m) => m.mention_id));
          const newMentions = mentions.filter((m) => !existingIds.has(m.mention_id));
          return updateActive(state, "mentions", [...active.mentions, ...newMentions]);
        }),

      setReport: (report) =>
        set((state) => updateActive(state, "report", report)),

      setIsAnalyzing: (val) =>
        set((state) => updateActive(state, "isAnalyzing", val)),

      setErrorMessage: (msg) =>
        set((state) => updateActive(state, "errorMessage", msg)),

      setCurrentOperation: (op) =>
        set((state) => updateActive(state, "currentOperation", op)),

      resetSession: () =>
        set((state) => {
          const active = state.workspaces.find((w) => w.id === state.activeWorkspaceId);
          if (!active) return state;
          return updateActive(state, "events", [] as AnalysisStreamEvent[]) as Partial<WorkspaceState>;
        }),
    }),
    {
      name: "vigilador-workspaces",
      partialize: (state) => ({ workspaces: state.workspaces, activeWorkspaceId: state.activeWorkspaceId }),
    },
  ),
);
