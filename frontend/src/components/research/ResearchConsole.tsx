import { useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { Chip, Button } from "@nextui-org/react";

import { useAppStore } from "@/stores/appStore";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { useActiveWorkspace } from "@/hooks/useActiveWorkspace";

export function ResearchConsole() {
  const isConsoleOpen = useAppStore((s) => s.isConsoleOpen);
  const setConsoleOpen = useAppStore((s) => s.setConsoleOpen);

  const workspace = useActiveWorkspace();
  const researchParams = workspace?.researchParams ?? { depth: 2, breadth: 3, freshness: "past_year", max_sources: 10, contextFiles: [] };
  const currentOperation = workspace?.currentOperation ?? null;
  const setResearchParam = useWorkspaceStore((s) => s.setResearchParam);
  const resetSession = useWorkspaceStore((s) => s.resetSession);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!e.target.files) return;
      const newFiles = [
        ...researchParams.contextFiles,
        ...Array.from(e.target.files),
      ];
      setResearchParam("contextFiles", newFiles);
      e.target.value = "";
    },
    [researchParams.contextFiles, setResearchParam],
  );

  const removeFile = useCallback(
    (index: number) => {
      const newFiles = researchParams.contextFiles.filter((_, i) => i !== index);
      setResearchParam("contextFiles", newFiles);
    },
    [researchParams.contextFiles, setResearchParam],
  );

  if (!isConsoleOpen) return null;

  return (
    <motion.div
      initial={{ x: "100%", opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: "100%", opacity: 0 }}
      transition={{ type: "spring", damping: 25, stiffness: 200 }}
      className="fixed right-0 top-0 h-full w-80 z-40 backdrop-blur-xl bg-background/70 backdrop-blur-md border-l border-border/20 shadow-[-20px_0_60px_rgba(0,0,0,0.04)]"
    >
      <div className="p-6 space-y-8">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">
            Consola de Investigacion
          </h2>
          <button
            type="button"
            onClick={() => setConsoleOpen(false)}
            className="text-sm font-medium text-foreground hover:text-muted-foreground transition-colors"
          >
            X
          </button>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">
              Profundidad
            </span>
            <span className="text-sm text-muted-foreground">
              {researchParams.depth}
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={5}
            step={1}
            value={researchParams.depth}
            onChange={(e) => setResearchParam("depth", Number(e.target.value))}
            className="w-full accent-lime-600"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Exploracion</span>
            <span>Investigacion profunda</span>
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">
              Amplitud
            </span>
            <span className="text-sm text-muted-foreground">
              {researchParams.breadth}
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={5}
            step={1}
            value={researchParams.breadth}
            onChange={(e) => setResearchParam("breadth", Number(e.target.value))}
            className="w-full accent-lime-600"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Focalizado</span>
            <span>Panoramico</span>
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">Antiguedad</span>
            <span className="text-sm text-muted-foreground">
              {researchParams.freshness === "past_month" ? "Ultimo mes" : researchParams.freshness === "past_year" ? "Ultimo ano" : "Cualquier fecha"}
            </span>
          </div>
          <select
            value={researchParams.freshness}
            onChange={(e) => setResearchParam("freshness", e.target.value)}
            className="w-full text-sm bg-transparent border border-border/30 rounded-lg p-2 text-foreground"
          >
            <option value="past_month">Ultimo mes</option>
            <option value="past_year">Ultimo ano</option>
            <option value="any">Cualquier fecha</option>
          </select>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">Fuentes maximas</span>
            <span className="text-sm text-muted-foreground">
              {researchParams.max_sources}
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={20}
            step={1}
            value={researchParams.max_sources}
            onChange={(e) => setResearchParam("max_sources", Number(e.target.value))}
            className="w-full accent-lime-600"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>1 fuente</span>
            <span>20 fuentes</span>
          </div>
        </div>

        <div className="space-y-3">
          <span className="text-sm font-medium text-foreground">Contexto</span>
          <div
            onClick={() => fileInputRef.current?.click()}
            className="h-[50px] flex items-center justify-center border border-dashed border-border rounded-xl cursor-pointer hover:bg-muted/50 transition-colors"
          >
            <span className="text-xs text-muted-foreground">
              Arrastra archivos de contexto
            </span>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
          <div className="flex flex-wrap gap-2">
            {researchParams.contextFiles.map((file, index) => (
              <Chip
                key={`${file.name}-${index}`}
                onClose={() => removeFile(index)}
                size="sm"
              >
                {file.name}
              </Chip>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
            Clave de idempotencia
          </span>
          <p className="text-[10px] font-mono text-muted-foreground break-all">
            {currentOperation?.idempotency_key ?? "—"}
          </p>
          <Button
            variant="light"
            color="danger"
            size="sm"
            onPress={resetSession}
          >
            Nueva sesión
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
