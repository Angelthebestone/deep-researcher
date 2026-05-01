"use client";

import { useState } from "react";
import { Network } from "lucide-react";

import { KnowledgeGraph } from "@/components/KnowledgeGraph";
import { GraphNodePopover } from "@/components/graph/GraphNodePopover";
import { useAppStore } from "@/stores/appStore";
import type { GraphNode } from "@/components/KnowledgeGraph";

export function GraphView() {
  const mentions = useAppStore((state) => state.mentions);
  const report = useAppStore((state) => state.report);
  const currentDocument = useAppStore((state) => state.currentDocument);

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const hasMentions = mentions.length > 0;

  return (
    <div className="relative w-full h-screen overflow-hidden">
      {hasMentions ? (
        <div className="absolute inset-0 flex items-center justify-center">
          <KnowledgeGraph
            documentId={currentDocument?.document_id ?? null}
            mentions={
              {
                document_id: currentDocument?.document_id ?? "",
                status: "NORMALIZED",
                extracted: mentions,
                normalized: mentions,
                mention_count: mentions.length,
                normalized_count: mentions.length,
              }
            }
            report={report}
            onNodeSelect={setSelectedNode}
          />
          {selectedNode && (
            <GraphNodePopover node={selectedNode} onClose={() => setSelectedNode(null)} />
          )}
        </div>
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground">
          <Network className="size-12 mb-4 opacity-50" />
          <p className="text-sm">
            Carga un documento o inicia una investigación para visualizar el grafo de conocimiento
          </p>
        </div>
      )}
    </div>
  );
}
