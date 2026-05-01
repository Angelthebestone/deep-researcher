"use client";

import { motion } from "framer-motion";
import { FileText } from "lucide-react";
import { Chip } from "@nextui-org/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "@/stores/appStore";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === "user") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-end"
      >
        <div className="bg-lime-50 text-lime-900 rounded-lg px-4 py-2">
          <p className="text-sm leading-relaxed">{message.content}</p>
        </div>
      </motion.div>
    );
  }

  if (message.role === "assistant") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-start gap-2"
      >
        <div className="prose prose-sm max-w-none prose-headings:text-lime-700 prose-a:text-lime-600 text-foreground">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
      </motion.div>
    );
  }

  if (message.role === "document") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-start"
      >
        <div className="inline-flex items-center gap-2 bg-muted/30 rounded-full px-3 py-1">
          <FileText className="size-4 text-muted-foreground" />
          <span className="text-sm text-foreground">{message.content}</span>
        </div>
      </motion.div>
    );
  }

  if (message.role === "mentions") {
    const names = message.content
      .split(",")
      .map((n) => n.trim())
      .filter(Boolean);

    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-start"
      >
        <div className="flex flex-wrap gap-2">
          {names.map((name) => (
            <Chip key={name} size="sm" color="success" variant="flat">
              {name}
            </Chip>
          ))}
        </div>
      </motion.div>
    );
  }

  if (message.role === "report") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-start w-full"
      >
        <div className="w-full bg-white/50 rounded-lg p-4">
          <p className="text-xs text-muted-foreground mb-2">Reporte de investigacion</p>
          <div className="prose prose-sm max-w-none prose-headings:text-lime-700 prose-a:text-lime-600 text-foreground">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex justify-start"
    >
      <p className="text-sm leading-relaxed text-foreground/70">
        {message.content}
      </p>
    </motion.div>
  );
}
