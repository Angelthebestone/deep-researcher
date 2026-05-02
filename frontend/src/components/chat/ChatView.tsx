"use client";

import { useEffect, useRef, useState, useMemo, type ComponentProps } from "react";
import {
  Skeleton,
  Tabs,
  Tab,
  Card,
  ScrollShadow,
  Chip,
} from "@nextui-org/react";
import { Slider as NextUISlider } from "@nextui-org/slider";
import { BookOpen, FileCheck, Settings } from "lucide-react";

function Slider(props: {
  size?: string;
  minValue?: number;
  maxValue?: number;
  value?: number;
  onChange?: (value: number) => void;
  className?: string;
}) {
  return <NextUISlider {...(props as unknown as ComponentProps<typeof NextUISlider>)} />;
}
import { useActiveWorkspace } from "@/hooks/useActiveWorkspace";
import { useWorkspaceStore } from "@/stores/workspaceStore";
import { useChatStream } from "@/hooks/useChatStream";
import { MessageBubble } from "./MessageBubble";
import { ThinkingTimeline } from "./ThinkingTimeline";
import { ChatInputBar } from "./ChatInputBar";

export function ChatView() {
  const [activeQuery, setActiveQuery] = useState<string | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  useChatStream(activeQuery, activeKey);

  const workspace = useActiveWorkspace();
  const chatMessages = workspace?.chatMessages ?? [];
  const isAnalyzing = workspace?.isAnalyzing ?? false;
  const currentOperation = workspace?.currentOperation ?? null;
  const mentions = workspace?.mentions;
  const researchParams = workspace?.researchParams ?? {
    depth: 2,
    breadth: 3,
    freshness: "past_year",
    max_sources: 10,
    contextFiles: [],
  };
  const setResearchParam = useWorkspaceStore((state) => state.setResearchParam);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleStartStream = (query: string, idempotencyKey: string) => {
    setActiveQuery(query);
    setActiveKey(idempotencyKey);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, isAnalyzing]);

  const lastMessage = chatMessages[chatMessages.length - 1];
  const showThinking =
    isAnalyzing ||
    (currentOperation?.status === "running" && lastMessage?.role !== "assistant");
  const showTyping = isAnalyzing && lastMessage?.role !== "assistant";

  const sourceUrls = useMemo(() => {
    const urls = (mentions ?? []).map((m) => m.source_uri).filter(Boolean);
    return Array.from(new Set(urls));
  }, [mentions]);

  const evidenceSpans = useMemo(() => {
    return (mentions ?? []).flatMap((m) => m.evidence_spans);
  }, [mentions]);

  return (
    <div className="flex">
      <div
        className={`flex-1 min-w-0 transition-all duration-300 ${
          panelOpen ? "mr-[280px]" : ""
        }`}
      >
        <div className="mx-auto max-w-3xl pt-24 pb-40 px-4">
          <div className="space-y-6">
            {chatMessages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}

            {showThinking && (
              <div className="my-1">
                <ThinkingTimeline />
              </div>
            )}

            {showTyping && (
              <div className="flex justify-start gap-2">
                <div className="size-2 rounded-full bg-primary animate-pulse shrink-0 mt-1" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-[250px] rounded-lg" />
                  <Skeleton className="h-4 w-[200px] rounded-lg" />
                  <Skeleton className="h-4 w-[180px] rounded-lg" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        <ChatInputBar
          onStartStream={handleStartStream}
          panelOpen={panelOpen}
          onTogglePanel={() => setPanelOpen((v) => !v)}
        />
      </div>

      {panelOpen && (
        <aside className="fixed right-0 top-0 h-full w-[280px] z-30 border-l border-border/20 bg-background/70 backdrop-blur-xl shadow-[-20px_0_60px_rgba(0,0,0,0.04)] flex flex-col">
          <div className="p-4 border-b border-border/20 flex items-center justify-between">
            <span className="text-sm font-semibold text-foreground">
              Contexto
            </span>
            <button
              type="button"
              onClick={() => setPanelOpen(false)}
              className="text-sm font-medium text-foreground hover:text-muted-foreground transition-colors"
            >
              X
            </button>
          </div>

          {!workspace ? (
            <div className="flex-1 flex items-center justify-center p-4">
              <p className="text-sm text-muted-foreground text-center">
                Selecciona un workspace
              </p>
            </div>
          ) : (
            <Tabs
              fullWidth
              size="sm"
              aria-label="Contexto del chat"
              classNames={{
                base: "flex-1 flex flex-col",
                panel: "flex-1 p-0 overflow-hidden",
              }}
            >
              <Tab
                key="fuentes"
                title={
                  <div className="flex items-center gap-1.5">
                    <BookOpen className="size-3.5" />
                    <span>Fuentes</span>
                  </div>
                }
              >
                <ScrollShadow className="h-full p-4">
                  {sourceUrls.length === 0 ? (
                    <p className="text-xs text-muted-foreground">Sin fuentes</p>
                  ) : (
                    <div className="space-y-2">
                      {sourceUrls.map((url, i) => (
                        <Card
                          key={`${url}-${i}`}
                          className="p-2 bg-transparent border border-border/30"
                        >
                          <p className="text-xs text-foreground break-all">
                            {url}
                          </p>
                        </Card>
                      ))}
                    </div>
                  )}
                </ScrollShadow>
              </Tab>

              <Tab
                key="evidencias"
                title={
                  <div className="flex items-center gap-1.5">
                    <FileCheck className="size-3.5" />
                    <span>Evidencias</span>
                  </div>
                }
              >
                <ScrollShadow className="h-full p-4">
                  {evidenceSpans.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      Sin evidencias
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {evidenceSpans.map((span) => (
                        <Card
                          key={span.evidence_id}
                          className="p-2 bg-transparent border border-border/30"
                        >
                          <p className="text-xs font-medium text-foreground capitalize">
                            {span.evidence_type}
                          </p>
                          <p className="text-xs text-muted-foreground line-clamp-3">
                            {span.text}
                          </p>
                          <p className="text-[10px] text-muted-foreground mt-1">
                            Página {span.page_number}
                          </p>
                        </Card>
                      ))}
                    </div>
                  )}
                </ScrollShadow>
              </Tab>

              <Tab
                key="configuracion"
                title={
                  <div className="flex items-center gap-1.5">
                    <Settings className="size-3.5" />
                    <span>Configuración</span>
                  </div>
                }
              >
                <ScrollShadow className="h-full p-4 space-y-6">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-foreground">
                        Profundidad
                      </span>
                      <Chip size="sm" variant="flat">
                        {researchParams.depth}
                      </Chip>
                    </div>
                    <Slider
                      size="sm"
                      minValue={1}
                      maxValue={5}
                      value={researchParams.depth}
                      onChange={(v: number) =>
                        setResearchParam("depth", Number(v))
                      }
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Exploración</span>
                      <span>Investigación profunda</span>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-foreground">
                        Amplitud
                      </span>
                      <Chip size="sm" variant="flat">
                        {researchParams.breadth}
                      </Chip>
                    </div>
                    <Slider
                      size="sm"
                      minValue={1}
                      maxValue={5}
                      value={researchParams.breadth}
                      onChange={(v: number) =>
                        setResearchParam("breadth", Number(v))
                      }
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Focalizado</span>
                      <span>Panorámico</span>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-foreground">Antigüedad</span>
                      <Chip size="sm" variant="flat">
                        {researchParams.freshness === "past_month" ? "Último mes" : researchParams.freshness === "past_year" ? "Último año" : "Cualquier fecha"}
                      </Chip>
                    </div>
                    <select
                      value={researchParams.freshness}
                      onChange={(e) => setResearchParam("freshness", e.target.value)}
                      className="w-full text-sm bg-transparent border border-border/30 rounded-lg p-2 text-foreground"
                    >
                      <option value="past_month">Último mes</option>
                      <option value="past_year">Último año</option>
                      <option value="any">Cualquier fecha</option>
                    </select>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-foreground">Fuentes máximas</span>
                      <Chip size="sm" variant="flat">{researchParams.max_sources}</Chip>
                    </div>
                    <Slider
                      size="sm"
                      minValue={1}
                      maxValue={20}
                      value={researchParams.max_sources}
                      onChange={(v: number) => setResearchParam("max_sources", Number(v))}
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>1 fuente</span>
                      <span>20 fuentes</span>
                    </div>
                  </div>
                </ScrollShadow>
              </Tab>
            </Tabs>
          )}
        </aside>
      )}
    </div>
  );
}
