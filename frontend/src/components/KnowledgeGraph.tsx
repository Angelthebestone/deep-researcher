"use client";

import { useMemo, useState } from "react";
import {
  BadgeCheck,
  Layers3,
  Sparkles,
} from "lucide-react";

import type { AlternativeTechnology, DocumentMentionsResponse, TechnologyMention, TechnologyReport } from "@/types/contracts";
import { cn } from "@/lib/utils";

type KnowledgeGraphProps = {
  documentId: string | null;
  mentions: DocumentMentionsResponse | null;
  report: TechnologyReport | null;
  onNodeSelect?: (node: GraphNode | null) => void;
};

export type GraphNode = {
  id: string;
  label: string;
  kind: "document" | "technology" | "alternative";
  x: number;
  y: number;
  status: string;
  vendor?: string;
  version?: string;
  category?: string;
  evidenceCount: number;
  sourceUrls: string[];
  mentions: TechnologyMention[];
  alternatives: AlternativeTechnology[];
  recommendation?: string;
};

function groupMentions(mentions: TechnologyMention[]): GraphNode[] {
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
    const x = centerX + Math.cos(angle) * radiusX;
    const y = centerY + Math.sin(angle) * radiusY;
    return {
      id: representative.normalized_name,
      label: representative.normalized_name,
      kind: "technology",
      x,
      y,
      status: representative.category,
      vendor: representative.vendor,
      version: representative.version,
      category: representative.category,
      evidenceCount: items.reduce((accumulator, mention) => accumulator + mention.evidence_spans.length, 0),
      sourceUrls: Array.from(new Set(items.map((mention) => mention.source_uri))),
      mentions: items,
      alternatives: [],
      recommendation: "",
    };
  });
}

function reportAlternativeNodes(report: TechnologyReport | null): GraphNode[] {
  if (!report) {
    return [];
  }
  const alternatives = report.comparisons.flatMap((comparison) => comparison.alternatives ?? []);
  const unique = new Map<string, AlternativeTechnology>();
  alternatives.forEach((alternative) => {
    unique.set(`${alternative.name}:${alternative.status}`, alternative);
  });
  const items = [...unique.values()];
  const count = items.length || 1;
  return items.map((alternative, index) => {
    const angle = (index / count) * Math.PI * 2 - Math.PI / 3;
    return {
      id: `${alternative.name}-${alternative.status}`,
      label: alternative.name,
      kind: "alternative",
      x: 130 + Math.cos(angle) * 90,
      y: 390 + Math.sin(angle) * 60,
      status: alternative.status,
      evidenceCount: alternative.source_urls.length,
      sourceUrls: alternative.source_urls,
      mentions: [],
      alternatives: [alternative],
      recommendation: alternative.reason,
    };
  });
}

function documentNode(documentId: string | null): GraphNode {
  return {
    id: documentId ?? "document",
    label: documentId ?? "Documento activo",
    kind: "document",
    x: 120,
    y: 230,
    status: "document",
    evidenceCount: 0,
    sourceUrls: [],
    mentions: [],
    alternatives: [],
    recommendation: "Origen de todas las menciones y de la trazabilidad persistida.",
  };
}

export function KnowledgeGraph({ documentId, mentions, report, onNodeSelect }: KnowledgeGraphProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const technologyMentions = mentions?.normalized?.length ? mentions.normalized : mentions?.extracted ?? [];

  const nodes = useMemo(() => {
    const techNodes = groupMentions(technologyMentions);
    const altNodes = reportAlternativeNodes(report);
    return [documentNode(documentId), ...techNodes, ...altNodes];
  }, [documentId, report, technologyMentions]);

  const selectedNode = useMemo(() => nodes.find((node) => node.id === selectedId) ?? nodes[1] ?? nodes[0], [nodes, selectedId]);

  return (
    <div className="relative h-full w-full overflow-hidden bg-white">
      <div className="absolute inset-0 z-0">
        <div className="relative h-full w-full bg-[radial-gradient(circle_at_20%_20%,rgba(124,58,237,0.06),transparent_28%),radial-gradient(circle_at_80%_20%,rgba(16,185,129,0.04),transparent_25%)]">
          <div className="absolute inset-0 ai-grid opacity-20" />
          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 720 460" preserveAspectRatio="none">
            {nodes.slice(1).map((node) => (
              <g key={`edge-${node.id}`}>
                <line
                  x1={nodes[0].x}
                  y1={nodes[0].y}
                  x2={node.x}
                  y2={node.y}
                  stroke="rgba(148, 163, 184, 0.28)"
                  strokeWidth="2"
                  strokeDasharray={node.kind === "alternative" ? "4 4" : "0"}
                />
              </g>
            ))}
          </svg>

          <div className="absolute left-6 top-6 rounded-[1.5rem] border border-border/70 bg-background/85 px-4 py-3 shadow-soft backdrop-blur">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
              <Sparkles className="size-3.5" />
              Root document
            </div>
            <div className="mt-2 text-sm font-semibold">{documentId ?? "Documento no seleccionado"}</div>
            <p className="mt-1 max-w-[250px] text-xs text-muted-foreground">
              El grafo se actualiza con menciones persistidas y comparaciones del reporte final.
            </p>
          </div>

          {nodes.map((node) => (
            <button
              key={node.id}
              type="button"
              className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center justify-center gap-2 group transition-all outline-none"
              style={{ left: `${(node.x / 720) * 100}%`, top: `${(node.y / 460) * 100}%` }}
              onClick={() => {
                setSelectedId(node.id);
                onNodeSelect?.(node);
              }}
            >
              <div
                className={cn(
                  "flex size-14 items-center justify-center rounded-full border shadow-sm transition-all group-hover:shadow-[0_0_20px_rgba(124,58,237,0.6)] group-hover:scale-110",
                  node.kind === "document" && "border-slate-800 bg-slate-800 text-white shadow-lg",
                  node.kind === "technology" && "border-primary/40 bg-white text-primary",
                  node.kind === "alternative" && "border-emerald-400 bg-white text-emerald-600",
                  selectedNode?.id === node.id && "ring-4 ring-primary/30 scale-110 shadow-[0_0_20px_rgba(124,58,237,0.4)]"
                )}
              >
                {node.kind === "document" && <Layers3 className="size-6" />}
                {node.kind === "technology" && <BadgeCheck className="size-6" />}
                {node.kind === "alternative" && <Sparkles className="size-6" />}
              </div>
              <div className="rounded-md bg-white/90 px-2 py-0.5 text-xs font-semibold text-slate-700 shadow-sm backdrop-blur">
                {node.label}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
