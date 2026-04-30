export type SourceType = "pdf" | "image" | "docx" | "pptx" | "sheet" | "text";
export type DocumentStatus =
  | "UPLOADED"
  | "PARSED"
  | "EXTRACTED"
  | "NORMALIZED"
  | "RESEARCHED"
  | "REPORTED";
export type OperationType = "research" | "analysis";
export type OperationStatus = "queued" | "running" | "completed" | "failed";
export type TechnologyCategory = "language" | "framework" | "database" | "cloud" | "tool" | "other";
export type ResearchStatus = "current" | "deprecated" | "emerging" | "unknown";
export type ResearchBranchProvider = "gemini_grounded" | "mistral_web_search";
export type EvidenceType = "text" | "ocr" | "table" | "figure" | "caption";
export type RecommendationPriority = "critical" | "high" | "medium" | "low";
export type EffortLevel = "low" | "medium" | "high";
export type ImpactLevel = "low" | "medium" | "high";
export type SeverityLevel = "low" | "medium" | "high" | "critical";

export interface StageContext {
  stage: string;
  model?: string;
  fallback_reason?: string | null;
  duration_ms?: number | null;
  failed_stage?: string | null;
  breadth?: number;
  depth?: number;
}

export interface EvidenceSpan {
  evidence_id: string;
  page_number: number;
  start_char: number;
  end_char: number;
  text: string;
  evidence_type: EvidenceType;
}

export interface TechnologyMention {
  mention_id: string;
  document_id: string;
  source_type: SourceType;
  page_number: number;
  raw_text: string;
  technology_name: string;
  normalized_name: string;
  category: TechnologyCategory;
  confidence: number;
  evidence_spans: EvidenceSpan[];
  source_uri: string;
  vendor?: string;
  version?: string;
  context?: string;
}

export interface AlternativeTechnology {
  name: string;
  reason: string;
  status: ResearchStatus;
  source_urls: string[];
}

export interface ResearchPlanBranch {
  branch_id: string;
  provider: ResearchBranchProvider;
  objective: string;
  queries: string[];
  max_iterations: number;
  search_model: string;
  review_model: string;
  embedding_model: string;
}

export interface ResearchPlan {
  plan_id: string;
  query: string;
  target_technology: string;
  breadth: number;
  depth: number;
  execution_mode: "serial";
  plan_summary: string;
  branches: ResearchPlanBranch[];
  consolidation_model: string;
}

export interface EmbeddingRelation {
  relation_id: string;
  source_embedding_id: string;
  target_embedding_id: string;
  similarity: number;
  reason: string;
}

export interface EmbeddingArtifact {
  embedding_id: string;
  branch_id: string;
  iteration: number;
  query: string;
  model: string;
  source_text: string;
  vector: number[];
  relations: EmbeddingRelation[];
}

export interface ResearchBranchResult {
  branch_id: string;
  provider: ResearchBranchProvider;
  objective: string;
  search_model: string;
  review_model: string;
  executed_queries: string[];
  learnings: string[];
  source_urls: string[];
  iterations: number;
  embeddings: EmbeddingArtifact[];
}

export interface TechnologyResearch {
  technology_name: string;
  status: ResearchStatus;
  summary: string;
  checked_at: string;
  breadth?: number;
  depth?: number;
  latest_version?: string | null;
  release_date?: string | null;
  alternatives?: AlternativeTechnology[];
  source_urls?: string[];
  visited_urls?: string[];
  learnings?: string[];
  fallback_history?: string[];
  stage_context?: StageContext;
}

export interface DocumentScopeItem {
  document_id: string;
  source_uri: string;
  title?: string;
  mime_type?: string;
  uploaded_at?: string | null;
}

export interface InventoryItem {
  technology_name: string;
  normalized_name: string;
  category: TechnologyCategory;
  status: ResearchStatus;
  mention_count: number;
  vendor?: string;
  current_version?: string | null;
  evidence_ids?: string[];
}

