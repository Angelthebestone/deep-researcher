"use client";

import { motion } from "framer-motion";
import { useAppStore } from "@/stores/appStore";

export function ViewToggle() {
  const view = useAppStore((state) => state.view);
  const setView = useAppStore((state) => state.setView);

  return (
    <div className="flex items-center justify-center gap-1" aria-label="Cambiar vista">
      {(["graph", "chat"] as const).map((v) => (
        <button
          key={v}
          onClick={() => setView(v)}
          aria-pressed={view === v}
          className={`relative px-4 py-1.5 text-sm font-medium transition-colors ${
            view === v ? "text-foreground" : "text-muted-foreground"
          }`}
        >
          {view === v && (
            <motion.div
              layoutId="activeViewPill"
              className="absolute inset-0 bg-primary/10 rounded-full"
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
            />
          )}
          <span className="relative z-10">
            {v === "graph" ? "Explorar" : "Conversar"}
          </span>
        </button>
      ))}
    </div>
  );
}
