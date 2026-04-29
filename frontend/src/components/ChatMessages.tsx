"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ReportSection } from "@/components/ReportSection";
import { Skeleton } from "@/components/ui/skeleton";
import { CheckCircle2, FileUp, Play, Sparkles } from "lucide-react";
import type {
  DocumentMentionsResponse,
  DocumentUploadResponse,
  OperationRecord,
  TechnologyReport,
} from "@/types/contracts";

export type ChatMessage = {
  id: string;
  role: "user" | "system" | "assistant";
  content?: string;
  document?: DocumentUploadResponse;
  report?: TechnologyReport;
  mentions?: DocumentMentionsResponse;
  timestamp: string | null;
};

type ChatMessagesProps = {
  messages: ChatMessage[];
  isAnalyzing: boolean;
  canAnalyze: boolean;
  operation: OperationRecord | null;
  currentDocumentId: string | null;
  onStartAnalysis: () => void;
  onExportPdf: () => void;
  messagesEndRef: React.RefObject<HTMLDivElement>;
};

function formatChatTimestamp(timestamp: string | null) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";

  const hours = date.getHours().toString().padStart(2, "0");
  const minutes = date.getMinutes().toString().padStart(2, "0");
  return `${hours}:${minutes}`;
}

export function ChatMessages({
  messages,
  isAnalyzing,
  canAnalyze,
  operation,
  currentDocumentId,
  onStartAnalysis,
  onExportPdf,
  messagesEndRef,
}: ChatMessagesProps) {
  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-10 space-y-8 pb-10">
      <div className="max-w-3xl mx-auto space-y-8">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] ${msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-white border border-slate-200 text-foreground"} rounded-2xl p-5 shadow-sm relative`}>

              {msg.role === "user" && msg.content && (
                <p className="text-sm leading-relaxed">{msg.content}</p>
              )}

              {msg.role !== "user" && msg.content && (
                <div className="flex gap-3">
                  <Sparkles className="size-5 text-primary shrink-0 mt-0.5" />
                  <p className="text-sm leading-relaxed">{msg.content}</p>
                </div>
              )}

              {msg.document && (
                <div className="flex items-center gap-3 bg-white/10 rounded-xl p-3 border border-white/20 mt-2">
                  <FileUp className="size-8 opacity-80" />
                  <div className="flex flex-col overflow-hidden">
                    <span className="text-sm font-medium truncate">{msg.document.filename}</span>
                    <span className="text-xs opacity-80 uppercase">
                      {msg.document.source_type} &bull; {msg.document.page_count} pags
                    </span>
                  </div>
                </div>
              )}

              {msg.mentions && (
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mt-2 w-full">
                  <div className="flex items-center gap-3 border-b border-slate-100 pb-3 mb-3">
                    <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <CheckCircle2 className="size-5" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-foreground">Tecnologias Extraidas</h4>
                      <p className="text-xs text-slate-500">{msg.mentions.normalized_count} detectadas</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {msg.mentions.normalized.slice(0, 8).map((tech) => (
                      <Badge key={tech.normalized_name} className="bg-emerald-100 text-emerald-700 hover:bg-emerald-200 border-none">
                        {tech.normalized_name}
                      </Badge>
                    ))}
                    {msg.mentions.normalized.length > 8 && (
                      <Badge variant="outline">+{msg.mentions.normalized.length - 8} mas</Badge>
                    )}
                  </div>
                </div>
              )}

              {msg.report && (
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mt-2 w-full">
                  <div className="flex items-center gap-3 border-b border-slate-100 pb-3 mb-3">
                    <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Sparkles className="size-5" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-foreground">Reporte Ejecutivo</h4>
                      <p className="text-xs text-slate-500">Documento analizado y consolidado</p>
                    </div>
                  </div>
                  <p className="text-sm text-slate-500 mb-4">
                    {(msg.report.executive_summary || "").substring(0, 150)}...
                  </p>
                  <ReportSection
                    documentId={currentDocumentId}
                    report={msg.report}
                    onExportPdf={onExportPdf}
                  />
                </div>
              )}

              {msg.role === "assistant" && msg.content?.includes("Deseas iniciar") && canAnalyze && !isAnalyzing && !operation && (
                <Button onClick={onStartAnalysis} variant="default" className="mt-4 w-full sm:w-auto shadow-md">
                  <Play className="size-4 mr-2" /> Iniciar Analisis
                </Button>
              )}

              <span className={`text-[10px] absolute -bottom-5 ${msg.role === "user" ? "right-2" : "left-2"} text-muted-foreground`}>
                {formatChatTimestamp(msg.timestamp)}
              </span>
            </div>
          </div>
        ))}

        {isAnalyzing && (
          <div className="flex justify-start">
            <div className="max-w-[85%] bg-white border border-slate-100 rounded-2xl p-5 shadow-sm space-y-3">
              <div className="flex items-center gap-2">
                <Sparkles className="size-5 text-primary animate-pulse" />
                <span className="text-sm font-medium text-slate-500 italic">Investigando...</span>
              </div>
              <div className="space-y-2">
                <Skeleton className="h-4 w-[250px] bg-slate-100" />
                <Skeleton className="h-4 w-[200px] bg-slate-100" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
