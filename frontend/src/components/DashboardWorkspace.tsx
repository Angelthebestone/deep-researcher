"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import { Activity, MessageSquare, Network, SidebarClose, SidebarOpen, Sparkles, LoaderCircle } from "lucide-react";

import { AnalysisStream } from "@/components/AnalysisStream";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DocumentIngest } from "@/components/DocumentIngest";
import { KnowledgeGraph } from "@/components/KnowledgeGraph";
import { ChatMessages } from "@/components/ChatMessages";
import type { ChatMessage } from "@/components/ChatMessages";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiBaseUrl, normalizeDetails, startAnalysis } from "@/lib/api";
import { persistDashboardSnapshot, persistReportArtifact } from "@/services/supabaseClient";
import type {
  AnalysisStreamEvent,
  DocumentMentionsResponse,
  DocumentStatusResponse,
  DocumentUploadResponse,
  OperationRecord,
  TechnologyReport,
} from "@/types/contracts";

type StreamState = {
  label: string;
  percent: number;
  tone: "neutral" | "primary" | "success" | "warning" | "critical";
  status: string;
  message: string;
};

function buildIdempotencyKey(doc: DocumentUploadResponse | null) {
  if (!doc) return null;
  return `analysis:${doc.document_id}:${doc.checksum}`;
}

