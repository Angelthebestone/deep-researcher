"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUpRight,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  Network,
  Search,
  Sparkles,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  createAnalyzeStreamUrl,
  createChatStreamUrl,
  getDocumentMentions,
  getDocumentReport,
  getOperationRecord,
  normalizeDetails,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { persistDashboardSnapshot, persistReportArtifact } from "@/services/supabaseClient";
import type {
  AnalysisStreamEvent,
  DocumentMentionsResponse,
  OperationRecord,
  StageContext,
  TechnologyReport,
} from "@/types/contracts";

type StreamStage = {
  label: string;
  percent: number;
  tone: "neutral" | "primary" | "success" | "warning" | "critical";
};

type AnalysisStreamProps = {
  documentId: string | null;
  idempotencyKey: string | null;
  chatQuery?: string | null;
  active: boolean;
  sessionSeed: number;
  onEvent?: (event: AnalysisStreamEvent) => void;
  onMentionsLoaded?: (payload: DocumentMentionsResponse) => void;
  onReportLoaded?: (report: TechnologyReport) => void;
  onOperationLoaded?: (operation: OperationRecord) => void;
  onStreamStateChange?: (state: StreamStage & { status: string; message: string }) => void;
};

const STAGE_ORDER: Record<string, number> = {
  PromptImprovementStarted: 6,
  PromptImproved: 12,
  DocumentParsed: 12,
  TechnologiesExtracted: 28,
  TechnologiesNormalized: 42,
  ResearchRequested: 54,
  ResearchPlanCreated: 62,
  ResearchNodeEvaluated: 78,
  ResearchCompleted: 88,
  ReportGenerated: 100,
};

function stageTone(eventType: string): StreamStage["tone"] {
  if (eventType === "ReportGenerated" || eventType === "ResearchCompleted") {
    return "success";
  }
  if (eventType === "ResearchNodeEvaluated" || eventType === "ResearchRequested" || eventType === "ResearchPlanCreated") {
    return "primary";
  }
  if (eventType === "TechnologiesExtracted" || eventType === "TechnologiesNormalized") {
    return "warning";
  }
  if (eventType === "AnalysisFailed") {
    return "critical";
  }
  return "neutral";
}

function isTerminalStreamEvent(event: AnalysisStreamEvent): boolean {
  return event.operation_status === "completed" || event.operation_status === "failed";
}

function terminalStreamState(event: AnalysisStreamEvent, stageMessage: string, percent: number) {
  if (event.operation_status === "completed") {
    return {
      badgeStatus: "complete",
      label: "Stream SSE completado.",
      tone: "success" as const,
      status: "completed",
      message: "Stream SSE completado.",
      percent,
    };
  }
  return {
    badgeStatus: "failed",
    label: stageMessage,
    tone: "critical" as const,
    status: "failed",
    message: stageMessage,
    percent,
  };
}

function getStageContext(event: AnalysisStreamEvent): StageContext {
  if (event.stage_context && typeof event.stage_context === "object") {
    return event.stage_context as StageContext;
  }
  const details = normalizeDetails(event.details);
  if (details.stage_context && typeof details.stage_context === "object") {
    return details.stage_context as StageContext;
  }
  return { stage: event.event_type };
}

function getStageModel(event: AnalysisStreamEvent): string | null {
  const stageContext = getStageContext(event);
  if (typeof stageContext.model === "string" && stageContext.model.trim()) {
    return stageContext.model;
  }
  const details = normalizeDetails(event.details);
  if (typeof details.model === "string" && details.model.trim()) {
    return details.model;
  }
  if (typeof details.ingestion_engine === "string" && details.ingestion_engine.trim()) {
    return details.ingestion_engine;
  }
  return null;
}

function getFailedStage(event: AnalysisStreamEvent): string | null {
  const stageContext = getStageContext(event);
  return stageContext.failed_stage ?? null;
}

function getStreamLabel(event: AnalysisStreamEvent): string {
  const stageContext = getStageContext(event);
  if (event.event_type === "AnalysisFailed") {
    return getFailedStage(event) ?? stageContext.stage ?? "AnalysisFailed";
  }
  return stageContext.stage ?? event.event_type;
}

