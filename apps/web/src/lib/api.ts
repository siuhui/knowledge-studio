import {
  ApiError,
  type ChatResponse,
  type Document,
  type DocumentDetail,
  type PaginatedMeta,
  type PresignResponse,
  type SessionDetail,
  type SessionItem,
  type UploadCompleteRequest,
  type UploadCompleteResponse,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── 401 auto-redirect guard ──

let unauthorizedHandled = false;

/** Reset the guard so the next 401 triggers a redirect again. Call after successful login. */
export function resetUnauthorizedFlag(): void {
  unauthorizedHandled = false;
}

function dispatchUnauthorized(status: number, skipUnauthorizedHandler = false): void {
  // skipUnauthorizedHandler lets callers opt out (e.g. login — 401 is a normal "bad credentials" response)
  if (status === 401 && !skipUnauthorizedHandler && !unauthorizedHandled) {
    unauthorizedHandled = true;
    window.dispatchEvent(new Event("auth:unauthorized"));
  }
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("kb_access_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

interface ApiOptions extends RequestInit {
  skipUnauthorizedHandler?: boolean;
}

// ── Shared HTTP layer ──
// Fires the fetch, builds headers, handles 401 and errors.
// Returns the raw Response — callers decide how to consume the body.

interface RequestResult {
  response: Response;
  requestId: string;
}

async function request(path: string, options?: ApiOptions): Promise<RequestResult> {
  const { skipUnauthorizedHandler = false, ...fetchOptions } = options ?? {};
  const requestId = crypto.randomUUID();
  const response = await fetch(`${BASE_URL}${path}`, {
    ...fetchOptions,
    headers: {
      ...(fetchOptions.method &&
        fetchOptions.method !== "GET" && {
          "Content-Type": "application/json",
        }),
      "X-Request-ID": requestId,
      ...getAuthHeader(),
      ...fetchOptions.headers,
    },
  });
  const rid = response.headers.get("X-Request-ID") || requestId;
  if (!response.ok) {
    dispatchUnauthorized(response.status, skipUnauthorizedHandler);
    const err = await response
      .json()
      .catch(() => ({ code: "NETWORK_ERROR", message: response.statusText }));
    throw new ApiError(err.code, err.message, response.status, rid);
  }
  return { response, requestId: rid };
}

// ── Response consumers ──

export async function api<T>(
  path: string,
  options?: ApiOptions,
): Promise<{ data: T; requestId: string }> {
  const { response, requestId } = await request(path, options);
  // 204 No Content and HEAD responses have no body — don't parse JSON
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return { data: undefined as T, requestId };
  }
  return { data: (await response.json()).data as T, requestId };
}

export async function apiPaginated<T>(
  path: string,
  options?: ApiOptions,
): Promise<{ data: T[]; meta: PaginatedMeta; requestId: string }> {
  const { response, requestId } = await request(path, options);
  const body = await response.json();
  return { data: body.data as T[], meta: body.meta as PaginatedMeta, requestId };
}

// ── Presigned upload helpers ──

export function getContentType(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  const map: Record<string, string> = {
    pdf: "application/pdf",
    md: "text/markdown",
    markdown: "text/markdown",
    txt: "text/plain",
    text: "text/plain",
  };
  return map[ext ?? ""] ?? "application/octet-stream";
}

export async function presignSourceUpload(
  sourceId: string,
  filename: string,
  contentType: string,
): Promise<PresignResponse> {
  const result = await api<PresignResponse>(`/api/v1/sources/${sourceId}/uploads/presign`, {
    method: "POST",
    body: JSON.stringify({ filename, content_type: contentType }),
  });
  return result.data;
}

export async function completeSourceUpload(
  sourceId: string,
  body: UploadCompleteRequest,
): Promise<UploadCompleteResponse> {
  const result = await api<UploadCompleteResponse>(`/api/v1/sources/${sourceId}/uploads/complete`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return result.data;
}

export async function listSourceDocuments(sourceId: string): Promise<Document[]> {
  const result = await apiPaginated<Document>(
    `/api/v1/sources/${sourceId}/documents?page=1&page_size=50`,
  );
  return result.data;
}

export async function listKnowledgeBaseDocuments(kbId: string): Promise<Document[]> {
  const result = await apiPaginated<Document>(
    `/api/v1/knowledge-bases/${kbId}/documents?page=1&page_size=200`,
  );
  return result.data;
}

export async function getDocumentChunks(documentId: string): Promise<DocumentDetail> {
  const result = await api<DocumentDetail>(`/api/v1/documents/${documentId}/chunks`);
  return result.data;
}

export async function uploadToPresignedUrl(
  uploadUrl: string,
  uploadFields: Record<string, string>,
  file: File,
): Promise<void> {
  const formData = new FormData();
  for (const [key, value] of Object.entries(uploadFields)) {
    formData.append(key, value);
  }
  // File must be last for S3/MinIO presigned POST compatibility
  formData.append("file", file);

  const res = await fetch(uploadUrl, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new ApiError("UPLOAD_FAILED", `Upload failed (${res.status}): ${text}`, res.status, "");
  }
}

// ── Chat & Session helpers ──

export async function sendMessage(
  kbId: string,
  content: string,
  sessionId?: string | null,
  referenceDocumentIds?: string[] | null,
): Promise<ChatResponse> {
  const result = await api<ChatResponse>("/api/v1/chat/messages", {
    method: "POST",
    body: JSON.stringify({
      knowledge_base_id: kbId,
      session_id: sessionId ?? null,
      content,
      reference_document_ids: referenceDocumentIds,
    }),
  });
  return result.data;
}

export async function sendMessageStream(
  kbId: string,
  content: string,
  sessionId?: string | null,
  referenceDocumentIds?: string[] | null,
  signal?: AbortSignal,
): Promise<{ stream: ReadableStream<Uint8Array> | null; requestId: string }> {
  const { response, requestId } = await request("/api/v1/chat/messages/stream", {
    method: "POST",
    body: JSON.stringify({
      knowledge_base_id: kbId,
      session_id: sessionId ?? null,
      content,
      reference_document_ids: referenceDocumentIds,
    }),
    signal,
  });
  return { stream: response.body, requestId };
}

export async function listSessions(
  kbId: string,
  page = 1,
  pageSize = 20,
): Promise<{ data: SessionItem[]; meta: PaginatedMeta }> {
  return apiPaginated<SessionItem>(
    `/api/v1/knowledge-bases/${kbId}/sessions?page=${page}&page_size=${pageSize}`,
  );
}

export async function getSession(kbId: string, sessionId: string): Promise<SessionDetail> {
  const result = await api<SessionDetail>(`/api/v1/knowledge-bases/${kbId}/sessions/${sessionId}`);
  return result.data;
}

export async function renameSession(
  kbId: string,
  sessionId: string,
  title: string,
): Promise<SessionItem> {
  const result = await api<SessionItem>(`/api/v1/knowledge-bases/${kbId}/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  return result.data;
}

export async function deleteSession(kbId: string, sessionId: string): Promise<void> {
  await api(`/api/v1/knowledge-bases/${kbId}/sessions/${sessionId}`, {
    method: "DELETE",
  });
}
