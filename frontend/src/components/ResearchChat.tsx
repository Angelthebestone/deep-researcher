"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { AlertCircle, LoaderCircle, Sparkles } from "lucide-react";

import { Chip } from "@nextui-org/react";
import { Button } from "@nextui-org/react";
import { Card, CardBody, CardHeader, CardFooter } from "@nextui-org/react";
import { Input } from "@nextui-org/react";
import { Divider } from "@nextui-org/react";
import { streamChatResearch } from "@/lib/api";
import type { ChatStreamEvent } from "@/types/contracts";

import { ResearchEventStream } from "./ResearchEventStream";
import { ResearchProgress } from "./ResearchProgress";

function buildChatIdempotencyKey(query: string) {
  const slug =
    query
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "research";
  const uniqueSeed = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}`;
  return `chat:${slug}:${uniqueSeed}`;
}

export function ResearchChat() {
  const [query, setQuery] = useState("");
  const [events, setEvents] = useState<ChatStreamEvent[]>([]);
  const [report, setReport] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "connecting" | "live" | "complete" | "failed">("idle");
  const [error, setError] = useState<string | null>(null);
  const [operationId, setOperationId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);
  const finalizedRef = useRef(false);

  useEffect(() => {
    return () => {
      sourceRef.current?.close();
    };
  }, []);

  const latestEvent = useMemo(() => events[events.length - 1] ?? null, [events]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery || isRunning) {
      return;
    }

    sourceRef.current?.close();
    finalizedRef.current = false;
    setError(null);
    setReport(null);
    setEvents([]);
    setOperationId(null);
    setStatus("connecting");
    setIsRunning(true);

    const idempotencyKey = buildChatIdempotencyKey(trimmedQuery);
    const source = streamChatResearch(trimmedQuery, idempotencyKey, (payload) => {
      setEvents((current) => (current.some((item) => item.event_id === payload.event_id) ? current : [...current, payload]));
      setOperationId(payload.operation_id);

      if (typeof payload.report === "string") {
        setReport(payload.report);
      }

      if (payload.event_type === "ResearchCompleted") {
        finalizedRef.current = true;
        setStatus("complete");
        setIsRunning(false);
        setReport(typeof payload.report === "string" ? payload.report : null);
        source.close();
      }

      if (payload.operation_status === "failed") {
        finalizedRef.current = true;
        setStatus("failed");
        setIsRunning(false);
        setError(payload.message || "La investigación falló.");
        source.close();
      }
    });

    source.onopen = () => {
      setStatus("live");
    };

    source.onerror = () => {
      if (finalizedRef.current) {
        return;
      }
      finalizedRef.current = true;
      setStatus("failed");
      setIsRunning(false);
      setError("El stream SSE se desconectó.");
      source.close();
    };

    sourceRef.current = source;
  }

  return (
    <div className="flex h-full flex-col gap-6 overflow-auto bg-slate-50 p-6 md:p-8">
      <Card className="border-border/70 shadow-soft">
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-display text-2xl">Investigación conversacional</h3>
              <p className="text-sm text-muted-foreground">Envía una consulta real y sigue los 7 eventos SSE del backend validado.</p>
            </div>
            <Chip color={status === "complete" ? "success" : status === "failed" ? "danger" : "secondary"} variant="flat" size="sm">
              {status}
            </Chip>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ej: investiga sobre gasificación de biomasa"
              className="h-11 flex-1"
              disabled={isRunning}
            />
            <Button type="submit" className="h-11 gap-2" disabled={!query.trim() || isRunning}>
              {isRunning ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              Iniciar investigación
            </Button>
          </form>

          {error ? (
            <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircle className="size-4" />
              {error}
            </div>
          ) : null}
        </CardHeader>
      </Card>

      <ResearchProgress events={events} />

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <ResearchEventStream events={events} />

        <Card className="border-border/70 shadow-soft">
          <CardHeader>
            <h3 className="font-display text-xl">Reporte final</h3>
            <p className="text-sm text-muted-foreground">{report ? "Reporte markdown recibido del backend." : "Aun no hay reporte final."}</p>
          </CardHeader>
          <CardBody className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span>Eventos: {events.length}</span>
              <span>•</span>
              <span>Operation: {operationId ?? "pendiente"}</span>
              <span>•</span>
              <span>Ultimo evento: {latestEvent?.event_type ?? "n/a"}</span>
            </div>
            <Divider />
            {report ? (
              <pre className="max-h-[62vh] overflow-auto whitespace-pre-wrap rounded-2xl border border-slate-200 bg-slate-950 p-4 text-sm leading-6 text-slate-100">
                {report}
              </pre>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-sm text-slate-500">
                Escribe una consulta y espera a que llegue el evento <span className="font-medium text-slate-700">ResearchCompleted</span>.
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
