"use client";

import { useState } from "react";
import { Card, CardBody, Chip, Divider } from "@nextui-org/react";
import { ExternalLink, GitBranch, Info, X, Gavel } from "lucide-react";
import { DecisionPanel, getNodeDecisions, statusColorMap } from "./DecisionPanel";
import type { GraphNodeData } from "@/components/graph/flow/types";

interface GraphNodePopoverProps {
  node: GraphNodeData | null;
  onClose: () => void;
}

function summarizeMentions(node: GraphNodeData) {
  if (!node.mentions.length) return null;
  const first = node.mentions[0];
  const evidenceSpans = node.mentions.flatMap((m) => m.evidence_spans);
  const sourceUrls = Array.from(new Set(node.mentions.map((m) => m.source_uri)));
  return {
    vendor: first.vendor ?? "n/a",
    version: first.version ?? "n/a",
    category: first.category,
    sourceUrls,
    evidenceSpans,
    mentions: node.mentions,
    normalizedName: first.normalized_name,
  };
}

export function GraphNodePopover({ node, onClose }: GraphNodePopoverProps) {
  const [activeTab, setActiveTab] = useState<"detalles" | "decisiones">("detalles");

  if (!node) return null;
  const nodeDecisions = getNodeDecisions(node.label);
  const latestDecision = nodeDecisions[nodeDecisions.length - 1];

  const details = node.kind === "technology" ? summarizeMentions(node) : null;
  const alternative = node.kind === "alternative" ? node.alternatives[0] ?? null : null;

  return (
    <Card className="absolute right-6 top-6 z-20 w-80 border-0 shadow-soft bg-background/85 backdrop-blur-md">
      <CardBody className="p-4">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div>
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
              <Info className="size-3.5" />
              Detalles del nodo
            </div>
            <div className="mt-1 text-base font-semibold">{node.label}</div>
          </div>
          <div className="flex items-center gap-2">
            <Chip color={node.kind === "alternative" ? "success" : "secondary"} variant="flat" size="sm">
              {node.kind}
            </Chip>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full p-1 hover:bg-muted transition-colors"
              aria-label="Cerrar detalles"
            >
              <X className="size-4 text-muted-foreground" />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 mb-3">
          <button
            type="button"
            onClick={() => setActiveTab("detalles")}
            className={`text-xs uppercase tracking-[0.18em] px-3 py-1 rounded-full transition-colors ${
              activeTab === "detalles" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
            }`}
          >
            Detalles
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("decisiones")}
            className={`text-xs uppercase tracking-[0.18em] px-3 py-1 rounded-full transition-colors flex items-center gap-1.5 ${
              activeTab === "decisiones" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
            }`}
          >
            <Gavel className="size-3" />
            Decisiones
            {latestDecision && (
              <Chip size="sm" color={statusColorMap[latestDecision.status]} variant="flat" className="ml-0.5">
                {latestDecision.status}
              </Chip>
            )}
          </button>
        </div>

        <Divider />

        {activeTab === "detalles" ? (
          <div className="flex flex-col gap-3 mt-3">
          {details ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Proveedor</div>
                  <div className="mt-1 font-medium">{details.vendor}</div>
                </div>
                <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Versión</div>
                  <div className="mt-1 font-medium">{details.version}</div>
                </div>
              </div>

              <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Evidencia</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {details.evidenceSpans.length ? (
                    details.evidenceSpans.map((span) => (
                      <Chip key={span.evidence_id} variant="bordered" size="sm">
                        pág.{span.page_number + 1} · {span.evidence_type}
                      </Chip>
                    ))
                  ) : (
                    <span className="text-sm text-muted-foreground">Sin evidence_spans persistidos.</span>
                  )}
                </div>
              </div>

              <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">URLs de fuentes</div>
                <div className="mt-2 flex flex-col gap-2">
                  {details.sourceUrls.length ? (
                    details.sourceUrls.map((url) => (
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
                  Menciones
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {details.mentions.length} menciones asociadas a {details.normalizedName}.
                </div>
              </div>
            </>
          ) : alternative ? (
            <>
              <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Alternativa</div>
                <div className="mt-1 font-medium">{alternative.name}</div>
              </div>
              <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Razón</div>
                <p className="mt-2 text-sm text-foreground">{alternative.reason}</p>
              </div>
              <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">URLs de fuentes</div>
                <div className="mt-2 flex flex-col gap-2">
                  {alternative.source_urls.length ? (
                    alternative.source_urls.map((url) => (
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
            </>
          ) : (
            <div className="rounded-[1.25rem] border border-dashed border-border bg-muted/20 p-5 text-sm text-muted-foreground">
              Selecciona un nodo de tecnología o una alternativa para ver proveedor, versión, fuentes y evidence_spans.
            </div>
          )}
        </div>
        ) : (
          <div className="mt-3">
            <DecisionPanel node={node} isOpen={true} onClose={() => setActiveTab("detalles")} />
          </div>
        )}
      </CardBody>
    </Card>
  );
}
