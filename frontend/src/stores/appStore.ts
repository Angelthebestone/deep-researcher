import { create } from "zustand";

export interface AppState {
  view: "chat" | "graph";
  isThinkingOpen: boolean;
  isConsoleOpen: boolean;

  setView: (view: "chat" | "graph") => void;
  setConsoleOpen: (open: boolean) => void;
  setThinkingOpen: (open: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  view: "chat",
  isThinkingOpen: false,
  isConsoleOpen: false,

  setView: (view) => set({ view }),
  setConsoleOpen: (isConsoleOpen) => set({ isConsoleOpen }),
  setThinkingOpen: (isThinkingOpen) => set({ isThinkingOpen }),
}));
