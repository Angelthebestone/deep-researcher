import { create } from "zustand";

import type {
  AnalysisStreamEvent,
  DocumentUploadResponse,
  OperationRecord,
  TechnologyMention,
  TechnologyReport,
} from "@/types/contracts";

export type ChatMessageRole = "user" | "assistant" | "system" | "document" | "mentions" | "report";

export interface ChatMessage {
  id: string;
  role: ChatMessageRole;
  content: string;
  metadata?: Record<string, unknown>;
  createdAt: number;
}

export interface AppState {
  view: "chat" | "graph";
  events: AnalysisStreamEvent[];
  chatMessages: ChatMessage[];
  researchParams: {
    depth: number;
    breadth: number;
    contextFiles: File[];
  };
  currentOperation: OperationRecord | null;
  isThinkingOpen: boolean;
  isConsoleOpen: boolean;
  currentDocument: DocumentUploadResponse | null;
  mentions: TechnologyMention[];
  report: TechnologyReport | null;
  isAnalyzing: boolean;
  errorMessage: string | null;

  setView: (view: "chat" | "graph") => void;
  addEvent: (event: AnalysisStreamEvent) => void;
  resetEvents: () => void;
  setResearchParam: <K extends keyof AppState["researchParams"]>(
    key: K,
    value: AppState["researchParams"][K],
  ) => void;
  setConsoleOpen: (open: boolean) => void;
  setThinkingOpen: (open: boolean) => void;
  resetSession: () => void;
  addChatMessage: (message: ChatMessage) => void;
  setCurrentDocument: (doc: DocumentUploadResponse | null) => void;
  setMentions: (mentions: TechnologyMention[]) => void;
  addMentions: (mentions: TechnologyMention[]) => void;
  setReport: (report: TechnologyReport | null) => void;
  setIsAnalyzing: (val: boolean) => void;
  setErrorMessage: (msg: string | null) => void;
  setCurrentOperation: (op: OperationRecord | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  view: "chat",
  events: [],
  chatMessages: [],
  researchParams: {
    depth: 2,
    breadth: 3,
    contextFiles: [],
  },
  currentOperation: null,
  isThinkingOpen: false,
  isConsoleOpen: false,
  currentDocument: null,
  mentions: [],
  report: null,
  isAnalyzing: false,
  errorMessage: null,

  setView: (view) => set({ view }),

  addEvent: (event) =>
    set((state) => {
      if (state.events.some((e) => e.event_id === event.event_id)) {
        return state;
      }
      return { events: [...state.events, event] };
    }),

  resetEvents: () => set({ events: [] }),

  setResearchParam: (key, value) =>
    set((state) => ({
      researchParams: { ...state.researchParams, [key]: value },
    })),

  setConsoleOpen: (isConsoleOpen) => set({ isConsoleOpen }),
  setThinkingOpen: (isThinkingOpen) => set({ isThinkingOpen }),

  resetSession: () =>
    set({
      events: [],
      chatMessages: [],
      currentOperation: null,
      currentDocument: null,
      mentions: [],
      report: null,
      isAnalyzing: false,
      errorMessage: null,
    }),

  addChatMessage: (message) =>
    set((state) => ({
      chatMessages: [...state.chatMessages, message],
    })),

  setCurrentDocument: (currentDocument) => set({ currentDocument }),
  setMentions: (mentions) => set({ mentions }),
  addMentions: (mentions) =>
    set((state) => {
      const existingIds = new Set(state.mentions.map((m) => m.mention_id));
      const newMentions = mentions.filter((m) => !existingIds.has(m.mention_id));
      return { mentions: [...state.mentions, ...newMentions] };
    }),
  setReport: (report) => set({ report }),
  setIsAnalyzing: (isAnalyzing) => set({ isAnalyzing }),
  setErrorMessage: (errorMessage) => set({ errorMessage }),
  setCurrentOperation: (currentOperation) => set({ currentOperation }),
}));
