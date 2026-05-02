import type { Node, Edge } from "@xyflow/react";

export type GraphNodeData = {
  kind: "document" | "technology" | "alternative";
  label: string;
  status: string;
  vendor?: string;
  version?: string;
  category?: string;
  evidenceCount: number;
  sourceUrls: string[];
  mentions: import("@/types/contracts").TechnologyMention[];
  alternatives: import("@/types/contracts").AlternativeTechnology[];
  recommendation?: string;
  priorityScore?: number;
  [key: string]: unknown;
};

export type GraphFlowNode = Node<GraphNodeData>;
export type GraphFlowEdge = Edge;
