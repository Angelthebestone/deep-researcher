"use client";

import { useEffect, useRef, useState } from "react";
import { Skeleton } from "@nextui-org/react";
import { useAppStore } from "@/stores/appStore";
import { useChatStream } from "@/hooks/useChatStream";
import { MessageBubble } from "./MessageBubble";
import { ThinkingTimeline } from "./ThinkingTimeline";
import { ChatInputBar } from "./ChatInputBar";

export function ChatView() {
  const [activeQuery, setActiveQuery] = useState<string | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);

  useChatStream(activeQuery, activeKey);

  const chatMessages = useAppStore((state) => state.chatMessages);
  const isAnalyzing = useAppStore((state) => state.isAnalyzing);
  const currentOperation = useAppStore((state) => state.currentOperation);
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
    isAnalyzing || (currentOperation?.status === "running" && lastMessage?.role !== "assistant");
  const showTyping = isAnalyzing && lastMessage?.role !== "assistant";

  return (
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

      <ChatInputBar onStartStream={handleStartStream} />
    </div>
  );
}
