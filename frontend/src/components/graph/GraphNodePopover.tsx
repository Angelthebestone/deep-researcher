"use client";

import { Popover, PopoverTrigger, PopoverContent, Chip, Divider } from "@nextui-org/react";
import { ExternalLink, GitBranch, Info } from "lucide-react";
import type { GraphNode } from "@/components/KnowledgeGraph";

interface GraphNodePopoverProps {
  node: GraphNode | null;
  onClose: () => void;
}

function summarizeMentions(node: GraphNode) {
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
  if (!node) return null;

  const details = node.kind === "technology" ? summarizeMentions(node) : null;
  const alternative = node.kind === "alternative" ? node.alternatives[0] ?? null : null;

  const left = `${(node.x / 720) * 100}%`;
  const top = `${(node.y / 460) * 100}%`;

  return (
    <Popover isOpen onOpenChange={(open) => { if (!open) onClose(); }} placement="right">
      <PopoverTrigger>
        <button
          type="button"
          className="absolute -translate-x-1/2 -translate-y-1/2 w-1 h-1 p-0 border-0 bg-transparent"
          style={{ left, top }}
          aria-hidden="true"
        />
      </PopoverTrigger>
      <PopoverContent className="backdrop-blur-xl bg-white/80 border-0 shadow-soft w-80 p-4">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                <Info className="size-3.5" />
                Node details
              </div>
              <div className="mt-1 text-base font-semibold">{node.label}</div>
            </div>
            <Chip color={node.kind === "alternative" ? "success" : "secondary"} variant="flat" size="sm">
              {node.kind}
            </Chip>
          </div>

          <Divider />

          {details ? (
            <div className="flex flex-col gap-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Vendor</div>
                  <div className="mt-1 font-medium">{details.vendor}</div>
                </div>
                <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Version</div>
                  <div className="mt-1 font-medium">{details.version}</div>
                </div>
              </div>

              <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Evidence</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {details.evidenceSpans.length ? (
                    details.evidenceSpans.map((span) => (
                      <Chip key={span.evidence_id} variant="bordered" size="sm">
                        p.{span.page_number + 1} · {span.evidence_type}
                      </Chip>
                    ))
                  ) : (
                    <span className="text-sm text-muted-foreground">Sin evidence_spans persistidos.</span>
                  )}
                </div>
              </div>

              <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Source URLs</div>
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
                  Mentions
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {details.mentions.length} mentions asociadas a {details.normalizedName}.
                </div>
              </div>
            </div>
          ) : alternative ? (
            <div className="flex flex-col gap-4">
              <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Alternative</div>
                <div className="mt-1 font-medium">{alternative.name}</div>
              </div>
              <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Reason</div>
                <p className="mt-2 text-sm text-foreground">{alternative.reason}</p>
              </div>
              <div className="rounded-[1.25rem] border border-border bg-muted/30 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Source URLs</div>
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
            </div>
          ) : (
            <div className="rounded-[1.25rem] border border-dashed border-border bg-muted/20 p-5 text-sm text-muted-foreground">
              Selecciona un nodo de tecnologia o una alternativa para ver vendor, version, fuentes y evidence_spans.
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
