"use client";

import { useMemo } from "react";
import { Download, Printer, ShieldAlert, Sparkles, Target } from "lucide-react";

import { Chip } from "@nextui-org/react";
import { Button } from "@nextui-org/react";
import { Card, CardBody, CardHeader, CardFooter } from "@nextui-org/react";
import { Divider } from "@nextui-org/react";
import { apiBaseUrl } from "@/lib/api";
import type { TechnologyReport } from "@/types/contracts";

type ReportSectionProps = {
  documentId: string | null;
  report: TechnologyReport | null;
  onExportPdf: () => void;
};

function severityTone(value: string) {
  if (value === "critical" || value === "high") {
    return "danger";
  }
  if (value === "medium") {
    return "secondary";
  }
  return "default";
}

export function ReportSection({ documentId, report, onExportPdf }: ReportSectionProps) {
  const metrics = useMemo(
    () => [
      { label: "Technologies", value: report?.technology_inventory.length ?? 0 },
      { label: "Risks", value: report?.risks.length ?? 0 },
      { label: "Recommendations", value: report?.recommendations.length ?? 0 },
      { label: "Sources", value: report?.sources.length ?? 0 },
    ],
    [report],
  );

  return (
    <Card className="ai-panel overflow-hidden border-border/70 shadow-soft">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h3 className="font-display text-xl">Veredicto final</h3>
            <p className="text-sm text-muted-foreground">Executive summary, riesgos, recomendaciones y fuentes verificables.</p>
          </div>
          <div data-report-actions className="flex flex-wrap gap-2">
            <Button
              variant="bordered"
              size="sm"
              startContent={<Download className="size-4" />}
              disabled={!documentId}
              onClick={() => {
                if (!documentId) {
                  return;
                }
                window.open(
                  `${apiBaseUrl()}/api/v1/documents/${encodeURIComponent(documentId)}/report/download`,
                  "_blank",
                  "noopener,noreferrer",
                );
              }}
            >
              Markdown
            </Button>
            <Button color="secondary" variant="flat" size="sm" startContent={<Printer className="size-4" />} disabled={!report} onClick={onExportPdf}>
              PDF
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardBody className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => (
            <div key={metric.label} className="rounded-[1.5rem] border border-border bg-background/70 p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{metric.label}</div>
              <div className="mt-1 text-2xl font-semibold">{metric.value}</div>
            </div>
          ))}
        </div>

        <div className="rounded-[1.75rem] border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(250,250,255,0.82))] p-5">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
            <Sparkles className="size-3.5" />
            Executive summary
          </div>
          <p className="mt-3 text-sm leading-7 text-foreground">
            {report?.executive_summary ?? "Esperando el reporte final."}
          </p>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-[1.75rem] border border-border bg-background/80 p-5">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
              <ShieldAlert className="size-3.5" />
              Risks
            </div>
            <div className="mt-4 flex flex-col gap-3">
              {report?.risks?.length ? (
                report.risks.map((risk) => (
                  <div
                    key={`${risk.technology_name}-${risk.severity}`}
                    className="rounded-[1.25rem] border border-border bg-muted/25 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium">{risk.technology_name}</div>
                      <Chip color={severityTone(risk.severity)} variant="flat" size="sm">{risk.severity}</Chip>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{risk.description}</p>
                    {risk.source_urls?.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {risk.source_urls.map((url) => (
                          <a
                            key={url}
                            href={url}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded-full border border-border px-3 py-1 text-xs text-primary hover:bg-primary/5"
                          >
                            {url}
                          </a>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))
              ) : (
                <div className="rounded-[1.25rem] border border-dashed border-border p-4 text-sm text-muted-foreground">
                  Los riesgos aparecen cuando se completa la investigacion.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[1.75rem] border border-border bg-background/80 p-5">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
              <Target className="size-3.5" />
              Recommendations
            </div>
            <div className="mt-4 flex flex-col gap-3">
              {report?.recommendations?.length ? (
                report.recommendations.map((recommendation) => (
                  <div
                    key={`${recommendation.technology_name}-${recommendation.priority}`}
                    className="rounded-[1.25rem] border border-border bg-muted/25 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium">{recommendation.technology_name}</div>
                      <Chip color="success" variant="flat" size="sm">{recommendation.priority}</Chip>
                    </div>
                    <p className="mt-2 text-sm font-medium text-foreground">{recommendation.action}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{recommendation.rationale}</p>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <Chip variant="bordered" size="sm">Effort {recommendation.effort}</Chip>
                      <Chip variant="bordered" size="sm">Impact {recommendation.impact}</Chip>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-[1.25rem] border border-dashed border-border p-4 text-sm text-muted-foreground">
                  Las recomendaciones se llenan con el reporte persistido.
                </div>
              )}
            </div>
          </div>
        </div>

        <Divider />

        <div className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-[1.75rem] border border-border bg-background/80 p-5">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Technology inventory</div>
            <div className="mt-4 flex flex-col gap-3">
              {report?.technology_inventory?.length ? (
                report.technology_inventory.map((item) => (
                  <div
                    key={`${item.normalized_name}-${item.mention_count}`}
                    className="rounded-[1.25rem] border border-border bg-muted/25 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="font-medium">{item.normalized_name}</div>
                        <div className="text-xs text-muted-foreground">{item.technology_name}</div>
                      </div>
                      <Chip color={item.status === "current" ? "success" : item.status === "emerging" ? "secondary" : "default"} variant={item.status === "current" ? "flat" : item.status === "emerging" ? "flat" : "bordered"} size="sm">
                        {item.category}
                      </Chip>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>Mentions: {item.mention_count}</span>
                      <span>Vendor: {item.vendor ?? "n/a"}</span>
                      <span>Version: {item.current_version ?? "n/a"}</span>
                    </div>
                    {item.evidence_ids?.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.evidence_ids.map((id) => (
                          <Chip key={id} variant="bordered" size="sm">
                            {id}
                          </Chip>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))
              ) : (
                <div className="rounded-[1.25rem] border border-dashed border-border p-4 text-sm text-muted-foreground">
                  Sin inventario todavia.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[1.75rem] border border-border bg-background/80 p-5">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Sources</div>
            <div className="mt-4 flex flex-col gap-3">
              {report?.sources?.length ? (
                report.sources.map((source) => (
                  <a
                    key={`${source.url}-${source.title}`}
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    className="block rounded-[1.25rem] border border-border bg-muted/25 p-4 transition-colors hover:bg-muted/50"
                  >
                    <div className="font-medium">{source.title}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{source.url}</div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <Chip variant="bordered" size="sm">{source.source_type ?? "source"}</Chip>
                      <span>{source.retrieved_at}</span>
                    </div>
                  </a>
                ))
              ) : (
                <div className="rounded-[1.25rem] border border-dashed border-border p-4 text-sm text-muted-foreground">
                  Las fuentes apareceran al generar el reporte final.
                </div>
              )}
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