export interface ComparisonItem {
  technology_name: string;
  normalized_name: string;
  market_status: ResearchStatus;
  current_version?: string | null;
  latest_version?: string | null;
  version_gap?: string;
  recommendation_summary?: string;
  source_urls?: string[];
  alternatives?: AlternativeTechnology[];
}

export interface RiskItem {
  technology_name: string;
  severity: SeverityLevel;
  description: string;
  evidence_ids?: string[];
  source_urls?: string[];
}

export interface RecommendationItem {
  technology_name: string;
  priority: RecommendationPriority;
  action: string;
  rationale: string;
  effort: EffortLevel;
  impact: ImpactLevel;
  source_urls?: string[];
}

export interface SourceItem {
  title: string;
  url: string;
  retrieved_at: string;
  source_type?: string;
}

export interface TechnologyReport {
  report_id: string;
  generated_at: string;
  executive_summary: string;
  document_scope: DocumentScopeItem[];
  technology_inventory: InventoryItem[];
  comparisons: ComparisonItem[];
  risks: RiskItem[];
  recommendations: RecommendationItem[];
  sources: SourceItem[];
  metadata?: Record<string, unknown> & {
    mention_count?: number;
    technology_count?: number;
    research_count?: number;
    comparison_count?: number;
    risk_count?: number;
    recommendation_count?: number;
    source_count?: number;
    status_counts?: Record<string, number>;
    research_history?: Array<{
      technology_name: string;
      status: ResearchStatus;
      summary: string;
      breadth?: number | null;
      depth?: number | null;
      source_urls?: string[];
      visited_urls?: string[];
      learnings?: string[];
      fallback_history?: string[];
      stage_context?: StageContext;
    }>;
  };
}

export interface DocumentUploadRequest {
  filename: string;
  content: string;
  source_type?: SourceType;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  source_type: SourceType;
  source_uri: string;
  mime_type: string;
  checksum: string;
  size_bytes: number;
  raw_text: string;
  page_count: number;
  uploaded_at: string;
}

export interface DocumentStatusResponse {
  document_id: string;
  status: DocumentStatus;
  last_updated: string;
  error?: string | null;
}

export interface DocumentMentionsResponse {
  document_id: string;
  status: DocumentStatus;
  extracted: TechnologyMention[];
  normalized: TechnologyMention[];
  mention_count: number;
  normalized_count: number;
}

export interface DocumentAnalyzeRequest {
  idempotency_key?: string | null;
}

export interface DocumentAnalyzeResponse {
  document_id: string;
  operation_id: string;
  idempotency_key: string;
  status: OperationStatus;
  report_id?: string | null;
  reused: boolean;
  report?: TechnologyReport | null;
}

export interface OperationEvent {
  event_id: string;
  sequence: number;
  operation_id: string;
  operation_type: OperationType;
  status: OperationStatus;
  created_at: string;
  message?: string;
  node_name?: string;
  event_key?: string;
  details?: Record<string, unknown>;
}

export interface OperationRecord {
  operation_id: string;
  operation_type: OperationType;
  subject_id: string;
  status: OperationStatus;
  created_at: string;
  updated_at: string;
  idempotency_key?: string | null;
  message?: string;
  details?: Record<string, unknown>;
  error?: string;
  event_count?: number;
  events?: OperationEvent[];
}

export interface AnalysisStreamEvent {
  event_id: string;
  sequence: number;
  operation_id: string;
  operation_type: OperationType;
  operation_status: OperationStatus;
  event_type: string;
  message: string;
  document_id: string;
  idempotency_key: string;
  details: Record<string, unknown>;
  stage_context?: StageContext;
  report?: TechnologyReport | string;
}

export interface DashboardSnapshot {
  documentId: string;
  uploadedDocument?: DocumentUploadResponse | null;
  status?: DocumentStatusResponse | null;
  mentions?: TechnologyMention[] | null;
  normalizedMentions?: TechnologyMention[] | null;
  report?: TechnologyReport | null;
  operation?: OperationRecord | null;
  events?: AnalysisStreamEvent[];
  idempotencyKey?: string | null;
  updatedAt: string;
}
