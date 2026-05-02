"use client";

import { useState } from "react";
import { Button, ScrollShadow } from "@nextui-org/react";
import { FolderOpen, Plus, Trash2, Clock, Download, History } from "lucide-react";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { WorkspaceBadge } from "./WorkspaceBadge";
import { ExportModal } from "./ExportModal";
import { HistoryModal } from "./HistoryModal";

function formatRelativeTime(timestamp: number): string {
  const now = new Date();
  const date = new Date(timestamp);
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "hoy";
  if (diffDays === 1) return "ayer";
  return `hace ${diffDays} días`;
}

export function WorkspaceSelector() {
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const activeWorkspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const createWorkspace = useWorkspaceStore((state) => state.createWorkspace);
  const deleteWorkspace = useWorkspaceStore((state) => state.deleteWorkspace);
  const setActiveWorkspace = useWorkspaceStore((state) => state.setActiveWorkspace);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  const handleCreate = () => {
    createWorkspace({ name: "Nuevo workspace" });
  };

  const handleDelete = (id: string, name: string) => {
    if (window.confirm(`¿Eliminar workspace "${name}"?`)) {
      deleteWorkspace(id);
    }
  };

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 flex flex-col bg-background/80 backdrop-blur-md border-r border-border z-40">
      <div className="flex items-center justify-between px-4 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <FolderOpen className="size-5 text-primary" />
          <h2 className="font-semibold text-sm text-foreground">Workspaces</h2>
        </div>
        <Button
          size="sm"
          variant="light"
          color="primary"
          startContent={<Plus className="size-4" />}
          onPress={handleCreate}
        >
          Nuevo
        </Button>
      </div>

      <ScrollShadow className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="flex flex-col gap-1 p-2">
          {workspaces.map((ws) => {
            const isActive = ws.id === activeWorkspaceId;
            return (
              <div
                key={ws.id}
                className={`group relative flex flex-col gap-1 rounded-xl px-3 py-2.5 cursor-pointer transition-colors ${
                  isActive ? "bg-primary/10" : "hover:bg-muted"
                }`}
                onClick={() => setActiveWorkspace(ws.id)}
                onMouseEnter={() => setHoveredId(ws.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-medium truncate pr-6 ${isActive ? "text-primary" : "text-foreground"}`}>
                    {ws.name}
                  </span>
                  {hoveredId === ws.id && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(ws.id, ws.name);
                      }}
                      className="absolute right-2 top-2 p-1 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                      aria-label={`Eliminar ${ws.name}`}
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <WorkspaceBadge status={ws.status} />
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="size-3" />
                    <span>{formatRelativeTime(ws.updatedAt)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </ScrollShadow>

      {activeWorkspaceId && (
        <div className="px-4 py-3 border-t border-border flex items-center gap-2">
          <Button
            size="sm"
            variant="light"
            startContent={<Download className="size-4" />}
            onPress={() => setIsExportOpen(true)}
            className="flex-1"
          >
            Exportar
          </Button>
          <Button
            size="sm"
            variant="light"
            startContent={<History className="size-4" />}
            onPress={() => setIsHistoryOpen(true)}
            className="flex-1"
          >
            Historial
          </Button>
        </div>
      )}

      {activeWorkspaceId && (
        <>
          <ExportModal
            isOpen={isExportOpen}
            onClose={() => setIsExportOpen(false)}
            workspaceId={activeWorkspaceId}
          />
          <HistoryModal
            isOpen={isHistoryOpen}
            onClose={() => setIsHistoryOpen(false)}
            workspaceId={activeWorkspaceId}
          />
        </>
      )}
    </aside>
  );
}
