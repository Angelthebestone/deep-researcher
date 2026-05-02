export type ChatMessageRole = "user" | "assistant" | "system" | "document" | "mentions" | "report";

export interface ChatMessage {
  id: string;
  role: ChatMessageRole;
  content: string;
  metadata?: Record<string, unknown>;
  createdAt: number;
}
