import type {
  AnalysisStreamEvent,
  ChatStreamEvent,
  DocumentAnalyzeRequest,
  DocumentAnalyzeResponse,
  DocumentMentionsResponse,
  DocumentStatusResponse,
  DocumentUploadRequest,
  DocumentUploadResponse,
  OperationRecord,
  TechnologyReport,
} from "@/types/contracts";

type JsonValue = Record<string, unknown>;

function resolveBaseUrl() {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configuredBaseUrl) {
    return configuredBaseUrl.replace(/\/$/, "");
  }

  return "http://127.0.0.1:8000";
}

export function apiBaseUrl() {
  return resolveBaseUrl();
}

function buildUrl(path: string) {
  return new URL(path, `${resolveBaseUrl()}/`).toString();
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return text ? (JSON.parse(text) as T) : ({} as T);
}

export async function uploadDocument(
  payload: DocumentUploadRequest,
): Promise<DocumentUploadResponse> {
  const response = await fetch(buildUrl("/api/v1/documents/upload"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readJson<DocumentUploadResponse>(response);
}

export async function startAnalysis(
  documentId: string,
  payload: DocumentAnalyzeRequest,
): Promise<DocumentAnalyzeResponse> {
  const response = await fetch(buildUrl(`/api/v1/documents/${encodeURIComponent(documentId)}/analyze`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readJson<DocumentAnalyzeResponse>(response);
}

export async function getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
  const response = await fetch(buildUrl(`/api/v1/documents/${encodeURIComponent(documentId)}/status`));
  return readJson<DocumentStatusResponse>(response);
}

export async function getDocumentMentions(documentId: string): Promise<DocumentMentionsResponse> {
  const response = await fetch(buildUrl(`/api/v1/documents/${encodeURIComponent(documentId)}/extract`));
  return readJson<DocumentMentionsResponse>(response);
}

export async function getDocumentReport(documentId: string): Promise<TechnologyReport> {
  const response = await fetch(buildUrl(`/api/v1/documents/${encodeURIComponent(documentId)}/report`));
  return readJson<TechnologyReport>(response);
}

export async function getOperationRecord(operationId: string): Promise<OperationRecord> {
  const response = await fetch(buildUrl(`/api/v1/operations/${encodeURIComponent(operationId)}`));
  return readJson<OperationRecord>(response);
}

export function createAnalyzeStreamUrl(documentId: string, idempotencyKey: string) {
  const url = new URL(
    buildUrl(`/api/v1/documents/${encodeURIComponent(documentId)}/analyze/stream`),
  );
  url.searchParams.set("idempotency_key", idempotencyKey);
  return url.toString();
}

export function createResearchStreamUrl(technology: string, breadth: number, depth: number) {
  const url = new URL(buildUrl("/api/v1/research/stream"));
  url.searchParams.set("technology", technology);
  url.searchParams.set("breadth", String(breadth));
  url.searchParams.set("depth", String(depth));
  return url.toString();
}

export function createChatStreamUrl(query: string, idempotencyKey?: string | null) {
  const url = new URL(buildUrl("/api/v1/chat/stream"));
  url.searchParams.set("query", query);
  if (idempotencyKey) {
    url.searchParams.set("idempotency_key", idempotencyKey);
  }
  return url.toString();
}

export function streamChatResearch(
  query: string,
  idempotencyKey: string,
  onEvent: (event: ChatStreamEvent) => void,
) {
  const source = new EventSource(createChatStreamUrl(query, idempotencyKey));
  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as ChatStreamEvent;
      onEvent(data);
    } catch {
      // Ignore malformed SSE payloads
    }
  };
  return source;
}

export async function readReportMarkdown(documentId: string): Promise<string> {
  const response = await fetch(buildUrl(`/api/v1/documents/${encodeURIComponent(documentId)}/report/download`));
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return text;
}

export function normalizeDetails(details: unknown): JsonValue {
  if (!details || typeof details !== "object" || Array.isArray(details)) {
    return {};
  }
  return details as JsonValue;
}

export function isAnalysisEvent(event: AnalysisStreamEvent): boolean {
  return Boolean(event.event_type);
}
