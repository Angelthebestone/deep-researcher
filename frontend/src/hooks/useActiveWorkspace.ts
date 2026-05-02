import { useWorkspaceStore } from "@/stores/workspaceStore";
import type { Workspace } from "@/types/workspace";

export function useActiveWorkspace(): Workspace | null {
  const { workspaces, activeWorkspaceId } = useWorkspaceStore();
  return workspaces.find((w) => w.id === activeWorkspaceId) ?? null;
}

export function useActiveWorkspaceActions() {
  const store = useWorkspaceStore();
  const active = useActiveWorkspace();

  return {
    active,
    addEvent: store.addEvent,
    resetEvents: store.resetEvents,
    addChatMessage: store.addChatMessage,
    setResearchParam: store.setResearchParam,
    setCurrentDocument: store.setCurrentDocument,
    setMentions: store.setMentions,
    addMentions: store.addMentions,
    setReport: store.setReport,
    setIsAnalyzing: store.setIsAnalyzing,
    setErrorMessage: store.setErrorMessage,
    setCurrentOperation: store.setCurrentOperation,
    resetSession: store.resetSession,
  };
}
