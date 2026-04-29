import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import type { DashboardSnapshot, DocumentUploadResponse, TechnologyReport } from "@/types/contracts";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() || "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() || "";

export const supabase: SupabaseClient | null =
  SUPABASE_URL && SUPABASE_ANON_KEY
    ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
        },
      })
    : null;

const STORAGE_PREFIX = "vigilador-dashboard:";

function storageKey(documentId: string) {
  return `${STORAGE_PREFIX}${documentId}`;
}

function safeJsonParse(value: string | null): DashboardSnapshot | null {
  if (!value) {
    return null;
  }
  try {
    return JSON.parse(value) as DashboardSnapshot;
  } catch {
    return null;
  }
}

async function writeSupabaseSnapshot(snapshot: DashboardSnapshot) {
  if (!supabase) {
    return;
  }
  await supabase.from("dashboard_snapshots").upsert(
    {
      document_id: snapshot.documentId,
      payload: snapshot,
      updated_at: snapshot.updatedAt,
    },
    { onConflict: "document_id" },
  );
}

async function writeSupabaseArtifact(
  documentId: string,
  artifactType: string,
  payload: Record<string, unknown>,
) {
  if (!supabase) {
    return;
  }
  await supabase.from("dashboard_artifacts").upsert(
    {
      document_id: documentId,
      artifact_type: artifactType,
      payload,
      updated_at: new Date().toISOString(),
    },
    { onConflict: "document_id,artifact_type" },
  );
}

export async function persistDashboardSnapshot(snapshot: DashboardSnapshot) {
  const normalizedSnapshot: DashboardSnapshot = {
    ...snapshot,
    updatedAt: new Date().toISOString(),
  };

  try {
    await writeSupabaseSnapshot(normalizedSnapshot);
  } catch {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(storageKey(snapshot.documentId), JSON.stringify(normalizedSnapshot));
    }
  }
}

export async function persistReportArtifact(
  documentId: string,
  report: TechnologyReport,
  document?: DocumentUploadResponse | null,
) {
  const payload = {
    document_id: documentId,
    report,
    document: document ?? null,
    updated_at: new Date().toISOString(),
  };

  try {
    await writeSupabaseArtifact(documentId, "report", payload);
  } catch {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(`${storageKey(documentId)}:report`, JSON.stringify(payload));
    }
  }
}

export async function loadDashboardSnapshot(documentId: string): Promise<DashboardSnapshot | null> {
  if (supabase) {
    try {
      const { data, error } = await supabase
        .from("dashboard_snapshots")
        .select("payload")
        .eq("document_id", documentId)
        .maybeSingle();
      if (!error && data?.payload && typeof data.payload === "object") {
        return data.payload as DashboardSnapshot;
      }
    } catch {
      // fall through to local storage
    }
  }

  if (typeof window !== "undefined") {
    return safeJsonParse(window.localStorage.getItem(storageKey(documentId)));
  }

  return null;
}
