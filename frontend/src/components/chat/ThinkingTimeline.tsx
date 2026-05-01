"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  Atom,
  Zap,
  Wind,
  CheckCircle2,
  ExternalLink,
  FileText,
  Sparkles,
  Clock,
} from "lucide-react";
import { Chip } from "@nextui-org/react";
import { useAppStore } from "@/stores/appStore";

interface TimelineEvent {
  event_id: string;
  event_type: string;
  operation_id?: string;
  sequence?: number;
  details?: any;
  stage_context?: any;
  message?: string;
  report?: any;
}

export function ThinkingTimeline() {
  const [expanded, setExpanded] = useState(false);
  const events = useAppStore((state) => state.events);
  const currentOperation = useAppStore((state) => state.currentOperation);

  const filtered: TimelineEvent[] = events.filter(
    (e) => e.operation_id === currentOperation?.operation_id
  );

  const sorted = [...filtered].sort(
    (a, b) => (a.sequence ?? 0) - (b.sequence ?? 0)
  );

  const lastEvent = sorted[sorted.length - 1];
  const isDone = sorted.some((e) => e.event_type === "ResearchCompleted");
  const label = isDone ? "Razonamiento" : "Razonando...";

  const isTerminal = (type: string) =>
    type === "ResearchCompleted" ||
    type === "ReportGenerated" ||
    type === "AnalysisFailed";

  const getModelIcon = (model?: string | null) => {
    if (!model) return <Brain className="size-4 text-muted-foreground" />;
    const lower = model.toLowerCase();
    if (lower.includes("gemini")) return <Zap className="size-4 text-primary" />;
    if (lower.includes("mistral"))
      return <Wind className="size-4 text-blue-500" />;
    if (lower.includes("gemma"))
      return <Atom className="size-4 text-purple-500" />;
    return <Brain className="size-4 text-muted-foreground" />;
  };

  const getStageIcon = (event: TimelineEvent) => {
    const type = event.event_type;
    if (type === "ResearchCompleted" || type === "ReportGenerated") {
      return <CheckCircle2 className="size-4 text-success" />;
    }
    if (type === "PromptImprovementStarted" || type === "PromptImproved") {
      return <Sparkles className="size-4 text-purple-500" />;
    }
    if (type === "ResearchRequested") {
      return <Atom className="size-4 text-primary" />;
    }
    if (type === "ResearchPlanCreated") {
      return <FileText className="size-4 text-muted-foreground" />;
    }
    if (type === "ResearchNodeEvaluated") {
      return getModelIcon(
        event.details?.provider || event.details?.model
      );
    }
    return <Brain className="size-4 text-muted-foreground" />;
  };

  return (
    <div className="inline-flex flex-col items-start">
      <button
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors px-2 py-0.5 rounded-full bg-white/40 border border-border/20 backdrop-blur-sm"
      >
        <span>{label}</span>
        {!isDone && (
          <span className="inline-flex gap-0.5">
            <span className="size-1 rounded-full bg-current animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="size-1 rounded-full bg-current animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="size-1 rounded-full bg-current animate-bounce" style={{ animationDelay: "300ms" }} />
          </span>
        )}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-2 bg-white/60 backdrop-blur-sm rounded-lg border border-border/30 p-2 max-h-64 overflow-y-auto w-80">
              <div className="space-y-2">
                {sorted.map((event) => {
                  const type = event.event_type;
                  const isLast = lastEvent?.event_id === event.event_id;
                  const active = isLast && !isTerminal(type);
                  const details = event.details || {};
                  const duration = details?.duration_ms;
                  const fallback = details?.fallback_reason;

                  return (
                    <motion.div
                      key={event.event_id}
                      initial={{ opacity: 0, x: -5 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.15 }}
                      className="flex items-start gap-2 border-l border-primary/20 pl-2 py-1 bg-white/40 rounded-md"
                    >
                      <div className="mt-0.5 shrink-0">
                        {active ? (
                          <div className="size-2 rounded-full animate-pulse bg-primary" />
                        ) : (
                          getStageIcon(event)
                        )}
                      </div>
                      <div className="flex-1 min-w-0 space-y-0.5">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[10px] font-medium text-foreground/80">
                            {type === "PromptImprovementStarted"
                              ? "Mejora de prompt"
                              : type === "PromptImproved"
                              ? "Prompt refinado"
                              : type === "ResearchRequested"
                              ? "Investigación solicitada"
                              : type === "ResearchPlanCreated"
                              ? "Plan de investigación"
                              : type === "ResearchNodeEvaluated"
                              ? "Rama evaluada"
                              : type === "ReportGenerated"
                              ? "Reporte generado"
                              : type === "ResearchCompleted"
                              ? "Investigación completada"
                              : type}
                          </span>
                          {duration !== undefined && duration !== null && (
                            <span className="text-[9px] text-muted-foreground flex items-center gap-0.5">
                              <Clock className="size-3" />
                              {duration}ms
                            </span>
                          )}
                          {fallback && (
                            <Chip
                              size="sm"
                              color="warning"
                              variant="flat"
                              className="text-[9px] h-4 px-1"
                            >
                              {fallback}
                            </Chip>
                          )}
                        </div>

                        {type === "PromptImproved" && (
                          <div className="space-y-0.5">
                            {details?.refined_query && (
                              <div className="bg-white/60 rounded px-1.5 py-0.5 text-[10px] text-foreground/80 font-mono break-words">
                                {details.refined_query}
                              </div>
                            )}
                            {Array.isArray(details?.keywords) &&
                              details.keywords.length > 0 && (
                                <div className="flex flex-wrap gap-1">
                                  {details.keywords.map(
                                    (k: string, i: number) => (
                                      <Chip
                                        key={i}
                                        size="sm"
                                        variant="flat"
                                        className="text-[9px] h-4 px-1"
                                      >
                                        {k}
                                      </Chip>
                                    )
                                  )}
                                </div>
                              )}
                          </div>
                        )}

                        {type === "ResearchRequested" && (
                          <div className="space-y-0.5">
                            <div className="text-[10px] text-foreground/80">
                              Investigando:{" "}
                              {details?.target_technology || event.message}
                            </div>
                            {(details?.breadth !== undefined || details?.depth !== undefined) && (
                              <div className="text-[9px] text-muted-foreground/60">
                                {details?.breadth !== undefined && `breadth ${details.breadth}`}
                                {details?.breadth !== undefined && details?.depth !== undefined && " · "}
                                {details?.depth !== undefined && `depth ${details.depth}`}
                              </div>
                            )}
                          </div>
                        )}

                        {type === "ResearchPlanCreated" && (
                          <div className="space-y-0.5">
                            {details?.plan_summary && (
                              <div className="text-[10px] text-foreground/70 line-clamp-1">
                                {details.plan_summary}
                              </div>
                            )}
                            {(details?.branch_count !== undefined ||
                              details?.branches?.length !== undefined) && (
                              <Chip
                                size="sm"
                                variant="flat"
                                className="text-[9px] h-4 px-1"
                              >
                                {details?.branch_count ??
                                  details?.branches?.length}{" "}
                                ramas
                              </Chip>
                            )}
                          </div>
                        )}

                        {type === "ResearchNodeEvaluated" && (
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-1 text-[10px] text-foreground/80">
                              {getModelIcon(
                                details?.provider || details?.model
                              )}
                              <span className="capitalize">
                                {details?.provider ||
                                  details?.model ||
                                  "Modelo"}
                              </span>
                            </div>
                            {Array.isArray(details?.executed_queries) &&
                              details.executed_queries.length > 0 && (
                                <div className="flex flex-wrap gap-1">
                                  {details.executed_queries.map(
                                    (q: string, i: number) => (
                                      <Chip
                                        key={i}
                                        size="sm"
                                        variant="flat"
                                        className="text-[9px] h-4 px-1"
                                      >
                                        {q}
                                      </Chip>
                                    )
                                  )}
                                </div>
                              )}
                            {Array.isArray(details?.source_urls) &&
                              details.source_urls.length > 0 && (
                                <div className="space-y-0.5">
                                  {details.source_urls
                                    .slice(0, 3)
                                    .map((url: string, i: number) => (
                                      <a
                                        key={i}
                                        href={url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-1 text-[10px] text-primary hover:underline truncate"
                                      >
                                        <ExternalLink className="size-3 shrink-0" />
                                        <span className="truncate">
                                          {url}
                                        </span>
                                      </a>
                                    ))}
                                  {details.source_urls.length > 3 && (
                                    <span className="text-[9px] text-muted-foreground">
                                      +{details.source_urls.length - 3} more
                                    </span>
                                  )}
                                </div>
                              )}
                            {Array.isArray(details?.learnings_preview) &&
                              details.learnings_preview.length > 0 && (
                                <div className="space-y-0.5">
                                  {details.learnings_preview.map(
                                    (l: string, i: number) => (
                                      <div
                                        key={i}
                                        className="text-[10px] text-foreground/70 line-clamp-2"
                                      >
                                        • {l}
                                      </div>
                                    )
                                  )}
                                </div>
                              )}
                            {details?.learnings_count !== undefined && (
                              <Chip
                                size="sm"
                                variant="flat"
                                className="text-[9px] h-4 px-1"
                              >
                                {details.learnings_count} aprendizajes
                              </Chip>
                            )}
                          </div>
                        )}

                        {(type === "ReportGenerated" ||
                          type === "ResearchCompleted") && (
                          <div className="space-y-0.5">
                            {(() => {
                              const report =
                                details?.report || event.report;
                              if (!report) return null;
                              return (
                                <>
                                  <div className="text-[9px] text-muted-foreground">
                                    {report.length} caracteres
                                  </div>
                                  <div className="text-[10px] text-foreground/70 truncate">
                                    {report
                                      .replace(/\n/g, " ")
                                      .slice(0, 120)}
                                    {report.length > 120 ? "..." : ""}
                                  </div>
                                </>
                              );
                            })()}
                            {type === "ResearchCompleted" &&
                              details?.branch_count !== undefined && (
                                <Chip
                                  size="sm"
                                  variant="flat"
                                  className="text-[9px] h-4 px-1"
                                >
                                  {details.branch_count} ramas
                                </Chip>
                              )}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
