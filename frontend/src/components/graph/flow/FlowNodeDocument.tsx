import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Layers3 } from "lucide-react";

import type { GraphNodeData } from "./types";

export const FlowNodeDocument = memo(function FlowNodeDocument(props: NodeProps) {
  const data = props.data as GraphNodeData;
  const selected = props.selected;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className={[
          "flex size-16 items-center justify-center rounded-full border-2 shadow-lg transition-all",
          "bg-secondary text-secondary-foreground border-border",
          selected ? "ring-4 ring-primary/40 scale-110" : "",
        ].join(" ")}
      >
        <Layers3 className="size-7" />
        <Handle type="source" position={Position.Right} className="opacity-0" />
        <Handle type="source" position={Position.Bottom} className="opacity-0" />
        <Handle type="source" position={Position.Left} className="opacity-0" />
        <Handle type="source" position={Position.Top} className="opacity-0" />
      </div>
      <div className="rounded-md bg-background/90 px-2 py-0.5 text-xs font-semibold text-foreground shadow-sm backdrop-blur whitespace-nowrap">
        {data.label}
      </div>
    </div>
  );
});