function eventIcon(eventType: string) {
  if (eventType === "DocumentParsed") return <Sparkles className="size-4" />;
  if (eventType === "TechnologiesExtracted") return <Search className="size-4" />;
  if (eventType === "TechnologiesNormalized") return <BrainCircuit className="size-4" />;
  if (eventType === "ResearchRequested") return <Network className="size-4" />;
  if (eventType === "ResearchPlanCreated") return <BrainCircuit className="size-4" />;
  if (eventType === "ResearchNodeEvaluated") return <ArrowUpRight className="size-4" />;
  if (eventType === "ResearchCompleted" || eventType === "ReportGenerated") return <CheckCircle2 className="size-4" />;
  if (eventType === "PromptImproved") return <Sparkles className="size-4" />;
  return <Clock3 className="size-4" />;
}

function extractStageLabel(event: AnalysisStreamEvent) {
  const details = normalizeDetails(event.details);
  const stageContext = getStageContext(event);
  const model = getStageModel(event);

  if (event.event_type === "AnalysisFailed") {
    const failedStage = getFailedStage(event);
    return failedStage ? `Fallo en ${failedStage}` : event.message || "Analisis fallido";
  }
  if (event.event_type === "DocumentParsed") {
    const fallbackReason = typeof details.fallback_reason === "string" ? details.fallback_reason : "";
    return fallbackReason ? `Fallback: ${fallbackReason}` : `Procesado por ${model ?? "motor desconocido"}`;
  }
  if (event.event_type === "ResearchNodeEvaluated") {
    const breadth = Number(details.breadth ?? 0);
    const depth = Number(details.depth ?? 0);
    const branchResult =
      details.branch_result && typeof details.branch_result === "object" && !Array.isArray(details.branch_result)
        ? (details.branch_result as Record<string, unknown>)
        : null;
    const branchId =
      typeof branchResult?.branch_id === "string"
        ? branchResult.branch_id
        : "rama";
    const iterations =
      typeof branchResult?.iterations === "number"
        ? branchResult.iterations
        : "?";
    return `${stageContext.stage ?? event.event_type} | ${branchId} | Breadth ${breadth || "?"} / Depth ${depth || "?"} | Iteraciones ${iterations}${
      model ? ` | ${model}` : ""
    }`;
  }
  if (event.event_type === "ResearchPlanCreated") {
    const plan = details.research_plan;
    const branchCount =
      plan && typeof plan === "object" && !Array.isArray(plan) && Array.isArray((plan as Record<string, unknown>).branches)
        ? ((plan as Record<string, unknown>).branches as unknown[]).length
        : 0;
    return `Plan de investigación creado${branchCount ? ` | ${branchCount} ramas` : ""}${model ? ` | ${model}` : ""}`;
  }
  if (event.event_type === "TechnologiesExtracted") {
    return `${details.mention_count ?? 0} menciones extraidas${model ? ` | ${model}` : ""}`;
  }
  if (event.event_type === "TechnologiesNormalized") {
    return `${details.mention_count ?? 0} menciones normalizadas${model ? ` | ${model}` : ""}`;
  }
  if (event.event_type === "ReportGenerated") {
    return typeof details.report_id === "string"
      ? `Reporte ${details.report_id}${model ? ` | ${model}` : ""}`
      : `Reporte final generado${model ? ` | ${model}` : ""}`;
  }
  if (event.event_type === "PromptImproved") {
    return `Prompt mejorado: ${details.target_technology ?? "Investigación"}`;
  }
  if (event.event_type === "PromptImprovementStarted") {
    return `Preparando investigación de ${details.target_technology ?? "la consulta"}`;
  }
  return event.message || event.event_type;
}

function computeProgress(payload: AnalysisStreamEvent, currentProgress: number) {
  if (payload.event_type === "ResearchNodeEvaluated") {
    const details = normalizeDetails(payload.details);
    const position = Number(details.position ?? 0);
    const total = Number(details.total ?? 0);
    if (position > 0 && total > 0) {
      return Math.min(100, 54 + Math.round((position / total) * 28));
    }
  }
  if (payload.event_type === "PromptImprovementStarted") {
    return 6;
  }
  if (payload.event_type === "PromptImproved") {
    return 12;
  }
  if (payload.event_type === "ResearchPlanCreated") {
    return 62;
  }
  return STAGE_ORDER[payload.event_type] ?? Math.min(100, currentProgress + 5);
}

