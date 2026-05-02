"use client";

import { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Sparkles } from "lucide-react";

import type {
  AlternativeTechnology,
  DocumentMentionsResponse,
  TechnologyMention,
  TechnologyReport,
} from "@/types/contracts";
import { FlowNodeDocument } from "@/components/graph/flow/FlowNodeDocument";
import { FlowNodeTechnology } from "@/components/graph/flow/FlowNodeTechnology";
import { FlowNodeAlternative } from "@/components/graph/flow/FlowNodeAlternative";
import type { GraphNodeData } from "@/components/graph/flow/types";

type KnowledgeGraphProps = {
  documentId: string | null;
  mentions: DocumentMentionsResponse | null;
  report: TechnologyReport | null;
  onNodeSelect?: (node: GraphNodeData | null) => void;
};

const nodeTypes: NodeTypes = {
  document: FlowNodeDocument,
  technology: FlowNodeTechnology,
  alternative: FlowNodeAlternative,
};

function buildTechnologyNodes(mentions: TechnologyMention[]): Node<GraphNodeData>[] {
  const grouped = new Map<string, TechnologyMention[]>();
  for (const mention of mentions) {
    const key = mention.normalized_name.trim().toLowerCase() || mention.mention_id;
    const items = grouped.get(key) ?? [];
    items.push(mention);
    grouped.set(key, items);
  }

  const count = grouped.size || 1;
  const radiusX = 250;
  const radiusY = 155;
  const centerX = 360;
  const centerY = 230;

  return [...grouped.values()].map((items, index) => {
    const representative = items[0];
    const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
    return {
      id: representative.normalized_name,
      type: "technology",
      position: {
        x: centerX + Math.cos(angle) * radiusX,
        y: centerY + Math.sin(angle) * radiusY,
      },
      data: {
        kind: "technology",
        label: representative.normalized_name,
        status: representative.category,
        vendor: representative.vendor,
        version: representative.version,
        category: representative.category,
        evidenceCount: items.reduce((acc, m) => acc + m.evidence_spans.length, 0),
        sourceUrls: Array.from(new Set(items.map((m) => m.source_uri))),
        mentions: items,
        alternatives: [],
      },
    };
  });
}

function buildAlternativeNodes(report: TechnologyReport | null): Node<GraphNodeData>[] {
  if (!report) return [];
  const alternatives = report.comparisons.flatMap((c) => c.alternatives ?? []);
  const unique = new Map<string, AlternativeTechnology>();
  alternatives.forEach((alt) => unique.set(`${alt.name}:${alt.status}`, alt));
  const items = [...unique.values()];
  const count = items.length || 1;

  return items.map((alt, index) => {
    const angle = (index / count) * Math.PI * 2 - Math.PI / 3;
    return {
      id: `${alt.name}-${alt.status}`,
      type: "alternative",
      position: {
        x: 130 + Math.cos(angle) * 90,
        y: 390 + Math.sin(angle) * 60,
      },
    data: {
      kind: "alternative",
      label: alt.name,
      status: alt.status,
        evidenceCount: alt.source_urls.length,
        sourceUrls: alt.source_urls,
        mentions: [],
        alternatives: [alt],
        recommendation: alt.reason,
      },
    };
  });
}

function buildDocumentNode(documentId: string | null): Node<GraphNodeData> {
  return {
    id: "document",
    type: "document",
    position: { x: 120, y: 230 },
    data: {
      kind: "document",
      label: documentId ?? "Documento activo",
      status: "document",
      evidenceCount: 0,
      sourceUrls: [],
      mentions: [],
      alternatives: [],
      recommendation: "Origen de todas las menciones y de la trazabilidad persistida.",
    },
  };
}

function buildEdges(nodes: Node<GraphNodeData>[]): Edge[] {
  const documentNode = nodes.find((n) => n.type === "document");
  if (!documentNode) return [];

  return nodes
    .filter((n) => n.type !== "document")
    .map((node) => ({
      id: `edge-${documentNode.id}-${node.id}`,
      source: documentNode.id,
      target: node.id,
      style: node.type === "alternative" ? { strokeDasharray: "4 4" } : undefined,
    }));
}

export function KnowledgeGraph({ documentId, mentions, report, onNodeSelect }: KnowledgeGraphProps) {
  const technologyMentions = mentions?.normalized?.length ? mentions.normalized : mentions?.extracted ?? [];

  const initialNodes = useMemo(() => {
    const doc = buildDocumentNode(documentId);
    const techs = buildTechnologyNodes(technologyMentions);
    const alts = buildAlternativeNodes(report);
    return [doc, ...techs, ...alts];
  }, [documentId, report, technologyMentions]);

  const initialEdges = useMemo(() => buildEdges(initialNodes), [initialNodes]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useMemo(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node<GraphNodeData>) => {
      onNodeSelect?.(node.data);
    },
    [onNodeSelect],
  );

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={48} size={1} className="ai-grid opacity-20" />
        <Controls />
        <MiniMap
          nodeStrokeWidth={3}
          className="!bg-background/80 !border-border"
          maskColor="rgba(0,0,0,0.1)"
        />
      </ReactFlow>

      <div className="absolute left-6 top-6 z-10 rounded-[1.5rem] border border-border/70 bg-background/85 px-4 py-3 shadow-soft backdrop-blur">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
          <Sparkles className="size-3.5" />
          Documento raíz
        </div>
        <div className="mt-2 text-sm font-semibold">{documentId ?? "Documento no seleccionado"}</div>
        <p className="mt-1 max-w-[250px] text-xs text-muted-foreground">
          El grafo se actualiza con menciones persistidas y comparaciones del reporte final.
        </p>
      </div>
    </div>
  );
}
