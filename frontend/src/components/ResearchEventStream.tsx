"use client";

import { useEffect, useRef } from "react";
import { Chip } from "@nextui-org/react";
import { Card, CardBody, CardHeader, CardFooter } from "@nextui-org/react";
import { Divider } from "@nextui-org/react";
import { cn } from "@/lib/utils";
import type { ChatStreamEvent } from "@/types/contracts";
import { ChevronDown, ChevronRight, Clock3, Database, FileText, Network, Sparkles } from "lucide-react";

function eventIcon(eventType: string) {
  if (eventType === "PromptImproved" || eventType === "PromptImprovementStarted") return Sparkles;
  if (eventType === "ResearchRequested" || eventType === "ResearchPlanCreated") return Network;
  if (eventType === "ResearchNodeEvaluated") return Database;
  if (eventType === "ReportGenerated" || eventType === "ResearchCompleted") return FileText;
  return Clock3;
}

function formatStageContext(event: ChatStreamEvent) {
  const context = event.stage_context ?? event.details?.stage_context;
  if (!context || typeof context !== "object" || Array.isArray(context)) {
    return null;
  }
  return context as Record<string, unknown>;
}

export function ResearchEventStream({ events }: { events: ChatStreamEvent[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <Card className="border-border/70 shadow-soft">
      <CardHeader>
        <h3 className="font-display text-xl">Eventos SSE</h3>
        <p className="text-sm text-muted-foreground">Registro en vivo del flujo de investigación.</p>
      </CardHeader>
      <CardBody className="space-y-3">
        {events.length ? (
          events.map((event) => {
            const Icon = eventIcon(event.event_type);
            const stageContext = formatStageContext(event);
            return (
              <details
                key={event.event_id}
                className={cn(
                  "group rounded-2xl border bg-white p-4",
                  event.operation_status === "failed" ? "border-red-200 bg-red-50/60" : "border-slate-200",
                )}
                open={event === events[events.length - 1]}
              >
                <summary className="flex cursor-pointer list-none items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <Icon className="size-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-slate-900">{event.event_type}</p>
                        <Chip color={event.operation_status === "completed" ? "success" : "secondary"} variant="flat" size="sm">#{event.sequence}</Chip>
                        <Chip color={event.operation_status === "failed" ? "danger" : "default"} variant={event.operation_status === "failed" ? "flat" : "bordered"} size="sm">{event.operation_status}</Chip>
                      </div>
                      <p className="text-xs text-slate-500">{event.message}</p>
                    </div>
                  </div>
                  <span className="mt-1 text-slate-400 group-open:hidden">
                    <ChevronRight className="size-4" />
                  </span>
                  <span className="mt-1 hidden text-slate-400 group-open:inline">
                    <ChevronDown className="size-4" />
                  </span>
                </summary>

                <Divider className="my-3" />

                <div className="grid gap-3 text-sm">
                  <div className="flex flex-wrap gap-3 text-xs text-slate-500">
                    <span>Operation: {event.operation_id}</span>
                    <span>•</span>
                    <span>Evento: {event.event_id}</span>
                  </div>
                  {stageContext ? (
                    <div className="grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 sm:grid-cols-2">
                      {Object.entries(stageContext).map(([key, value]) => (
                        <div key={key} className="break-words">
                          <span className="font-medium text-slate-700">{key}:</span>{" "}
                          {typeof value === "string" || typeof value === "number" || typeof value === "boolean"
                            ? String(value)
                            : JSON.stringify(value)}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  <pre className="overflow-auto rounded-xl bg-slate-950 p-3 text-xs text-slate-100">
                    {JSON.stringify(event.details ?? {}, null, 2)}
                  </pre>
                  {typeof event.report === "string" ? (
                    <pre className="overflow-auto rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-950 whitespace-pre-wrap">
                      {event.report}
                    </pre>
                  ) : null}
                </div>
              </details>
            );
          })
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-500">
            Todavia no hay eventos para mostrar.
          </div>
        )}
        <div ref={endRef} />
      </CardBody>
    </Card>
  );
}
