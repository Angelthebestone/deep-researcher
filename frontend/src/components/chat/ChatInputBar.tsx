"use client";

import { useCallback, useRef, useState, type KeyboardEvent } from "react";
import { Button, Textarea, ButtonGroup } from "@nextui-org/react";
import {
  Paperclip,
  Send,
  SlidersHorizontal,
  RefreshCw,
  PanelRight,
  PanelRightClose,
} from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { useActiveWorkspace } from "@/hooks/useActiveWorkspace";
import { startAnalysis, uploadDocument } from "@/lib/api";
import { sourceTypeFromFilename, toBase64 } from "@/lib/files";
import type { ChatMessage } from "@/types/chat";

type ChatMode =
  | "investigación"
  | "comparador"
  | "validación"
  | "costo-beneficio";

const MODES: { key: ChatMode; label: string }[] = [
  { key: "investigación", label: "Investigación" },
  { key: "comparador", label: "Comparador" },
  { key: "validación", label: "Validación" },
  { key: "costo-beneficio", label: "Costo/Beneficio" },
];

interface ChatInputBarProps {
  onStartStream?: (query: string, idempotencyKey: string) => void;
  panelOpen?: boolean;
  onTogglePanel?: () => void;
}

export function ChatInputBar({
  onStartStream,
  panelOpen,
  onTogglePanel,
}: ChatInputBarProps) {
  const [value, setValue] = useState("");
  const [uploading, setUploading] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);
  const [mode, setMode] = useState<ChatMode>("investigación");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const workspace = useActiveWorkspace();
  const addChatMessage = useWorkspaceStore((state) => state.addChatMessage);
  const setConsoleOpen = useAppStore((state) => state.setConsoleOpen);
  const isConsoleOpen = useAppStore((state) => state.isConsoleOpen);
  const setCurrentDocument = useWorkspaceStore((state) => state.setCurrentDocument);
  const setIsAnalyzing = useWorkspaceStore((state) => state.setIsAnalyzing);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || !workspace) return;

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
      if (!file || uploading || !workspace) return;

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
    [addChatMessage, setCurrentDocument, setIsAnalyzing, uploading, workspace],
  );

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 w-full max-w-3xl px-4 z-40 space-y-2">
      <div className="flex items-center justify-between px-1">
        <ButtonGroup size="sm" variant="light">
          {MODES.map((m) => (
            <Button
              key={m.key}
              variant={mode === m.key ? "solid" : "light"}
              color={mode === m.key ? "primary" : "default"}
              size="sm"
              onPress={() => setMode(m.key)}
              className="text-xs"
            >
              {m.label}
            </Button>
          ))}
        </ButtonGroup>

        <div className="flex items-center gap-1">
          <Button
            isIconOnly
            variant="light"
            size="sm"
            onPress={() => console.log("Actualizar vigilancia")}
            aria-label="Actualizar vigilancia"
          >
            <RefreshCw className="size-4 text-muted-foreground" />
          </Button>
          <Button
            isIconOnly
            variant="light"
            size="sm"
            onPress={onTogglePanel}
            aria-label="Alternar panel contextual"
          >
            {panelOpen ? (
              <PanelRightClose className="size-4 text-primary" />
            ) : (
              <PanelRight className="size-4 text-muted-foreground" />
            )}
          </Button>
        </div>
      </div>

      <div className="bg-background/60 backdrop-blur-xl rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.04)] flex items-end gap-2 p-2">
        <Button
          isIconOnly
          variant="light"
          size="sm"
          isLoading={uploading}
          onPress={() => fileInputRef.current?.click()}
          className="pb-1"
          aria-label="Adjuntar archivo"
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
            aria-label="Alternar consola de investigación"
          >
            <SlidersHorizontal className="size-4 text-muted-foreground" />
          </Button>
          <Button
            isIconOnly
            variant="light"
            size="sm"
            onPress={handleSend}
            aria-label="Enviar mensaje"
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
