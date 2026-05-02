"use client";

import { Card, CardBody, Chip, Table, TableBody, TableCell, TableColumn, TableHeader, TableRow } from "@nextui-org/react";
import { ArrowRightLeft, Scale } from "lucide-react";
import type { AlternativeTechnology, TechnologyMention, TechnologyReport } from "@/types/contracts";

interface ComparatorModeProps {
  mentions: TechnologyMention[];
  report: TechnologyReport | null;
}

function statusColor(status: string): "success" | "warning" | "danger" | "default" {
  switch (status) {
    case "current":
      return "success";
    case "emerging":
      return "warning";
    case "deprecated":
      return "danger";
    default:
      return "default";
  }
}

type Row =
  | {
      kind: "primary";
      name: string;
      normalized_name: string;
      status: string;
      vendor: string;
      version: string;
      confidence: number;
      sources: number;
      versionGap?: string | null;
      recommendation?: string | null;
    }
  | {
      kind: "alternative";
      parent: string;
      alt: AlternativeTechnology;
    };

export function ComparatorMode({ mentions, report }: ComparatorModeProps) {
  const mentionMap = new Map(mentions.map((m) => [m.normalized_name, m]));

  const rows: Row[] = [];

  if (report?.comparisons?.length) {
    for (const comp of report.comparisons) {
      const mention = mentionMap.get(comp.normalized_name);
      rows.push({
        kind: "primary",
        name: comp.technology_name,
        normalized_name: comp.normalized_name,
        status: comp.market_status,
        vendor: mention?.vendor ?? "N/A",
        version: mention?.version ?? comp.current_version ?? "N/A",
        confidence: mention?.confidence ?? 0,
        sources: (mention?.evidence_spans?.length ?? 0) + (comp.source_urls?.length ?? 0),
        versionGap: comp.version_gap,
        recommendation: comp.recommendation_summary,
      });
      for (const alt of comp.alternatives ?? []) {
        rows.push({ kind: "alternative", parent: comp.normalized_name, alt });
      }
    }
  } else {
    for (const m of mentions) {
      rows.push({
        kind: "primary",
        name: m.technology_name,
        normalized_name: m.normalized_name,
        status: "unknown",
        vendor: m.vendor ?? "N/A",
        version: m.version ?? "N/A",
        confidence: m.confidence,
        sources: m.evidence_spans.length,
      });
    }
  }

  if (rows.length === 0) {
    return (
      <Card className="m-4">
        <CardBody className="text-center text-muted-foreground">
          No hay tecnologías para comparar.
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-2">
        <Scale className="size-5 text-primary" />
        <h2 className="text-lg font-semibold">Comparador de Tecnologías</h2>
      </div>
      <Card>
        <CardBody>
          <Table aria-label="Tabla comparativa de tecnologías" removeWrapper>
            <TableHeader>
              <TableColumn>Tecnología</TableColumn>
              <TableColumn>Estado</TableColumn>
              <TableColumn>Proveedor</TableColumn>
              <TableColumn>Versión</TableColumn>
              <TableColumn>Confianza</TableColumn>
              <TableColumn>Fuentes</TableColumn>
            </TableHeader>
            <TableBody>
              {rows.map((row, idx) =>
                row.kind === "primary" ? (
                  <TableRow key={`${row.normalized_name}-${idx}`}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <ArrowRightLeft className="size-4 text-primary" />
                        <span className="font-medium">{row.name}</span>
                      </div>
                      {row.recommendation ? (
                        <div className="mt-1 text-xs text-muted-foreground">{row.recommendation}</div>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Chip color={statusColor(row.status)} variant="flat" size="sm">
                        {row.status}
                      </Chip>
                    </TableCell>
                    <TableCell>{row.vendor}</TableCell>
                    <TableCell>
                      <span className={row.versionGap ? "text-warning font-semibold" : ""}>{row.version}</span>
                      {row.versionGap ? (
                        <span className="ml-2 text-xs text-warning">({row.versionGap})</span>
                      ) : null}
                    </TableCell>
                    <TableCell>{Math.round(row.confidence * 100)}%</TableCell>
                    <TableCell>{row.sources}</TableCell>
                  </TableRow>
                ) : (
                  <TableRow key={`alt-${row.alt.name}-${idx}`}>
                    <TableCell>
                      <div className="flex items-center gap-2 pl-6">
                        <Chip size="sm" color="success" variant="dot">
                          Alternativa
                        </Chip>
                        <span>{row.alt.name}</span>
                      </div>
                      <div className="pl-6 mt-1 text-xs text-muted-foreground">{row.alt.reason}</div>
                    </TableCell>
                    <TableCell>
                      <Chip color={statusColor(row.alt.status)} variant="flat" size="sm">
                        {row.alt.status}
                      </Chip>
                    </TableCell>
                    <TableCell className="text-muted-foreground">N/A</TableCell>
                    <TableCell className="text-muted-foreground">N/A</TableCell>
                    <TableCell className="text-muted-foreground">—</TableCell>
                    <TableCell>{row.alt.source_urls?.length ?? 0}</TableCell>
                  </TableRow>
                )
              )}
            </TableBody>
          </Table>
        </CardBody>
      </Card>
    </div>
  );
}
