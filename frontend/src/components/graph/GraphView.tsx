"use client";

import { useState } from "react";
import { Network } from "lucide-react";

import dynamic from "next/dynamic";

import { KnowledgeGraph } from "@/components/KnowledgeGraph";
import { GraphNodePopover } from "@/components/graph/GraphNodePopover";
import { GraphModeSelector, type GraphMode } from "@/components/graph/GraphModeSelector";
import { EvidenceDrawer } from "@/components/graph/EvidenceDrawer";
import { useActiveWorkspace } from "@/hooks/useActiveWorkspace";
import type { GraphNodeData } from "@/components/graph/flow/types";

const ComparatorMode = dynamic(
  () => import("@/components/graph/modes/ComparatorMode").then((m) => ({ default: m.ComparatorMode })),
  { ssr: false, loading: () => <LoadingFallback /> },
);

const TimelineMode = dynamic(
  () => import("@/components/graph/modes/TimelineMode").then((m) => ({ default: m.TimelineMode })),
  { ssr: false, loading: () => <LoadingFallback /> },
);

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="size-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export function GraphView() {
  const workspace = useActiveWorkspace();
  const mentions = workspace?.mentions ?? [];
  const report = workspace?.report ?? null;
  const currentDocument = workspace?.currentDocument ?? null;

  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null);
  const [graphMode, setGraphMode] = useState<GraphMode>("technologies");
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const hasMentions = mentions.length > 0;

  if (!workspace) {
    return (
      <div className="relative w-full h-screen overflow-hidden">
        <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground">
          <Network className="size-12 mb-4 opacity-50" />
          <p className="text-sm">Carga un documento o inicia una investigación...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-screen overflow-hidden">
      <div className="absolute top-6 left-6 z-30">
        <GraphModeSelector mode={graphMode} onModeChange={setGraphMode} />
      </div>

      {hasMentions ? (
        <div className="absolute inset-0 flex items-center justify-center">
          {graphMode === "technologies" && (
            <KnowledgeGraph
              documentId={currentDocument?.document_id ?? null}
              mentions={{
                document_id: currentDocument?.document_id ?? "",
                status: "NORMALIZED",
                extracted: mentions,
                normalized: mentions,
                mention_count: mentions.length,
                normalized_count: mentions.length,
              }}
              report={report}
              onNodeSelect={(node) => {
                setSelectedNode(node);
                setEvidenceOpen(true);
              }}
            />
          )}

          {graphMode === "comparator" && (
            <div className="w-full h-full p-6 pt-20">
              <ComparatorMode mentions={mentions} report={report} />
            </div>
          )}

          {graphMode === "timeline" && (
            <div className="w-full h-full p-6 pt-20">
              <TimelineMode mentions={mentions} />
            </div>
          )}

          {graphMode === "technologies" && selectedNode && (
            <GraphNodePopover node={selectedNode} onClose={() => setSelectedNode(null)} />
          )}

          <EvidenceDrawer
            node={evidenceOpen ? selectedNode : null}
            onClose={() => setEvidenceOpen(false)}
          />
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
