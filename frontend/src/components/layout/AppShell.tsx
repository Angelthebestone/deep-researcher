"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useAppStore } from "@/stores/appStore";
import { ViewToggle } from "@/components/layout/ViewToggle";
import { ChatView } from "@/components/chat/ChatView";
import { GraphView } from "@/components/graph/GraphView";
import { ResearchConsole } from "@/components/research/ResearchConsole";

export function AppShell() {
  const view = useAppStore((state) => state.view);
  const isConsoleOpen = useAppStore((state) => state.isConsoleOpen);

  return (
    <div className="relative min-h-screen">
      <div className="absolute top-6 left-1/2 -translate-x-1/2 z-50">
        <ViewToggle />
      </div>

      <AnimatePresence mode="wait">
        {view === "chat" ? (
          <motion.div
            key="chat"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
          >
            <ChatView />
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

      {isConsoleOpen && <ResearchConsole />}
    </div>
  );
}
