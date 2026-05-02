import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Sparkles } from "lucide-react";

import type { GraphNodeData } from "./types";

export const FlowNodeAlternative = memo(function FlowNodeAlternative(props: NodeProps) {
  const data = props.data as GraphNodeData;
  const selected = props.selected;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className={[
          "flex size-14 items-center justify-center rounded-full border-2 shadow-md transition-all",
          "bg-background text-emerald-600 border-emerald-400/70",
          "hover:shadow-[0_0_20px_rgba(16,185,129,0.4)] hover:scale-110",
          selected ? "ring-4 ring-emerald-400/30 scale-110 shadow-[0_0_20px_rgba(16,185,129,0.4)]" : "",
        ].join(" ")}
      >
        <Sparkles className="size-6" />
        <Handle type="target" position={Position.Left} className="opacity-0" />
        <Handle type="source" position={Position.Right} className="opacity-0" />
      </div>
      <div className="rounded-md bg-background/90 px-2 py-0.5 text-xs font-semibold text-foreground shadow-sm backdrop-blur whitespace-nowrap max-w-[180px] truncate">
        {data.label}
      </div>
    </div>
  );
});
