"use client";

import { Chip } from "@nextui-org/react";
import type { WorkspaceStatus } from "@/types/workspace";

const statusConfig: Record<
  WorkspaceStatus,
  { color: "default" | "warning" | "success" | "primary"; label: string }
> = {
  borrador: { color: "default", label: "Borrador" },
  revisión: { color: "warning", label: "Revisión" },
  aprobado: { color: "success", label: "Aprobado" },
  publicado: { color: "primary", label: "Publicado" },
};

interface WorkspaceBadgeProps {
  status: WorkspaceStatus;
}

export function WorkspaceBadge({ status }: WorkspaceBadgeProps) {
  const config = statusConfig[status];
  return (
    <Chip size="sm" variant="flat" color={config.color}>
      {config.label}
    </Chip>
  );
}