function buildChatIdempotencyKey(query: string) {
  const slug = query
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "chat";
  const uniqueSeed = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}`;
  return `chat:${slug}:${uniqueSeed}`;
}

function hasActiveOperation(op: OperationRecord | null) {
  if (!op) return false;
  return op.status === "running" || op.status === "queued";
}

export function DashboardWorkspace() {
  const [currentDocument, setCurrentDocument] = useState<DocumentUploadResponse | null>(null);
  const [documentStatus, setDocumentStatus] = useState<DocumentStatusResponse | null>(null);
  const [mentions, setMentions] = useState<DocumentMentionsResponse | null>(null);
  const [report, setReport] = useState<TechnologyReport | null>(null);
  const [operation, setOperation] = useState<OperationRecord | null>(null);
  const [events, setEvents] = useState<AnalysisStreamEvent[]>([]);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [analysisSessionSeed, setAnalysisSessionSeed] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [chatQuery, setChatQuery] = useState<string | null>(null);
  const [inputMessage, setInputMessage] = useState("");
  const [isCotOpen, setIsCotOpen] = useState(true);
  const [isDocumentPanelOpen, setIsDocumentPanelOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([{
    id: "welcome",
    role: "system",
    content: "Hola. Soy el Vigilador Tecnologico. Sube un documento o escribe una consulta para comenzar.",
    timestamp: null,
  }]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const canAnalyze = Boolean(currentDocument && idempotencyKey);
  const activeOperation = useMemo(() => hasActiveOperation(operation), [operation]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  async function handleUploaded(doc: DocumentUploadResponse) {
    setErrorMessage(null);
    setCurrentDocument(doc);
    setDocumentStatus({ document_id: doc.document_id, status: "PARSED", last_updated: doc.uploaded_at, error: null });
    setMentions(null); setReport(null); setOperation(null); setEvents([]);
    setChatQuery(null); setAnalysisSessionSeed(0);
    setIsDocumentPanelOpen(false);
    const nextKey = buildIdempotencyKey(doc);
    setIdempotencyKey(nextKey);
    setChatMessages((prev) => [...prev, { id: Date.now().toString(), role: "user", document: doc, timestamp: new Date().toISOString() }]);
    setTimeout(() => {
      setChatMessages((prev) => [...prev, {
        id: (Date.now() + 1).toString(), role: "assistant",
        content: `He recibido el documento "${doc.filename}". Deseas iniciar el analisis profundo?`,
        timestamp: new Date().toISOString(),
      }]);
    }, 500);
    await persistDashboardSnapshot({ documentId: doc.document_id, uploadedDocument: doc, status: { document_id: doc.document_id, status: "PARSED", last_updated: doc.uploaded_at, error: null }, idempotencyKey: nextKey, updatedAt: new Date().toISOString() });
  }

  async function handleStartAnalysis() {
    if (!currentDocument || !idempotencyKey) return;
    setErrorMessage(null); setIsAnalyzing(true);
    setAnalysisSessionSeed((v) => v + 1);
    setChatMessages((prev) => [...prev, { id: Date.now().toString(), role: "user", content: "Inicia el analisis de este documento.", timestamp: new Date().toISOString() }]);
    try {
      const response = await startAnalysis(currentDocument.document_id, { idempotency_key: idempotencyKey });
      setOperation({ operation_id: response.operation_id, operation_type: "analysis", subject_id: currentDocument.document_id, status: response.status, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), idempotency_key: idempotencyKey, message: response.reused ? "Reused." : "Requested.", details: { report_id: response.report_id, reused: response.reused }, event_count: events.length });
      if (response.report) setReport(response.report);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "No se pudo iniciar el analisis.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleSendMessage(e?: React.FormEvent) {
    e?.preventDefault();
    if (!inputMessage.trim() || isAnalyzing) return;
    const query = inputMessage.trim();
    const nextIdempotencyKey = buildChatIdempotencyKey(query);
    setInputMessage(""); setErrorMessage(null); setIsAnalyzing(true);
    setAnalysisSessionSeed((v) => v + 1); setChatQuery(query);
    setCurrentDocument(null); setIdempotencyKey(nextIdempotencyKey); setReport(null); setMentions(null); setOperation(null); setEvents([]);
    setChatMessages((prev) => [...prev, { id: Date.now().toString(), role: "user", content: query, timestamp: new Date().toISOString() }]);
  }

  function handleEvent(event: AnalysisStreamEvent) {
    setEvents((cur) => cur.some((e) => e.event_id === event.event_id) ? cur : [...cur, event]);
    setOperation((current) => {
      const createdAt = current?.operation_id === event.operation_id ? current.created_at : new Date().toISOString();
      const previousCount = current?.operation_id === event.operation_id ? current.event_count ?? 0 : 0;
      return {
        operation_id: event.operation_id,
        operation_type: event.operation_type,
        subject_id: event.document_id,
        status: event.operation_status,
        created_at: createdAt,
        updated_at: new Date().toISOString(),
        idempotency_key: event.idempotency_key,
        message: event.message,
        details: event.details,
        event_count: previousCount + 1,
      };
    });
    if (event.event_type === "PromptImproved") {
      const details = normalizeDetails(event.details);
      const refinedQuery = typeof details.refined_query === "string" ? details.refined_query : "";
      const targetTechnology = typeof details.target_technology === "string" ? details.target_technology : "";
      const content = refinedQuery
        ? `Prompt mejorado${targetTechnology ? ` para ${targetTechnology}` : ""}: ${refinedQuery}`
        : `Prompt mejorado${targetTechnology ? ` para ${targetTechnology}` : ""}.`;
      setChatMessages((prev) => {
        if (prev.some((m) => m.id === event.event_id)) return prev;
        return [...prev, { id: event.event_id, role: "assistant", content, timestamp: new Date().toISOString() }];
      });
    }
    if (event.operation_status === "completed" || event.operation_status === "failed") {
      setIsAnalyzing(false);
    }
  }

  function handleStreamStateChange(state: StreamState) {
    if (state.status === "completed" || state.status === "failed" || state.status === "complete" || state.status === "disconnected") {
      setIsAnalyzing(false);
    }
  }

  function handleMentionsLoaded(payload: DocumentMentionsResponse) {
    setMentions(payload);
    setChatMessages((prev) => {
      if (prev.some((m) => m.mentions?.document_id === payload.document_id && m.mentions?.normalized_count === payload.normalized_count)) return prev;
      return [...prev, { id: Date.now().toString() + "-mentions", role: "assistant", mentions: payload, timestamp: new Date().toISOString() }];
    });
    if (currentDocument) void persistDashboardSnapshot({ documentId: currentDocument.document_id, uploadedDocument: currentDocument, status: documentStatus, mentions: payload.extracted, normalizedMentions: payload.normalized, report, operation, events, idempotencyKey, updatedAt: new Date().toISOString() });
  }

  function handleReportLoaded(nextReport: TechnologyReport) {
    setReport(nextReport);
    setChatMessages((prev) => {
      if (prev.some((m) => m.report && m.report.executive_summary === nextReport.executive_summary)) return prev;
      return [...prev, { id: Date.now().toString() + "-report", role: "assistant", report: nextReport, timestamp: new Date().toISOString() }];
    });
    if (currentDocument) void persistReportArtifact(currentDocument.document_id, nextReport, currentDocument);
  }

  function handleExportPdf() {
    if (typeof window === "undefined") return;
    const root = document.body;
    root.dataset.printMode = "report";
    const cleanup = () => { delete root.dataset.printMode; window.removeEventListener("afterprint", cleanup); };
    window.addEventListener("afterprint", cleanup);
    window.requestAnimationFrame(() => window.print());
  }

  return (
    <div className="flex h-screen w-full flex-col bg-slate-50 text-foreground overflow-hidden font-sans">
      <Tabs defaultValue="chat" className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-border/60 bg-white px-6 shadow-sm z-20">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
              <Activity className="size-5" />
            </div>
            <div className="flex flex-col leading-none">
              <span className="text-sm font-bold tracking-tight text-slate-900">Vigilador Tecnologico</span>
              <span className="text-[10px] uppercase tracking-[0.2em] font-medium text-slate-500 mt-0.5">Workspace</span>
            </div>
          </div>
          <TabsList className="bg-slate-100">
            <TabsTrigger value="chat" className="gap-2"><MessageSquare className="size-4" />Chat de Analisis</TabsTrigger>
            <TabsTrigger value="graph" className="gap-2"><Network className="size-4" />Grafo de Conocimiento</TabsTrigger>
          </TabsList>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground" onClick={() => setIsCotOpen(!isCotOpen)}>
              {isCotOpen ? (<><SidebarClose className="size-4 mr-2" />Ocultar Razonamiento</>) : (<><SidebarOpen className="size-4 mr-2" />Ver Razonamiento</>)}
            </Button>
          </div>
        </header>

        <TabsContent value="chat" className="flex-1 mt-0 overflow-hidden flex">
          <div className="flex flex-1 h-full overflow-hidden bg-white">
            <div className="flex flex-1 flex-col overflow-hidden bg-white border-r border-slate-100">
              <ChatMessages
                messages={chatMessages}
                isAnalyzing={isAnalyzing}
                canAnalyze={canAnalyze}
                operation={operation}
                currentDocumentId={currentDocument?.document_id ?? null}
                onStartAnalysis={handleStartAnalysis}
                onExportPdf={handleExportPdf}
                messagesEndRef={messagesEndRef}
              />
              <div className="shrink-0 bg-white border-t border-slate-200/60 pt-4 pb-6 px-6 md:px-10">
                <div className="max-w-3xl mx-auto space-y-4">
                  <form onSubmit={handleSendMessage} className="flex items-center gap-2 bg-white rounded-2xl border border-slate-200 p-2 shadow-sm focus-within:ring-2 focus-within:ring-primary/20 transition-all">
                    <Input
                      placeholder="Escribe una consulta (ej: 'investiga sobre paneles solares')..."
                      className="border-none shadow-none focus-visible:ring-0 text-sm"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      disabled={isAnalyzing}
                    />
                    <Button type="submit" size="sm" disabled={!inputMessage.trim() || isAnalyzing} className="rounded-xl px-4">
                      {isAnalyzing ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4 mr-2" />}
                      Analizar
                    </Button>
                  </form>
                  <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                    <button
                      type="button"
                      className="group flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-slate-50"
                      onClick={() => setIsDocumentPanelOpen((current) => !current)}
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-900">
                          {currentDocument ? "Documento activo" : "Subir documento"}
                        </p>
                        <p className="truncate text-xs text-slate-500">
                          {currentDocument
                            ? `${currentDocument.filename} | ${currentDocument.source_type} | ${currentDocument.document_id}`
                            : "Abre el panel solo cuando necesites cargar o reemplazar un artefacto."}
                        </p>
                      </div>
                      <span className="inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors group-hover:bg-slate-100">
                        {isDocumentPanelOpen ? <SidebarClose className="size-4" /> : <SidebarOpen className="size-4" />}
                        {isDocumentPanelOpen ? "Ocultar" : "Mostrar"}
                      </span>
                    </button>
                    {isDocumentPanelOpen ? (
                      <div className="max-h-[44vh] overflow-y-auto border-t border-slate-200 bg-slate-50/60 p-3">
                        <DocumentIngest
                          compact
                          currentDocument={currentDocument}
                          onUploaded={handleUploaded}
                          onUploadError={setErrorMessage}
                        />
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>

            {isCotOpen && (
              <div className="w-96 shrink-0 bg-slate-50 border-l border-slate-200 flex flex-col overflow-hidden">
                <div className="p-4 border-b border-slate-200 bg-white flex justify-between items-center shrink-0">
                  <div>
                    <p className="text-sm font-semibold text-primary">Internal Trace</p>
                    <p className="text-[10px] uppercase font-mono text-slate-500">Live SSE Stream</p>
                  </div>
                  {isAnalyzing && <LoaderCircle className="size-4 animate-spin text-primary" />}
                </div>
                <div className="flex-1 overflow-y-auto p-4 custom-scrollbar font-mono text-xs">
                  <AnalysisStream
                    documentId={currentDocument?.document_id ?? null}
                    idempotencyKey={idempotencyKey}
                    chatQuery={chatQuery}
                    active={Boolean((currentDocument && idempotencyKey) || chatQuery) && analysisSessionSeed > 0}
                    sessionSeed={analysisSessionSeed}
                    onEvent={handleEvent}
                    onMentionsLoaded={handleMentionsLoaded}
                    onReportLoaded={handleReportLoaded}
                    onOperationLoaded={(op) => setOperation(op)}
                    onStreamStateChange={handleStreamStateChange}
                  />
                </div>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="graph" className="flex-1 mt-0 overflow-hidden flex">
          <div className="flex flex-1 h-full bg-slate-50">
            <KnowledgeGraph documentId={currentDocument?.document_id ?? null} mentions={mentions} report={report} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
