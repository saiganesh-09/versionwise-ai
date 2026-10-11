/**
 * Typed client for the VersionWise AI backend.
 *
 * Base URL comes from NEXT_PUBLIC_API_BASE_URL (see frontend/.env.example);
 * falls back to the local dev default.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    ...init,
  });
  if (!res.ok) {
    let body: ApiError | null = null;
    try {
      body = (await res.json()) as ApiError;
    } catch {
      // non-JSON error body — fall through to generic message
    }
    throw new Error(body?.error.message ?? `Request failed (${res.status})`);
  }
  // Some success responses have no body (e.g. logout) — don't hard-fail on it.
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/v1/health");
}

// --- Auth ---------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const TOKEN_KEY = "versionwise_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function registerUser(
  email: string,
  fullName: string,
  password: string,
): Promise<UserResponse> {
  return request<UserResponse>("/api/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, full_name: fullName, password }),
  });
}

/** request() + bearer token attached from storage. */
export function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  return request<T>(path, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
}

export function getMe(): Promise<UserResponse> {
  return authRequest<UserResponse>("/api/v1/auth/me");
}

export function logout(): Promise<void> {
  return authRequest<void>("/api/v1/auth/logout", { method: "POST" });
}

// --- Documents & versions -------------------------------------------------

export interface DocumentItem {
  id: string;
  title: string;
  description: string | null;
  document_type: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface VersionItem {
  id: string;
  document_id: string;
  version_number: number;
  original_filename: string;
  file_hash: string;
  effective_from: string;
  effective_until: string | null;
  status: string;
  ingestion_status: string;
  uploaded_by: string;
  uploaded_at: string;
  approved_by: string | null;
  approved_at: string | null;
  supersedes_version_id: string | null;
  extra: Record<string, unknown>;
}

export function listDocuments(): Promise<DocumentItem[]> {
  return authRequest<DocumentItem[]>("/api/v1/documents");
}

export function createDocument(
  title: string,
  documentType = "general",
  description?: string,
): Promise<DocumentItem> {
  return authRequest<DocumentItem>("/api/v1/documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, document_type: documentType, description }),
  });
}

export function getDocument(id: string): Promise<DocumentItem & { versions: VersionItem[] }> {
  return authRequest(`/api/v1/documents/${id}`);
}

export function listVersions(documentId: string): Promise<VersionItem[]> {
  return authRequest<VersionItem[]>(`/api/v1/documents/${documentId}/versions`);
}

export function uploadVersion(
  documentId: string,
  file: File,
  effectiveFrom: string,
  effectiveUntil?: string,
): Promise<VersionItem> {
  const form = new FormData();
  form.append("file", file);
  form.append("effective_from", effectiveFrom);
  if (effectiveUntil) form.append("effective_until", effectiveUntil);
  return authRequest<VersionItem>(`/api/v1/documents/${documentId}/versions`, {
    method: "POST",
    body: form,
  });
}

export function approveVersion(
  versionId: string,
  supersedeVersionId?: string,
): Promise<VersionItem> {
  return authRequest<VersionItem>(`/api/v1/versions/${versionId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      supersedeVersionId ? { supersede_version_id: supersedeVersionId } : {},
    ),
  });
}

export function rejectVersion(versionId: string, reason?: string): Promise<VersionItem> {
  return authRequest<VersionItem>(`/api/v1/versions/${versionId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
}

export interface CompareResult {
  version_a: Record<string, string | number | null>;
  version_b: Record<string, string | number | null>;
  added: string[];
  removed: string[];
  changed_hint: boolean;
}

export function compareVersions(aId: string, bId: string): Promise<CompareResult> {
  return authRequest<CompareResult>(
    `/api/v1/compare?version_a_id=${aId}&version_b_id=${bId}`,
  );
}

// --- Chat ------------------------------------------------------------------

export interface Citation {
  chunk_id: string;
  document_id: string;
  document_title: string;
  version_id: string;
  version_number: number;
  effective_from: string;
  effective_until: string | null;
  page_number: number | null;
  section_title: string | null;
  content: string;
  score: number;
  rank: number;
}

export interface ChatAnswer {
  session_id: string;
  message_id: string;
  status: string;
  answer: string;
  citations: Citation[];
  evidence: Citation[];
  warnings: string[];
  intent: {
    kind: string;
    as_of: string | null;
    compare_a: string | null;
    compare_b: string | null;
    ambiguous: boolean;
    resolved_by: string;
  };
}

export function askChat(
  question: string,
  opts?: { sessionId?: string; asOfDate?: string; documentId?: string },
): Promise<ChatAnswer> {
  return authRequest<ChatAnswer>("/api/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      session_id: opts?.sessionId ?? null,
      document_id: opts?.documentId ?? null,
      as_of_date: opts?.asOfDate ?? null,
    }),
  });
}

// --- Conflicts ---------------------------------------------------------------

export interface ConflictItem {
  id: string;
  document_id: string | null;
  chunk_a_id: string | null;
  chunk_b_id: string | null;
  conflict_type: string;
  explanation: string;
  evidence_a: string;
  evidence_b: string;
  confidence: number | null;
  status: string;
  resolution_note: string | null;
  reviewed_by: string | null;
  created_at: string;
  updated_at: string;
}

export function listConflicts(status?: string): Promise<ConflictItem[]> {
  const q = status ? `?status=${status}` : "";
  return authRequest<ConflictItem[]>(`/api/v1/conflicts${q}`);
}

export function detectConflicts(): Promise<{ candidates_evaluated: number; findings: ConflictItem[] }> {
  return authRequest("/api/v1/conflicts/detect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

export function reviewConflict(
  id: string,
  action: "confirm" | "dismiss" | "resolve",
  note?: string,
): Promise<ConflictItem> {
  return authRequest<ConflictItem>(`/api/v1/conflicts/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, note }),
  });
}

// --- Dashboard / settings ----------------------------------------------------

export interface DashboardStats {
  documents: number;
  versions: number;
  chunks: number;
  versions_by_status: Record<string, number>;
  ingestion_failures: number;
  open_conflicts: number;
  my_chat_sessions: number;
}

export function getDashboardStats(): Promise<DashboardStats> {
  return authRequest<DashboardStats>("/api/v1/dashboard/stats");
}

export interface PublicSettings {
  environment: string;
  llm_provider: string;
  llm_model: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimensions: number;
  object_storage_provider: string;
  chunk_size_tokens: number;
  chunk_overlap_tokens: number;
  retrieval_top_k: number;
  retrieval_similarity_threshold: number;
  max_upload_mb: number;
  access_token_expire_minutes: number;
}

export function getPublicSettings(): Promise<PublicSettings> {
  return authRequest<PublicSettings>("/api/v1/settings/public");
}
