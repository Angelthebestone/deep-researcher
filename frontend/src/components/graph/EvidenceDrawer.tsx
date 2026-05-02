"use client";

import {
  Card,
  CardBody,
  Chip,
  Divider,
  ScrollShadow,
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from "@nextui-org/react";
import { FileCheck, ExternalLink, X, GitBranch } from "lucide-react";
import type { GraphNodeData } from "@/components/graph/flow/types";

interface EvidenceDrawerProps {
  node: GraphNodeData | null;
  onClose: () => void;
}

const kindColorMap: Record<
  GraphNodeData["kind"],
  "default" | "secondary" | "success"
> = {
  document: "default",
  technology: "secondary",
  alternative: "success",
};

export function EvidenceDrawer({ node, onClose }: EvidenceDrawerProps) {
  return (
    <div className="fixed top-0 right-0 h-full w-[380px] z-30 border-l border-border bg-background/95 backdrop-blur-md flex flex-col">
      {node ? (
        <>
          <div className="flex items-center justify-between gap-3 p-4 border-b border-border shrink-0">
            <div className="flex items-center gap-2 min-w-0">
              <h2 className="text-base font-semibold truncate text-foreground">
                {node.label}
              </h2>
              <Chip
                color={kindColorMap[node.kind]}
                variant="flat"
                size="sm"
              >
                {node.kind}
              </Chip>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full p-1.5 hover:bg-muted transition-colors shrink-0"
              aria-label="Cerrar panel"
            >
              <X className="size-4 text-muted-foreground" />
            </button>
          </div>

          <ScrollShadow className="flex-1 overflow-y-auto">
            <div className="p-4">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
                <GitBranch className="size-3.5" />
                Trazabilidad
              </div>
              <Table
                removeWrapper
                isCompact
                aria-label="Trazabilidad de menciones"
              >
                <TableHeader>
                  <TableColumn key="name">Nombre</TableColumn>
                  <TableColumn key="cat" className="w-16">
                    Cat.
                  </TableColumn>
                  <TableColumn key="vendor" className="w-24">
                    Prov./Ver.
                  </TableColumn>
                  <TableColumn key="conf" className="w-20">
                    Conf.
                  </TableColumn>
                  <TableColumn key="source">Fuente</TableColumn>
                </TableHeader>
                <TableBody emptyContent="Sin menciones">
                  {node.mentions.map((m) => (
                    <TableRow key={m.mention_id}>
                      <TableCell>
                        <span className="text-xs text-foreground">
                          {m.normalized_name}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {m.category}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {m.vendor ?? "-"} / {m.version ?? "-"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <div className="w-10 bg-muted rounded-full h-1.5 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-secondary"
                              style={{
                                width: `${Math.round(m.confidence * 100)}%`,
                              }}
                            />
                          </div>
                          <span className="text-[10px] text-muted-foreground tabular-nums">
                            {Math.round(m.confidence * 100)}%
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <a
                          href={m.source_uri}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-1 text-xs text-primary hover:underline"
                        >
                          <ExternalLink className="size-3 shrink-0" />
                          <span className="truncate max-w-[80px] inline-block align-bottom">
                            {m.source_uri}
                          </span>
                        </a>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <Divider />

            <div className="p-4">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
                <FileCheck className="size-3.5" />
                Evidencia
              </div>
              <div className="flex flex-col gap-2">
                {node.mentions
                  .flatMap((m) =>
                    m.evidence_spans.map((span) => ({
                      ...span,
                      source_uri: m.source_uri,
                      confidence: m.confidence,
                    }))
                  )
                  .map((item) => (
                    <div
                      key={item.evidence_id}
                      className="rounded-[1.25rem] border border-border bg-muted/30 p-3"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <Chip variant="flat" size="sm">
                            {item.evidence_type}
                          </Chip>
                          <span className="text-xs text-muted-foreground">
                            pág. {item.page_number}
                          </span>
                        </div>
                        <span className="text-[10px] text-muted-foreground tabular-nums">
                          {Math.round(item.confidence * 100)}%
                        </span>
                      </div>
                      {item.source_uri && (
                        <a
                          href={item.source_uri}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-1.5 text-xs text-primary hover:underline mt-1"
                        >
                          <ExternalLink className="size-3 shrink-0" />
                          <span className="truncate">{item.source_uri}</span>
                        </a>
                      )}
                    </div>
                  ))}
                {node.mentions.flatMap((m) => m.evidence_spans).length ===
                  0 && (
                  <span className="text-sm text-muted-foreground">
                    Sin evidence spans disponibles.
                  </span>
                )}
              </div>
            </div>

            <Divider />

            <div className="p-4">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
                <ExternalLink className="size-3.5" />
                Fuentes
              </div>
              <div className="flex flex-col gap-2">
                {Array.from(new Set(node.sourceUrls)).map((url) => (
                  <a
                    key={url}
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 text-sm text-primary hover:underline"
                  >
                    <ExternalLink className="size-3.5 shrink-0" />
                    <span className="truncate">{url}</span>
                  </a>
                ))}
                {node.sourceUrls.length === 0 && (
                  <span className="text-sm text-muted-foreground">
                    No hay fuentes disponibles.
                  </span>
                )}
              </div>
            </div>
          </ScrollShadow>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center h-full p-6 text-center">
          <GitBranch className="size-8 mb-3 text-muted-foreground/50" />
          <p className="text-sm text-muted-foreground">
            Selecciona un nodo para ver evidencia
          </p>
        </div>
      )}
    </div>
  );
}
