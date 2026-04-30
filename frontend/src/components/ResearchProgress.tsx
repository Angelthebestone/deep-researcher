"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { ChatStreamEvent } from "@/types/contracts";
import type { LucideIcon } from "lucide-react";
import { CheckCircle2, Clock3, Network, Search, Sparkles, FileText, ArrowUpRight } from "lucide-react";

type ResearchStage = {
  eventType: string;
  label: string;
  description: string;
  icon: LucideIcon;
};

const STAGES: ResearchStage[] = [
  {
    eventType: "PromptImprovementStarted",
    label: "Mejora del prompt",
    description: "Prepara la investigación.",
    icon: Sparkles,
  },
  {
    eventType: "PromptImproved",
    label: "Consulta refinada",
    description: "Normaliza la intención.",
    icon: Search,
  },
  {
    eventType: "ResearchRequested",
    label: "Solicitud enviada",
    description: "Abre la operación de investigación.",
    icon: Network,
  },
  {
    eventType: "ResearchPlanCreated",
    label: "Plan creado",
    description: "Define ramas y profundidad.",
    icon: ArrowUpRight,
  },
  {
    eventType: "ResearchNodeEvaluated",
    label: "Ramas evaluadas",
    description: "Ejecuta la búsqueda y revisión.",
    icon: Clock3,
  },
  {
    eventType: "ReportGenerated",
    label: "Reporte generado",
    description: "Consolida el hallazgo final.",
    icon: FileText,
  },
  {
    eventType: "ResearchCompleted",
    label: "Investigación completada",
    description: "Entrega el resultado final.",
    icon: CheckCircle2,
  },
];

function getCompletedCount(events: ChatStreamEvent[]) {
  const seen = new Set(events.map((event) => event.event_type));
  return STAGES.filter((stage) => seen.has(stage.eventType)).length;
}

export function ResearchProgress({ events }: { events: ChatStreamEvent[] }) {
  const latestEvent = events[events.length - 1] ?? null;
  const completedCount = getCompletedCount(events);
  const percent = events.length ? Math.min(100, Math.round((completedCount / STAGES.length) * 100)) : 0;
  const activeIndex = latestEvent ? STAGES.findIndex((stage) => stage.eventType === latestEvent.event_type) : -1;

  return (
    <Card className="border-border/70 shadow-soft">
      <CardHeader className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="font-display text-xl">Progreso de investigación</CardTitle>
            <CardDescription>Seguimiento de los 7 eventos SSE del backend validado.</CardDescription>
          </div>
          <Badge variant={latestEvent ? "secondary" : "outline"}>
            {latestEvent ? latestEvent.event_type : "Sin eventos"}
          </Badge>
        </div>
        <div className="flex items-center gap-3">
          <Progress value={percent} className="h-2 flex-1" />
          <span className="min-w-12 text-right text-sm font-semibold text-slate-700">{percent}%</span>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {STAGES.map((stage, index) => {
          const Icon = stage.icon;
          const isCompleted = index < activeIndex || (latestEvent?.event_type === stage.eventType && latestEvent.operation_status === "completed");
          const isActive = latestEvent?.event_type === stage.eventType && latestEvent.operation_status !== "completed";

          return (
            <div
              key={stage.eventType}
              className={cn(
                "rounded-2xl border p-4 transition-colors",
                isCompleted ? "border-emerald-200 bg-emerald-50/70" : isActive ? "border-primary/30 bg-primary/5" : "border-slate-200 bg-white",
              )}
            >
              <div className="flex items-start gap-3">
                <div
                  className={cn(
                    "flex size-10 shrink-0 items-center justify-center rounded-xl",
                    isCompleted ? "bg-emerald-100 text-emerald-700" : isActive ? "bg-primary/10 text-primary" : "bg-slate-100 text-slate-500",
                  )}
                >
                  <Icon className="size-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-900">{stage.label}</p>
                  <p className="text-xs text-slate-500">{stage.description}</p>
                  <p className="mt-2 text-[10px] uppercase tracking-[0.18em] text-slate-500">{stage.eventType}</p>
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
