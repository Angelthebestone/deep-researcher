"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { FileUp, LoaderCircle, Sparkles } from "lucide-react";

import { Chip } from "@nextui-org/react";
import { Button } from "@nextui-org/react";
import { Card, CardBody, CardHeader, CardFooter } from "@nextui-org/react";
import { Input } from "@nextui-org/react";
import { Progress } from "@nextui-org/react";
import { apiBaseUrl, uploadDocument } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DocumentUploadResponse, SourceType } from "@/types/contracts";

type DocumentIngestProps = {
  onUploaded: (document: DocumentUploadResponse) => void;
  onUploadError?: (message: string) => void;
  currentDocument: DocumentUploadResponse | null;
  compact?: boolean;
};

const SOURCE_TYPES: SourceType[] = ["pdf", "image", "docx", "pptx", "sheet", "text"];

function sourceTypeFromFilename(filename: string): SourceType {
  const extension = filename.split(".").pop()?.toLowerCase() ?? "";
  if (extension === "pdf") return "pdf";
  if (["png", "jpg", "jpeg", "bmp", "gif", "tif", "tiff", "webp"].includes(extension)) return "image";
  if (extension === "docx") return "docx";
  if (extension === "pptx") return "pptx";
  if (["xlsx", "xlsm", "csv", "tsv"].includes(extension)) return "sheet";
  return "text";
}

function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = typeof reader.result === "string" ? reader.result : "";
      const index = value.indexOf(",");
      resolve(index >= 0 ? value.slice(index + 1) : value);
    };
    reader.onerror = () => reject(new Error("No se pudo leer el archivo."));
    reader.readAsDataURL(file);
  });
}

