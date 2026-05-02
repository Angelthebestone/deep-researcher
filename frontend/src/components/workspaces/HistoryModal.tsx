"use client";

import React from "react";
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  Divider,
  Chip,
  ScrollShadow,
} from "@nextui-org/react";
import { History, Clock, GitCommit, ArrowRightLeft } from "lucide-react";
import { useWorkspaceStore } from "@/stores/workspaceStore";

interface HistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId: string;
}

function formatDate(ts: number): string {
  return new Date(ts).toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRelative(ts: number): string {
  const diff = Date.now() - ts;
  const minutes = Math.floor(diff / (1000 * 60));
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "ayer";
  return `hace ${days} días`;
}

interface Snapshot {
  id: string;
  label: string;
  date: number;
  mentionsCount: number;
  reportStatus: string;
  documentStatus: string;
  depth: number;
  breadth: number;
}

export function HistoryModal({ isOpen, onClose, workspaceId }: HistoryModalProps) {
  const workspace = useWorkspaceStore((state) =>
    state.workspaces.find((w) => w.id === workspaceId),
  );

  if (!workspace) return null;

  const currentMentions = workspace.mentions.length;
  const reportStatus = workspace.report ? "generado" : "pendiente";
  const documentStatus = workspace.currentDocument ? "analizado" : "sin documento";

  const derivedEvents = workspace.events.length > 0
    ? workspace.events.map((ev) => {
        const ts =
          typeof ev.details?.timestamp === "string" || typeof ev.details?.timestamp === "number"
            ? ev.details.timestamp
            : Date.now();
        return {
          id: ev.event_id,
          label: ev.message || ev.event_type,
          date: new Date(ts).getTime(),
          icon: GitCommit,
        };
      })
    : [
        {
          id: "created",
          label: "Workspace creado",
          date: workspace.createdAt,
          icon: GitCommit,
        },
        ...(workspace.currentDocument
          ? [
              {
                id: "doc-analyzed",
                label: "Documento analizado",
                date: workspace.updatedAt,
                icon: GitCommit,
              } as const,
            ]
          : []),
        ...(workspace.report
          ? [
              {
                id: "report",
                label: "Reporte generado",
                date: workspace.updatedAt,
                icon: GitCommit,
              } as const,
            ]
          : []),
      ];

  const initialSnapshot: Snapshot = {
    id: "initial",
    label: "Estado inicial",
    date: workspace.createdAt,
    mentionsCount: 0,
    reportStatus: "pendiente",
    documentStatus: "sin documento",
    depth: workspace.researchParams.depth,
    breadth: workspace.researchParams.breadth,
  };

  const currentSnapshot: Snapshot = {
    id: "current",
    label: "Resumen actual",
    date: workspace.updatedAt,
    mentionsCount: currentMentions,
    reportStatus,
    documentStatus,
    depth: workspace.researchParams.depth,
    breadth: workspace.researchParams.breadth,
  };

  return (
    <Modal
      isOpen={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      size="3xl"
      scrollBehavior="inside"
    >
      <ModalContent className="bg-background text-foreground">
        <ModalHeader className="flex items-center gap-2">
          <History className="size-5 text-primary" />
          <span>Historial de auditoría</span>
        </ModalHeader>
        <ModalBody>
          <ScrollShadow className="max-h-[70vh] pr-2">
            {/* 1. Resumen actual */}
            <section className="mb-6">
              <h3 className="text-sm font-semibold text-foreground mb-3">Resumen actual</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1 rounded-lg bg-muted/40 p-3 border border-border">
                  <span className="text-xs text-muted-foreground">Menciones</span>
                  <span className="text-lg font-semibold text-foreground">{currentMentions}</span>
                </div>
                <div className="flex flex-col gap-1 rounded-lg bg-muted/40 p-3 border border-border">
                  <span className="text-xs text-muted-foreground">Estado</span>
                  <Chip size="sm" variant="flat" color="primary">
                    {workspace.status}
                  </Chip>
                </div>
                <div className="flex flex-col gap-1 rounded-lg bg-muted/40 p-3 border border-border">
                  <span className="text-xs text-muted-foreground">Documento</span>
                  <span className="text-sm font-medium text-foreground capitalize">{documentStatus}</span>
                </div>
                <div className="flex flex-col gap-1 rounded-lg bg-muted/40 p-3 border border-border">
                  <span className="text-xs text-muted-foreground">Reporte</span>
                  <span className="text-sm font-medium text-foreground capitalize">{reportStatus}</span>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                <Clock className="size-3.5" />
                <span>
                  Última actualización: {formatDate(workspace.updatedAt)} ({formatRelative(workspace.updatedAt)})
                </span>
              </div>
              <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">Parámetros:</span>
                <span>profundidad {workspace.researchParams.depth}</span>
                <span>·</span>
                <span>amplitud {workspace.researchParams.breadth}</span>
              </div>
            </section>

            <Divider />

            {/* 2. Línea de tiempo */}
            <section className="mb-6">
              <h3 className="text-sm font-semibold text-foreground mb-3">Línea de tiempo</h3>
              <div className="relative pl-4">
                <div className="absolute left-[9px] top-2 bottom-2 w-px bg-border" />
                <div className="flex flex-col gap-4">
                  {derivedEvents.map((event) => (
                    <div key={event.id} className="relative flex items-start gap-3">
                      <div className="mt-1 z-10 flex size-4 shrink-0 items-center justify-center rounded-full bg-primary/20 ring-2 ring-background">
                        <event.icon className="size-3 text-primary" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground">{event.label}</span>
                        <span className="text-xs text-muted-foreground">{formatDate(event.date)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-4 flex flex-col gap-2">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Snapshots
                </span>
                {[initialSnapshot, currentSnapshot].map((snap) => (
                  <div
                    key={snap.id}
                    className="flex items-center justify-between rounded-md border border-border bg-muted/30 px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <GitCommit className="size-3.5 text-muted-foreground" />
                      <span className="text-sm text-foreground">{snap.label}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">{formatRelative(snap.date)}</span>
                  </div>
                ))}
              </div>
            </section>

            <Divider />

            {/* 3. Comparación */}
            <section className="pb-2">
              <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                <ArrowRightLeft className="size-4 text-primary" />
                Comparación
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Estado inicial
                  </div>
                  <div className="flex flex-col gap-2 text-sm text-foreground">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Fecha</span>
                      <span>{formatDate(initialSnapshot.date)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Menciones</span>
                      <span>{initialSnapshot.mentionsCount}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Documento</span>
                      <span className="capitalize">{initialSnapshot.documentStatus}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Reporte</span>
                      <span className="capitalize">{initialSnapshot.reportStatus}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Profundidad</span>
                      <span>{initialSnapshot.depth}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Amplitud</span>
                      <span>{initialSnapshot.breadth}</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Estado actual
                  </div>
                  <div className="flex flex-col gap-2 text-sm text-foreground">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Fecha</span>
                      <span>{formatDate(currentSnapshot.date)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Menciones</span>
                      <span>{currentSnapshot.mentionsCount}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Documento</span>
                      <span className="capitalize">{currentSnapshot.documentStatus}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Reporte</span>
                      <span className="capitalize">{currentSnapshot.reportStatus}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Profundidad</span>
                      <span>{currentSnapshot.depth}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Amplitud</span>
                      <span>{currentSnapshot.breadth}</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </ScrollShadow>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}
