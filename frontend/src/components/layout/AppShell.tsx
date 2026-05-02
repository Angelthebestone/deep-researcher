"use client";

import { useEffect } from "react";
import dynamic from "next/dynamic";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { ViewToggle } from "@/components/layout/ViewToggle";
import { WorkspaceSelector } from "@/components/workspaces/WorkspaceSelector";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { ChatView } from "@/components/chat/ChatView";
import { ErrorFallback } from "@/components/ui/ErrorFallback";

const GraphView = dynamic(
  () => import("@/components/graph/GraphView").then((mod) => mod.GraphView),
  { ssr: false, loading: () => <LoadingFallback /> }
);

const ResearchConsole = dynamic(
  () =>
    import("@/components/research/ResearchConsole").then(
      (mod) => mod.ResearchConsole
    ),
  { ssr: false, loading: () => <LoadingFallback /> }
);

function LoadingFallback() {
  return (
    <div className="flex h-screen items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  );
}

export function AppShell() {
  const view = useAppStore((state) => state.view);
  const isConsoleOpen = useAppStore((state) => state.isConsoleOpen);
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const activeWorkspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const createWorkspace = useWorkspaceStore((state) => state.createWorkspace);

  useEffect(() => {
    if (workspaces.length === 0) {
      createWorkspace({ name: "Workspace principal", status: "borrador" });
    }
  }, [workspaces.length, createWorkspace]);

  return (
    <div className="relative min-h-screen flex">
      <WorkspaceSelector />

      <main className="flex-1 ml-60">
        <div className="absolute top-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3">
          <ViewToggle />
          <ThemeToggle />
        </div>

        {!activeWorkspaceId ? (
          <div className="flex items-center justify-center h-screen">
            <p className="text-muted-foreground">Crea un workspace para comenzar</p>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {view === "chat" ? (
              <motion.div
                key="chat"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
              >
                <ErrorFallback>
                  <ChatView />
                </ErrorFallback>
              </motion.div>
            ) : (
              <motion.div
                key="graph"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
              >
                <GraphView />
              </motion.div>
            )}
          </AnimatePresence>
        )}

        {isConsoleOpen && <ResearchConsole />}
      </main>
    </div>
  );
}
