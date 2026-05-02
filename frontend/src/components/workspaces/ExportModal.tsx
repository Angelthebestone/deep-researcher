"use client";

import { useState, useMemo } from "react";
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  Tabs,
  Tab,
  Chip,
} from "@nextui-org/react";
import {
  Download,
  FileJson,
  FileSpreadsheet,
  FileText,
  Printer,
} from "lucide-react";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { exportDocument } from "@/lib/api";
import type { Workspace } from "@/types/workspace";
import type { TechnologyMention } from "@/types/contracts";

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId: string;
}

function escapeCsv(value: string | number | undefined): string {
  const str = String(value ?? "");
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function generateCsv(mentions: TechnologyMention[]): string {
  const headers = [
    "normalized_name",
    "category",
    "vendor",
    "version",
    "confidence_score",
    "source_uri",
    "page_number",
  ];
  const rows = mentions.map((m) => [
    m.normalized_name,
    m.category,
    m.vendor ?? "",
    m.version ?? "",
    m.confidence,
    m.source_uri,
    m.page_number,
  ]);
  return [
    headers.join(","),
    ...rows.map((r) => r.map(escapeCsv).join(",")),
  ].join("\n");
}

function generateMarkdown(workspace: Workspace): string {
  const totalEvidence = workspace.mentions.reduce(
    (sum, m) => sum + m.evidence_spans.length,
    0
  );
  const lines: string[] = [];
  lines.push(`# Reporte de Workspace: ${workspace.name}`);
  lines.push("");
  lines.push(`**Estado:** ${workspace.status}`);
  lines.push(`**Generado:** ${new Date().toLocaleString("es-ES")}`);
  lines.push("");
  lines.push(`## Menciones Tecnológicas (${workspace.mentions.length})`);
  lines.push("");
  workspace.mentions.forEach((m) => {
    lines.push(`### ${m.normalized_name}`);
    lines.push("");
    lines.push(`- **Categoría:** ${m.category}`);
    lines.push(`- **Proveedor:** ${m.vendor || "N/A"}`);
    lines.push(`- **Versión:** ${m.version || "N/A"}`);
    lines.push(`- **Confianza:** ${(m.confidence * 100).toFixed(1)}%`);
    lines.push(`- **Fuente:** ${m.source_uri}`);
    lines.push(`- **Página:** ${m.page_number}`);
    lines.push("");
    if (m.evidence_spans.length > 0) {
      lines.push("**Evidencias:**");
      m.evidence_spans.forEach((e) => {
        lines.push(`- [${e.evidence_type}] Pág. ${e.page_number}: ${e.text}`);
      });
      lines.push("");
    }
  });
  lines.push("## Resumen de Evidencias");
  lines.push("");
  lines.push(`- **Total de menciones:** ${workspace.mentions.length}`);
  lines.push(`- **Total de evidencias:** ${totalEvidence}`);
  lines.push("");
  return lines.join("\n");
}

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function ExportModal({ isOpen, onClose, workspaceId }: ExportModalProps) {
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const workspace = useMemo(
    () => workspaces.find((w) => w.id === workspaceId) ?? null,
    [workspaces, workspaceId]
  );
  const [selectedFormat, setSelectedFormat] = useState<string>("json");
  const [isLoading, setIsLoading] = useState(false);

  const handleDownload = async () => {
    if (!workspace) return;

    const documentId = workspace.currentDocument?.document_id;

    if (documentId && selectedFormat !== "pdf") {
      setIsLoading(true);
      try {
        const format = selectedFormat as "json" | "csv" | "markdown";
        const blob = await exportDocument(documentId, format);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${workspace.name}-${format === "markdown" ? "md" : format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        return;
      } catch {
        // Fallback to client-side generation on backend error
      } finally {
        setIsLoading(false);
      }
    }

    if (selectedFormat === "json") {
      const content = JSON.stringify(workspace, null, 2);
      downloadFile(content, `${workspace.name}.json`, "application/json");
    } else if (selectedFormat === "csv") {
      const content = generateCsv(workspace.mentions);
      downloadFile(content, `${workspace.name}.csv`, "text/csv;charset=utf-8;");
    } else if (selectedFormat === "markdown") {
      const content = generateMarkdown(workspace);
      downloadFile(content, `${workspace.name}.md`, "text/markdown");
    }
  };

  const isPdf = selectedFormat === "pdf";

  return (
    <Modal
      isOpen={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      size="lg"
    >
      <ModalContent>
        <ModalHeader className="text-foreground">
          Exportar Workspace
        </ModalHeader>
        <ModalBody>
          {!workspace ? (
            <p className="text-sm text-muted-foreground">
              Workspace no encontrado
            </p>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Selecciona el formato de exportación para{" "}
                <span className="font-medium text-foreground">
                  {workspace.name}
                </span>
              </p>
              <Tabs
                fullWidth
                size="sm"
                selectedKey={selectedFormat}
                onSelectionChange={(key) => setSelectedFormat(String(key))}
                aria-label="Formatos de exportación"
              >
                <Tab
                  key="json"
                  title={
                    <div className="flex items-center gap-1.5">
                      <FileJson className="size-4" />
                      <span>JSON</span>
                    </div>
                  }
                >
                  <div className="py-2 text-sm text-muted-foreground">
                    Exporta el workspace completo como archivo JSON.
                  </div>
                </Tab>
                <Tab
                  key="csv"
                  title={
                    <div className="flex items-center gap-1.5">
                      <FileSpreadsheet className="size-4" />
                      <span>CSV</span>
                    </div>
                  }
                >
                  <div className="py-2 text-sm text-muted-foreground">
                    Exporta las menciones en formato CSV con las columnas
                    definidas.
                  </div>
                </Tab>
                <Tab
                  key="markdown"
                  title={
                    <div className="flex items-center gap-1.5">
                      <FileText className="size-4" />
                      <span>Markdown</span>
                    </div>
                  }
                >
                  <div className="py-2 text-sm text-muted-foreground">
                    Genera un reporte en Markdown con nombre, estado, menciones
                    y evidencias.
                  </div>
                </Tab>
                <Tab
                  key="pdf"
                  title={
                    <div className="flex items-center gap-1.5">
                      <Printer className="size-4" />
                      <span>PDF</span>
                    </div>
                  }
                >
                  <div className="py-2 flex items-center gap-2 text-sm text-muted-foreground">
                    <Chip size="sm" variant="flat" color="warning">
                      Próximamente
                    </Chip>
                    <span>
                      La exportación a PDF estará disponible en una futura
                      versión.
                    </span>
                  </div>
                </Tab>
              </Tabs>
            </div>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onPress={onClose}>
            Cerrar
          </Button>
          <Button
            color="primary"
            startContent={<Download className="size-4" />}
            onPress={handleDownload}
            isDisabled={!workspace || isPdf}
            isLoading={isLoading}
          >
            Descargar
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