export function DocumentIngest({ onUploaded, onUploadError, currentDocument, compact = false }: DocumentIngestProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedSourceType, setSelectedSourceType] = useState<SourceType | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string>("");
  const [note, setNote] = useState("Arrastra un PDF, imagen o documento para crear un document_id estable.");
  const [progress, setProgress] = useState(0);

  const stageState = useMemo(() => {
    if (!currentDocument) {
      return {
        uploaded: false,
        parsed: false,
      };
    }
    return {
      uploaded: true,
      parsed: true,
    };
  }, [currentDocument]);

  const handleFiles = useCallback(
    async (files: FileList | File[] | null) => {
      const file = files?.[0];
      if (!file || uploading) {
        return;
      }
      const inferredSourceType = sourceTypeFromFilename(file.name);
      const resolvedSourceType = selectedSourceType ?? inferredSourceType;
      setSelectedFileName(file.name);
      setSelectedSourceType(resolvedSourceType);
      setUploading(true);
      setProgress(8);
      setNote(`Subiendo ${file.name} a ${apiBaseUrl()}.`);

      try {
        const content = await toBase64(file);
        setProgress(36);
        const response = await uploadDocument({
          filename: file.name,
          content,
          source_type: resolvedSourceType,
        });
        setProgress(100);
        setNote(`Documento ${response.document_id} cargado y parseado.`);
        onUploaded(response);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Error desconocido al subir el documento.";
        setNote(message);
        onUploadError?.(message);
      } finally {
        setUploading(false);
        setTimeout(() => setProgress(0), 800);
      }
    },
    [onUploadError, onUploaded, selectedSourceType, uploading],
  );

  return (
    <Card
      className={cn(
        "ai-panel overflow-hidden border-border/70 shadow-soft",
        dragActive && "border-primary/40 shadow-[0_0_0_1px_rgba(124,58,237,0.2),0_20px_60px_rgba(124,58,237,0.06)]",
      )}
    >
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h3 className={cn("font-display", compact ? "text-lg" : "text-xl")}>Ingesta multimodal</h3>
            <p className="text-sm text-muted-foreground">
              {compact
                ? "Carga un artefacto sin salir del flujo de chat."
                : "Arrastra un PDF, imagen o documento y el agente preserva el mismo `document_id` para cada reintento."}
            </p>
          </div>
          <Chip color={stageState.parsed ? "success" : "secondary"} variant="flat" size="sm">
            {stageState.parsed ? "PARSED" : "UPLOADED"}
          </Chip>
        </div>
      </CardHeader>
      <CardBody className={cn("flex flex-col", compact ? "gap-3" : "gap-4")}>
        <label
          className={cn(
            "group flex cursor-pointer flex-col items-center justify-center rounded-[2rem] border border-dashed border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(250,250,255,0.74))] px-6 text-center transition-all",
            compact ? "min-h-40 py-6" : "min-h-56",
            dragActive && "border-primary bg-primary/5 shadow-[0_0_0_1px_rgba(124,58,237,0.18),0_24px_60px_rgba(124,58,237,0.08)]",
          )}
          onDragEnter={() => setDragActive(true)}
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragActive(false);
            void handleFiles(event.dataTransfer.files);
          }}
        >
          <input ref={inputRef} type="file" className="hidden" onChange={(event) => void handleFiles(event.target.files)} />
          <div className={cn("mb-4 flex items-center justify-center rounded-[1.4rem] bg-primary/10 text-primary shadow-[0_14px_35px_rgba(124,58,237,0.12)]", compact ? "size-12" : "size-16")}>
            <FileUp className={cn(compact ? "size-5" : "size-6")} />
          </div>
          <p className={cn("font-semibold text-foreground", compact ? "text-base" : "text-lg")}>Suelta el documento o abre un archivo</p>
          <p className={cn("max-w-lg text-muted-foreground", compact ? "mt-1 text-xs leading-5" : "mt-2 text-sm leading-6")}>{note}</p>
          <div className={cn("flex flex-wrap items-center justify-center gap-2", compact ? "mt-4" : "mt-6")}>
            {SOURCE_TYPES.map((sourceType) => (
              <Button
                key={sourceType}
                variant={selectedSourceType === sourceType ? "solid" : "bordered"}
                size="sm"
                onClick={(event) => {
                  event.preventDefault();
                  setSelectedSourceType(sourceType);
                  inputRef.current?.click();
                }}
              >
                {sourceType.toUpperCase()}
              </Button>
            ))}
          </div>
        </label>

        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
          <Input value={selectedFileName} readOnly placeholder="No hay archivo seleccionado" className="bg-background/80" />
          <Button
            color="secondary" variant="flat" size="sm"
            onClick={() => inputRef.current?.click()}
            startContent={uploading ? <LoaderCircle className="animate-spin size-4" /> : <Sparkles className="size-4" />}
          >
            {uploading ? "Procesando" : "Seleccionar"}
          </Button>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs uppercase tracking-[0.18em] text-muted-foreground">
            <span>UPLOADED</span>
            <span>PARSED</span>
          </div>
          <Progress value={progress || (stageState.parsed ? 100 : 0)} />
        </div>

        <div className={cn("grid gap-3", compact ? "sm:grid-cols-1" : "sm:grid-cols-2")}>
          <div className="rounded-[1.5rem] border border-border bg-background/70 p-4">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Estado</div>
            <div className="mt-1 font-medium">{currentDocument ? currentDocument.document_id : "Esperando upload"}</div>
          </div>
          {!compact ? (
            <div className="rounded-[1.5rem] border border-border bg-background/70 p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Trazabilidad</div>
              <div className="mt-1 font-medium">{currentDocument ? `${currentDocument.page_count} paginas` : "Sin artefacto"}</div>
            </div>
          ) : null}
        </div>

        {currentDocument ? (
          <div className="rounded-[1.5rem] border border-success/20 bg-success/5 p-4">
            <div className="text-xs uppercase tracking-[0.18em] text-success">Documento activo</div>
            <div className="mt-1 flex flex-wrap gap-2 text-sm text-foreground">
              <span className="font-medium">{currentDocument.filename}</span>
              <span className="text-muted-foreground">{currentDocument.source_type}</span>
              <span className="font-mono text-xs text-muted-foreground">{currentDocument.checksum.slice(0, 12)}</span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              Se mantiene el mismo `document_id` en reintentos para no romper la idempotencia.
            </p>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
