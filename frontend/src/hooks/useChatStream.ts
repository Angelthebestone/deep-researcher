"use client";

import { useEffect, useRef } from "react";
import { streamChatResearch } from "@/lib/api";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import type { ChatStreamEvent, TechnologyMention, TechnologyReport } from "@/types/contracts";

function getImprovedPrompt(event: ChatStreamEvent): string {
  if (event.details && typeof event.details === "object") {
    if (typeof event.details.refined_query === "string") {
      return event.details.refined_query;
    }
    if (typeof event.details.improved_prompt === "string") {
      return event.details.improved_prompt;
    }
    if (typeof event.details.prompt === "string") {
      return event.details.prompt;
    }
  }
  return event.message;
}

function getReportContent(event: ChatStreamEvent): string {
  if (event.details && typeof event.details === "object") {
    if (typeof event.details.report === "string") {
      return event.details.report;
    }
    if (typeof event.details.report_markdown === "string") {
      return event.details.report_markdown;
    }
  }
  if (typeof event.report === "string") {
    return event.report;
  }
  return event.message;
}

function getErrorContent(event: ChatStreamEvent): string {
  if (event.details && typeof event.details === "object") {
    if (typeof event.details.error === "string") {
      return event.details.error;
    }
  }
  return event.message || "Error desconocido";
}

function getTargetTechnology(event: ChatStreamEvent): string {
  if (event.details && typeof event.details === "object") {
    if (typeof event.details.target_technology === "string") {
      return event.details.target_technology;
    }
    if (typeof event.details.query === "string") {
      return event.details.query;
    }
  }
  return event.message || "la tecnología";
}

function getBreadth(event: ChatStreamEvent): number | string {
  if (event.details && typeof event.details === "object" && typeof event.details.breadth === "number") {
    return event.details.breadth;
  }
  return "?";
}

function getDepth(event: ChatStreamEvent): number | string {
  if (event.details && typeof event.details === "object" && typeof event.details.depth === "number") {
    return event.details.depth;
  }
  return "?";
}

function getBranchCount(event: ChatStreamEvent): number {
  if (event.details && typeof event.details === "object" && typeof event.details.branch_count === "number") {
    return event.details.branch_count;
  }
  return 0;
}

function getProvider(event: ChatStreamEvent): string {
  if (event.details && typeof event.details === "object" && typeof event.details.provider === "string") {
    return event.details.provider;
  }
  return "desconocida";
}

function getLearningsCount(event: ChatStreamEvent): number | string {
  if (event.details && typeof event.details === "object" && typeof event.details.learnings_count === "number") {
    return event.details.learnings_count;
  }
  return 0;
}

function getSourceUrlsCount(event: ChatStreamEvent): number {
  if (event.details && typeof event.details === "object" && Array.isArray(event.details.source_urls)) {
    return event.details.source_urls.length;
  }
  return 0;
}

const TERMINAL_EVENT_TYPES = new Set([
  "AnalysisFailed",
  "ResearchCompleted",
]);

function isTerminalEvent(event: ChatStreamEvent): boolean {
  return TERMINAL_EVENT_TYPES.has(event.event_type) || event.operation_status === "failed";
}

