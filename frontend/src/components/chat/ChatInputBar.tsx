"use client";

import { useCallback, useRef, useState, type KeyboardEvent } from "react";
import { Button, Textarea } from "@nextui-org/react";
import { Paperclip, Send, SlidersHorizontal } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { startAnalysis, uploadDocument } from "@/lib/api";
import type { ChatMessage } from "@/stores/appStore";
import type { SourceType } from "@/types/contracts";

interface ChatInputBarProps {
  onStartStream?: (query: string, idempotencyKey: string) => void;
}

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

export function ChatInputBar({ onStartStream }: ChatInputBarProps) {
  const [value, setValue] = useState("");
  const [uploading, setUploading] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const addChatMessage = useAppStore((state) => state.addChatMessage);
  const setConsoleOpen = useAppStore((state) => state.setConsoleOpen);
  const isConsoleOpen = useAppStore((state) => state.isConsoleOpen);
  const setCurrentDocument = useAppStore((state) => state.setCurrentDocument);
  const setIsAnalyzing = useAppStore((state) => state.setIsAnalyzing);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed) return;

    const message: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
      createdAt: Date.now(),
    };

    addChatMessage(message);
    setValue("");

    if (onStartStream) {
      const slug = trimmed
        .toLowerCase()
        .trim()
        .replace(/\s+/g, "-")
        .replace(/[^\w-]/g, "")
        .slice(0, 30);
      const idempotencyKey = `chat:${slug}:${crypto.randomUUID()}`;
      setIsAnalyzing(true);
      onStartStream(trimmed, idempotencyKey);
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file || uploading) return;

      setUploading(true);
      setNotification(null);

      try {
        const content = await toBase64(file);
        const sourceType = sourceTypeFromFilename(file.name);
        const response = await uploadDocument({
          filename: file.name,
          content,
          source_type: sourceType,
        });

        const documentMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: "document",
          content: `Documento subido: ${response.filename}`,
          metadata: { documentId: response.document_id },
          createdAt: Date.now(),
        };

        addChatMessage(documentMessage);
        setCurrentDocument(response);
        setNotification("Documento subido. Iniciando extracción...");

        await startAnalysis(response.document_id, {
          idempotency_key: response.document_id,
        });

        setIsAnalyzing(true);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Error al subir el documento.";
        setNotification(message);
      } finally {
        setUploading(false);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    },
    [addChatMessage, setCurrentDocument, setIsAnalyzing, uploading],
  );

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 w-full max-w-3xl px-4 z-40">
      <div className="bg-white/60 backdrop-blur-xl rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.04)] flex items-end gap-2 p-2">
        <Button
          isIconOnly
          variant="light"
          size="sm"
          isLoading={uploading}
          onPress={() => fileInputRef.current?.click()}
          className="pb-1"
        >
          <Paperclip className="size-4 text-muted-foreground" />
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,.png,.jpg,.jpeg,.webp"
          onChange={handleFileChange}
        />
        <Textarea
          variant="flat"
          radius="lg"
          minRows={1}
          maxRows={4}
          placeholder="Investiga tecnologías de gasificación de biomasa..."
          value={value}
          onValueChange={setValue}
          onKeyDown={handleKeyDown}
          classNames={{
            inputWrapper: "bg-transparent shadow-none border-none",
            input: "text-foreground placeholder:text-muted-foreground",
          }}
          className="flex-1"
        />
        <div className="flex items-center gap-1 pb-1 pr-1">
          <Button
            isIconOnly
            variant="light"
            size="sm"
            onPress={() => setConsoleOpen(!isConsoleOpen)}
          >
            <SlidersHorizontal className="size-4 text-muted-foreground" />
          </Button>
          <Button
            isIconOnly
            variant="light"
            size="sm"
            onPress={handleSend}
          >
            <Send className="size-4 text-primary" />
          </Button>
        </div>
      </div>
      {notification ? (
        <div className="mt-2 text-center text-sm text-muted-foreground">
          {notification}
        </div>
      ) : null}
    </div>
  );
}
