"use client";

import { useMemo, useState } from "react";
import {
  BadgeCheck,
  ExternalLink,
  GitBranch,
  Info,
  Layers3,
  Link2,
  MapPin,
  Sparkles,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { AlternativeTechnology, DocumentMentionsResponse, TechnologyMention, TechnologyReport } from "@/types/contracts";
import { cn } from "@/lib/utils";

type KnowledgeGraphProps = {
  documentId: string | null;
  mentions: DocumentMentionsResponse | null;
  report: TechnologyReport | null;
};

type GraphNode = {
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

function statusTone(status: string) {
  if (status === "current" || status === "document") return "success";
  if (status === "emerging") return "warning";
  if (status === "deprecated") return "destructive";
  return "secondary";
}

function summarizeMentions(mentions: TechnologyMention[]) {
  if (!mentions.length) {
    return null;
  }
  const first = mentions[0];
  const evidenceSpans = mentions.flatMap((mention) => mention.evidence_spans);
  const sourceUrls = Array.from(new Set(mentions.map((mention) => mention.source_uri)));
  return {
    technologyName: first.technology_name,
    normalizedName: first.normalized_name,
    vendor: first.vendor ?? "n/a",
    version: first.version ?? "n/a",
    category: first.category,
    sourceUrls,
    evidenceSpans,
    mentions,
  };
}

export function KnowledgeGraph({ documentId, mentions, report }: KnowledgeGraphProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const technologyMentions = mentions?.normalized?.length ? mentions.normalized : mentions?.extracted ?? [];

  const nodes = useMemo(() => {
    const techNodes = groupMentions(technologyMentions);
    const altNodes = reportAlternativeNodes(report);
    return [documentNode(documentId), ...techNodes, ...altNodes];
  }, [documentId, report, technologyMentions]);

  const selectedNode = useMemo(() => nodes.find((node) => node.id === selectedId) ?? nodes[1] ?? nodes[0], [nodes, selectedId]);

  const selectedDetails = useMemo(() => {
    if (!selectedNode || selectedNode.kind === "document") {
      return null;
    }
    return summarizeMentions(selectedNode.mentions);
  }, [selectedNode]);
  const selectedAlternative = selectedNode?.kind === "alternative" ? selectedNode.alternatives[0] ?? null : null;

  return (
    <div className="flex h-full w-full relative overflow-hidden bg-white">
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
                onClick={() => setSelectedId(node.id)}
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

      <div className="relative z-10 w-[380px] border-l border-slate-200 bg-white/80 backdrop-blur-md shadow-[-10px_0_30px_rgba(0,0,0,0.03)] flex flex-col h-full ml-auto">
        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar flex flex-col gap-6">
            <div className="rounded-[1.75rem] border border-border bg-background/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    <Info className="size-3.5" />
                    Node details
                  </div>
                  <div className="mt-1 text-base font-semibold">{selectedNode?.label ?? "Selecciona un nodo"}</div>
                </div>
                <Badge variant={selectedNode ? (selectedNode.kind === "alternative" ? "success" : "secondary") : "outline"}>
                  {selectedNode?.kind ?? "none"}
                </Badge>
              </div>

              <Separator className="my-4" />

              {selectedDetails ? (
                <div className="flex flex-col gap-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                      <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Vendor</div>
                      <div className="mt-1 font-medium">{selectedDetails.vendor}</div>
                    </div>
                    <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                      <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Version</div>
                      <div className="mt-1 font-medium">{selectedDetails.version}</div>
                    </div>
                  </div>

                  <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Evidence</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedDetails.evidenceSpans.length ? (
                        selectedDetails.evidenceSpans.map((span) => (
                          <Badge key={span.evidence_id} variant="outline">
                            p.{span.page_number + 1} · {span.evidence_type}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-sm text-muted-foreground">Sin evidence_spans persistidos.</span>
                      )}
                    </div>
                  </div>

                  <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Source URLs</div>
                    <div className="mt-2 flex flex-col gap-2">
                      {selectedDetails.sourceUrls.length ? (
                        selectedDetails.sourceUrls.map((url) => (
                          <a
                            key={url}
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-2 text-sm text-primary hover:underline"
                          >
                            <ExternalLink className="size-3.5" />
                            <span className="truncate">{url}</span>
                          </a>
                        ))
                      ) : (
                        <span className="text-sm text-muted-foreground">No hay URLs persistidas.</span>
                      )}
                    </div>
                  </div>

                  <div className="rounded-[1.25rem] border border-border bg-background p-3">
                    <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                      <GitBranch className="size-3.5" />
                      Mentions
                    </div>
                    <div className="mt-2 text-sm text-muted-foreground">
                      {selectedDetails.mentions.length} mentions asociadas a {selectedDetails.normalizedName}.
                    </div>
                  </div>
                </div>
              ) : selectedAlternative ? (
                <div className="flex flex-col gap-4">
                  <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Alternative</div>
                    <div className="mt-1 font-medium">{selectedAlternative.name}</div>
                  </div>
                  <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Reason</div>
                    <p className="mt-2 text-sm text-foreground">{selectedAlternative.reason}</p>
                  </div>
                  <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Source URLs</div>
                    <div className="mt-2 flex flex-col gap-2">
                      {selectedAlternative.source_urls.length ? (
                        selectedAlternative.source_urls.map((url) => (
                          <a
                            key={url}
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-2 text-sm text-primary hover:underline"
                          >
                            <ExternalLink className="size-3.5" />
                            <span className="truncate">{url}</span>
                          </a>
                        ))
                      ) : (
                        <span className="text-sm text-muted-foreground">No hay URLs persistidas.</span>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-[1.25rem] border border-dashed border-border bg-muted/20 p-5 text-sm text-muted-foreground">
                  Selecciona un nodo de tecnologia o una alternativa para ver vendor, version, fuentes y evidence_spans.
                </div>
              )}
            </div>

            <div className="rounded-[1.75rem] border border-border bg-background/80 p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Reporte</div>
              <div className="mt-2 flex flex-col gap-2 text-sm">
                <div className="flex items-center gap-2">
                  <BadgeCheck className="size-4 text-success" />
                  <span>{report?.executive_summary ?? "El resumen ejecutivo se cargara al finalizar ReportGenerated."}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Layers3 className="size-4 text-primary" />
                  <span>{report?.technology_inventory.length ?? 0} tecnologias en el inventario final.</span>
                </div>
                <div className="flex items-center gap-2">
                  <Link2 className="size-4 text-primary" />
                  <span>{report?.sources.length ?? 0} fuentes consolidadas.</span>
                </div>
                {report?.metadata?.research_history?.length ? (
                  <div className="mt-3 rounded-[1.25rem] border border-border bg-muted/25 p-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Research trace</div>
                    <div className="mt-2 flex flex-col gap-2">
                      {report.metadata.research_history.slice(0, 3).map((item) => (
                        <div key={`${item.technology_name}-${item.breadth}-${item.depth}`} className="rounded-[1.25rem] border border-border bg-background p-3">
                          <div className="font-medium">{item.technology_name}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            breadth {item.breadth ?? "?"} · depth {item.depth ?? "?"} · {item.status}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
          </div>
        </div>
      </div>
    </div>
  );
}