export function AnalysisStream({
  documentId,
  idempotencyKey,
  chatQuery,
  active,
  sessionSeed,
  onEvent,
  onMentionsLoaded,
  onReportLoaded,
  onOperationLoaded,
  onStreamStateChange,
}: AnalysisStreamProps) {
  const [events, setEvents] = useState<AnalysisStreamEvent[]>([]);
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("Esperando una ejecucion de analisis.");
  const [progress, setProgress] = useState(0);
  const [operationId, setOperationId] = useState<string | null>(null);
  const [fallbackLabel, setFallbackLabel] = useState<string | null>(null);
  const [internalDocumentId, setInternalDocumentId] = useState<string | null>(documentId);
  const eventsRef = useRef<AnalysisStreamEvent[]>([]);
  const progressRef = useRef(0);
  const operationIdRef = useRef<string | null>(null);
  const mentionsLoadedStage = useRef<"extracted" | "normalized" | null>(null);
  const mentionsLoadedForDocument = useRef<string | null>(null);
  const reportLoadedForDocument = useRef<string | null>(null);
  const onEventRef = useRef(onEvent);
  const onMentionsLoadedRef = useRef(onMentionsLoaded);
  const onReportLoadedRef = useRef(onReportLoaded);
  const onOperationLoadedRef = useRef(onOperationLoaded);
  const onStreamStateChangeRef = useRef(onStreamStateChange);

  useEffect(() => {
    setInternalDocumentId(documentId);
  }, [documentId]);

  useEffect(() => {
    eventsRef.current = events;
  }, [events]);

  useEffect(() => {
    progressRef.current = progress;
  }, [progress]);

  useEffect(() => {
    operationIdRef.current = operationId;
  }, [operationId]);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    onMentionsLoadedRef.current = onMentionsLoaded;
  }, [onMentionsLoaded]);

  useEffect(() => {
    onReportLoadedRef.current = onReportLoaded;
  }, [onReportLoaded]);

  useEffect(() => {
    onOperationLoadedRef.current = onOperationLoaded;
  }, [onOperationLoaded]);

  useEffect(() => {
    onStreamStateChangeRef.current = onStreamStateChange;
  }, [onStreamStateChange]);

  useEffect(() => {
    if (!active || (!idempotencyKey && !chatQuery)) {
      return;
    }

    const streamUrl = chatQuery
      ? createChatStreamUrl(chatQuery, idempotencyKey)
      : (documentId && idempotencyKey ? createAnalyzeStreamUrl(documentId, idempotencyKey) : null);
    
    if (!streamUrl) return;

    const source = new EventSource(streamUrl);
    const seenEventIds = new Set<string>();

    setStatus("connecting");
    setMessage("Conectando con SSE.");

    source.onopen = () => {
      setStatus("live");
      setMessage("Monitor SSE conectado.");
    };

    source.onmessage = async (event) => {
      const payload = JSON.parse(event.data) as AnalysisStreamEvent;
      if (seenEventIds.has(payload.event_id)) {
        return;
      }
      seenEventIds.add(payload.event_id);

      const nextEvents = eventsRef.current.some((item) => item.event_id === payload.event_id)
        ? eventsRef.current
        : [...eventsRef.current, payload];
      eventsRef.current = nextEvents;
      setEvents(nextEvents);

      onEventRef.current?.(payload);
      const previousOperationId = operationIdRef.current;
      setOperationId(payload.operation_id);
      operationIdRef.current = payload.operation_id;

      if (payload.event_type === "PromptImproved" && payload.document_id) {
          setInternalDocumentId(payload.document_id);
      }

      const nextProgress = computeProgress(payload, progressRef.current);
      progressRef.current = nextProgress;
      setProgress(nextProgress);

      const stageMessage = extractStageLabel(payload);
      setMessage(stageMessage);
      onStreamStateChangeRef.current?.({
        label: stageMessage,
        percent: nextProgress,
        tone: stageTone(payload.event_type),
        status: payload.operation_status,
        message: stageMessage,
      });

      if (isTerminalStreamEvent(payload)) {
        const terminalState = terminalStreamState(payload, stageMessage, nextProgress);
        setStatus(terminalState.badgeStatus);
        setMessage(terminalState.message);
        onStreamStateChangeRef.current?.({
          label: terminalState.label,
          percent: terminalState.percent,
          tone: terminalState.tone,
          status: terminalState.status,
          message: terminalState.message,
        });
        source.close();
      }

      if (payload.event_type === "DocumentParsed") {
        const details = normalizeDetails(payload.details);
        const stageContext = getStageContext(payload);
        const engine =
          typeof stageContext.model === "string"
            ? stageContext.model
            : typeof details.model === "string"
              ? details.model
              : typeof details.ingestion_engine === "string"
                ? details.ingestion_engine
                : null;
        const fallbackReason = typeof details.fallback_reason === "string" ? details.fallback_reason : null;
        setFallbackLabel(fallbackReason ? `Fallback: ${fallbackReason}` : engine ? `Procesado por ${engine}` : null);
      }

      if (
        documentId &&
        payload.document_id === documentId &&
        (payload.event_type === "TechnologiesExtracted" || payload.event_type === "TechnologiesNormalized")
      ) {
        const targetStage = payload.event_type === "TechnologiesNormalized" ? "normalized" : "extracted";
        if (mentionsLoadedForDocument.current !== payload.document_id || mentionsLoadedStage.current !== targetStage) {
          try {
            const mentions = await getDocumentMentions(payload.document_id);
            mentionsLoadedForDocument.current = payload.document_id;
            mentionsLoadedStage.current = targetStage;
            onMentionsLoadedRef.current?.(mentions);
          } catch {
            // mention sidecar may still be missing on early replays
          }
        }
      }

      if (payload.operation_id && payload.operation_id !== previousOperationId) {
        try {
          const operation = await getOperationRecord(payload.operation_id);
          onOperationLoadedRef.current?.(operation);
        } catch {
          // best effort only
        }
      }

      if (documentId && payload.document_id === documentId && payload.event_type === "ReportGenerated" && reportLoadedForDocument.current !== payload.document_id) {
        try {
          const report = await getDocumentReport(payload.document_id);
          reportLoadedForDocument.current = payload.document_id;
          onReportLoadedRef.current?.(report);
          await persistReportArtifact(payload.document_id, report);
        } catch {
          // report hydration will be retried by the dashboard shell
        }
      }

      await persistDashboardSnapshot({
        documentId: payload.document_id || documentId || "chat",
        events: nextEvents,
        idempotencyKey,
        updatedAt: new Date().toISOString(),
      });
    };

    source.onerror = () => {
      const lastEvent = eventsRef.current[eventsRef.current.length - 1] ?? null;
      if (lastEvent?.operation_status === "completed") {
        setStatus("complete");
        setMessage("Stream SSE completado.");
        onStreamStateChangeRef.current?.({
          label: "Stream SSE completado.",
          percent: progressRef.current,
          tone: "success",
          status: "completed",
          message: "Stream SSE completado.",
        });
      } else if (lastEvent?.operation_status === "failed") {
        const stageMessage = extractStageLabel(lastEvent);
        setStatus("failed");
        setMessage(stageMessage);
        onStreamStateChangeRef.current?.({
          label: stageMessage,
          percent: progressRef.current,
          tone: "critical",
          status: "failed",
          message: stageMessage,
        });
      } else {
        setStatus("disconnected");
        setMessage("El stream SSE se desconecto.");
        onStreamStateChangeRef.current?.({
          label: "El stream SSE se desconecto.",
          percent: progressRef.current,
          tone: "critical",
          status: "disconnected",
          message: "El stream SSE se desconecto.",
        });
      }
      source.close();
    };

    return () => {
      source.close();
    };
  }, [active, documentId, idempotencyKey, chatQuery, sessionSeed]);

  const latestEvent = events[events.length - 1];
  const visibleEvents = useMemo(() => events.slice(-6).reverse(), [events]);

  return (
    <Card className="ai-panel overflow-hidden border-border/70 shadow-soft">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <CardTitle className="font-display text-xl">Rastro de razonamiento</CardTitle>
            <CardDescription>Progressive SSE para la taxonomia completa del analisis y Deep Research.</CardDescription>
          </div>
          <Badge
            variant={status === "live" || status === "complete" ? "success" : status === "connecting" ? "secondary" : "outline"}
          >
            {status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="rounded-[1.75rem] border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(250,250,255,0.82))] p-4">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-col gap-1">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Estado actual</div>
                <div className="font-medium text-foreground">{message}</div>
              </div>
              {fallbackLabel ? <Badge variant="outline">{fallbackLabel}</Badge> : <Badge variant="secondary">Sin fallback</Badge>}
            </div>
            <Progress value={progress} />
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>Id: {internalDocumentId ?? "pendiente"}</span>
              <span>•</span>
              {idempotencyKey ? (
                <>
                  <span>Idempotency: {idempotencyKey}</span>
                  <span>•</span>
                </>
              ) : null}
              {operationId ? (
                <>
                  <span>OperationId: {operationId}</span>
                </>
              ) : null}
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-[1.5rem] border border-border bg-background/80 p-4">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Eventos</div>
            <div className="mt-1 text-2xl font-semibold">{events.length}</div>
          </div>
          <div className="rounded-[1.5rem] border border-border bg-background/80 p-4">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Progreso</div>
            <div className="mt-1 text-2xl font-semibold">{progress}%</div>
          </div>
          <div className="rounded-[1.5rem] border border-border bg-background/80 p-4">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Ultimo nodo</div>
            <div className="mt-1 text-sm font-medium">
              {typeof latestEvent?.stage_context?.model === "string" ? latestEvent.stage_context.model : "n/a"}
            </div>
          </div>
          <div className="rounded-[1.5rem] border border-border bg-background/80 p-4">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Ultimo tipo</div>
            <div className="mt-1 text-sm font-medium">{latestEvent?.event_type ?? "n/a"}</div>
          </div>
        </div>

        <Separator />

        <div className="flex flex-col gap-3">
          {visibleEvents.length ? (
            visibleEvents.map((event) => (
              <div
                key={event.event_id}
                className={cn(
                  "rounded-[1.75rem] border p-4 transition-colors",
                  event.event_type === "ReportGenerated"
                    ? "border-success/20 bg-success/5"
                    : "border-border bg-background/90",
                )}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "flex size-11 items-center justify-center rounded-2xl",
                        event.event_type === "ReportGenerated" ? "bg-success/10 text-success" : "bg-primary/10 text-primary",
                      )}
                    >
                      {eventIcon(event.event_type)}
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <div className="font-medium">{event.event_type}</div>
                      <div className="text-xs text-muted-foreground">{extractStageLabel(event)}</div>
                      {getStageModel(event) ? (
                        <div className="text-[0.7rem] uppercase tracking-[0.16em] text-muted-foreground">
                          Modelo: {getStageModel(event)}
                        </div>
                      ) : null}
                    </div>
                  </div>
                  <Badge variant={stageTone(event.event_type) === "success" ? "success" : "secondary"}>#{event.sequence}</Badge>
                </div>
                <div className="mt-3 grid gap-2 text-sm text-muted-foreground">
                  <div>Node: {typeof event.details?.node_name === "string" ? event.details.node_name : "n/a"}</div>
                  {Object.keys(event.details || {}).length ? (
                    <pre className="overflow-auto rounded-[1.25rem] bg-muted/40 p-3 text-xs text-foreground">
                      {JSON.stringify(event.details, null, 2)}
                    </pre>
                  ) : null}
                </div>
              </div>
            ))
          ) : (
            <div className="flex min-h-48 flex-col items-center justify-center rounded-[1.75rem] border border-dashed border-border bg-muted/20 text-center">
              <LoaderCircle className="size-8 animate-spin text-muted-foreground" />
              <p className="mt-3 text-sm text-muted-foreground">Todavia no hay eventos SSE.</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