export function useChatStream(query: string | null, idempotencyKey: string | null) {
  const sourceRef = useRef<EventSource | null>(null);
  const keyRef = useRef<string | null>(null);
  const lastEventTimeRef = useRef<number>(Date.now());
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasTerminalRef = useRef(false);

  useEffect(() => {
    if (!query || !idempotencyKey) return;
    if (keyRef.current === idempotencyKey && sourceRef.current) return;

    sourceRef.current?.close();
    sourceRef.current = null;
    keyRef.current = null;
    hasTerminalRef.current = false;
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    const store = useWorkspaceStore.getState();
    store.setIsAnalyzing(true);
    store.setErrorMessage(null);
    lastEventTimeRef.current = Date.now();

    const resetTimeout = () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        const state = useWorkspaceStore.getState();
        const active = state.workspaces.find((w) => w.id === state.activeWorkspaceId);
        if (active?.isAnalyzing) {
          state.setIsAnalyzing(false);
          state.setErrorMessage("Se agoto el tiempo de espera del stream de investigacion.");
          state.addChatMessage({
            id: `timeout-${Date.now()}`,
            role: "assistant",
            content: "El tiempo de espera para la investigacion ha expirado despues de 5 minutos. La investigacion puede estar tomando mas tiempo de lo esperado.",
            metadata: { event_type: "Timeout" },
            createdAt: Date.now(),
          });
        }
        sourceRef.current?.close();
        sourceRef.current = null;
        keyRef.current = null;
      }, 300000);
    };

    resetTimeout();

    const source = streamChatResearch(query, idempotencyKey, (event: ChatStreamEvent) => {
      lastEventTimeRef.current = Date.now();
      resetTimeout();

      const state = useWorkspaceStore.getState();
      const active = state.workspaces.find((w) => w.id === state.activeWorkspaceId);
      if (!active) return;

      if (active.events.some((e) => e.event_id === event.event_id)) {
        return;
      }

      state.addEvent(event);

      if (event.event_type === "PromptImproved") {
        const rawKeywords = event.details?.keywords;
        const keywords = Array.isArray(rawKeywords)
          ? rawKeywords.map((k) => String(k))
          : [];
        if (keywords.length > 0) {
          const mentions: TechnologyMention[] = keywords.map((keyword, index) => ({
            mention_id: `keyword-${index}-${Date.now()}`,
            document_id: event.document_id || "",
            source_type: "text",
            page_number: 0,
            raw_text: keyword,
            technology_name: keyword,
            normalized_name: keyword,
            category: "other",
            confidence: 0.85,
            evidence_spans: [],
            source_uri: "",
          }));
          state.addMentions(mentions);
        }
      }

      if (event.event_type === "ResearchNodeEvaluated") {
        const rawSourceUrls = event.details?.source_urls;
        const sourceUrls = Array.isArray(rawSourceUrls)
          ? rawSourceUrls.map((u) => String(u))
          : [];
        if (sourceUrls.length > 0) {
          const mention: TechnologyMention = {
            mention_id: `branch-${event.event_id}`,
            document_id: event.document_id || "",
            source_type: "text",
            page_number: 0,
            raw_text: `${getProvider(event)} research`,
            technology_name: getTargetTechnology(event),
            normalized_name: getTargetTechnology(event),
            category: "other",
            confidence: 0.9,
            evidence_spans: [],
            source_uri: sourceUrls[0],
          };
          state.addMentions([mention]);
        }
      }

      if (event.event_type === "ReportGenerated" || event.event_type === "ResearchCompleted") {
        const report = event.report;
        if (report && typeof report === "object" && (report as TechnologyReport).report_id) {
          state.setReport(report as TechnologyReport);
        }
      }

      if (event.event_type === "ReportGenerated") {
        const content = getReportContent(event);
        if (content) {
          state.addChatMessage({
            id: event.event_id,
            role: "report",
            content,
            metadata: { event_type: event.event_type },
            createdAt: Date.now(),
          });
        }
      }

      if (event.event_type === "ResearchCompleted") {
        state.addChatMessage({
          id: event.event_id,
          role: "assistant",
          content: "Investigacion completada.",
          metadata: { event_type: event.event_type },
          createdAt: Date.now(),
        });
      }

      if (event.event_type === "AnalysisFailed" || event.operation_status === "failed") {
        const content = getErrorContent(event);
        state.addChatMessage({
          id: event.event_id,
          role: "assistant",
          content,
          metadata: { event_type: event.event_type },
          createdAt: Date.now(),
        });
        state.addChatMessage({
          id: `${event.event_id}-system`,
          role: "system",
          content,
          metadata: { event_type: event.event_type },
          createdAt: Date.now(),
        });
      }

      if (isTerminalEvent(event)) {
        hasTerminalRef.current = true;
        state.setIsAnalyzing(false);
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }
        sourceRef.current?.close();
        sourceRef.current = null;
        keyRef.current = null;
      }
    });

    source.onerror = () => {
      if (hasTerminalRef.current) {
        source.close();
        return;
      }
      const state = useWorkspaceStore.getState();
      state.setErrorMessage("Error de conexion con el stream de chat");
      state.setIsAnalyzing(false);
      state.addChatMessage({
        id: `error-${Date.now()}`,
        role: "assistant",
        content: "Se perdio la conexion con el stream de investigacion. Por favor, intentalo de nuevo.",
        metadata: { event_type: "StreamError" },
        createdAt: Date.now(),
      });
      source.close();
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      sourceRef.current = null;
      keyRef.current = null;
    };

    sourceRef.current = source;
    keyRef.current = idempotencyKey;

    return () => {
      hasTerminalRef.current = true;
      source.close();
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      sourceRef.current = null;
      keyRef.current = null;
    };
  }, [query, idempotencyKey]);
}
