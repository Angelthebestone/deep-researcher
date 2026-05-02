import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { BadgeCheck } from "lucide-react";
import { Chip } from "@nextui-org/react";

import type { GraphNodeData } from "./types";

export const FlowNodeTechnology = memo(function FlowNodeTechnology(props: NodeProps) {
  const data = props.data as GraphNodeData;
  const selected = props.selected;

  const priorityScore = data.priorityScore;
  const priorityLabel =
    typeof priorityScore === "number"
      ? priorityScore <= 30
        ? "Baja"
        : priorityScore <= 60
          ? "Media"
          : "Alta"
      : null;
  const priorityColor =
    typeof priorityScore === "number"
      ? priorityScore <= 30
        ? "success"
        : priorityScore <= 60
          ? "warning"
          : "danger"
      : null;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative">
        <div
          className={[
            "flex size-14 items-center justify-center rounded-full border-2 shadow-md transition-all",
            "bg-background text-primary border-primary/40",
            "hover:shadow-[0_0_20px_rgba(124,58,237,0.4)] hover:scale-110",
            selected ? "ring-4 ring-primary/30 scale-110 shadow-[0_0_20px_rgba(124,58,237,0.4)]" : "",
          ].join(" ")}
        >
          <BadgeCheck className="size-6" />
          <Handle type="target" position={Position.Left} className="opacity-0" />
          <Handle type="source" position={Position.Right} className="opacity-0" />
        </div>
        {priorityLabel && priorityColor && (
          <Chip
            size="sm"
            color={priorityColor as "success" | "warning" | "danger"}
            variant="flat"
            className="absolute -top-1.5 -right-2 text-[10px] min-w-0 h-5 px-1.5"
          >
            {priorityLabel}
          </Chip>
        )}
      </div>
      <div className="rounded-md bg-background/90 px-2 py-0.5 text-xs font-semibold text-foreground shadow-sm backdrop-blur whitespace-nowrap max-w-[180px] truncate">
        {data.label}
      </div>
    </div>
  );
});
