import type {
  AnalysisStreamEvent,
  DocumentUploadResponse,
  OperationRecord,
  TechnologyMention,
  TechnologyReport,
} from "@/types/contracts";
import type { ChatMessage } from "@/types/chat";

export type WorkspaceStatus = "borrador" | "revisión" | "aprobado" | "publicado";

export interface Workspace {
  id: string;
  name: string;
  status: WorkspaceStatus;
  createdAt: number;
  updatedAt: number;

  events: AnalysisStreamEvent[];
  chatMessages: ChatMessage[];
  researchParams: {
    depth: number;
    breadth: number;
    contextFiles: File[];
  };
  currentOperation: OperationRecord | null;
  currentDocument: DocumentUploadResponse | null;
  mentions: TechnologyMention[];
  report: TechnologyReport | null;
  isAnalyzing: boolean;
  errorMessage: string | null;
}

export interface WorkspaceCreateInput {
  name: string;
  status?: WorkspaceStatus;
}
