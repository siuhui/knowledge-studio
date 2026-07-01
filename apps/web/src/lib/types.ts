export interface KnowledgeBase {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Source {
  id: string;
  knowledge_base_id: string;
  type: string;
  config: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: string;
  source_id: string | null;
  title: string;
  source_format: string;
  status: string;
  chunk_status: string | null;
  embed_status: string | null;
  created_at: string;
  updated_at: string;
}

/** A single indexed chunk within a document */
export interface DocumentChunk {
  id: string;
  chunk_index: number;
  content: string;
  token_count: number;
}

/** Full document detail returned by GET /api/v1/documents/{id}/chunks */
export interface DocumentDetail {
  id: string;
  source_id: string | null;
  title: string;
  source_format: string;
  status: string;
  chunk_status: string | null;
  embed_status: string | null;
  created_at: string;
  updated_at: string;
  chunk_count: number;
  truncated: boolean;
  chunks: DocumentChunk[];
}

// ── Panel state (workspace right panel) ──

export type PanelState =
  | { type: "empty" }
  | { type: "source"; sourceId: string }
  | { type: "document"; documentId: string };

// ── Derived / UI types ──

/** A source with its documents resolved — used in tabbed sidebar */
export interface SourceNode {
  id: string;
  name: string;
  type: "upload" | "link";
  status: string;
  documents: SourceDocument[];
}

export interface SourceDocument {
  id: string;
  sourceId: string;
  title: string;
  version: string;
  description: string;
  status: string;
  chunkStatus: string | null;
  embedStatus: string | null;
}

/** Flattened document row for display.
 *  sourceId/sourceName/sourceType are undefined for orphaned docs (source deleted). */
export interface FlatDocument {
  id: string;
  sourceId: string | undefined;
  sourceName: string | undefined;
  sourceType: "upload" | "link" | undefined;
  title: string;
  version: string;
  description: string;
  status: string;
  chunkStatus: string | null;
  embedStatus: string | null;
}

export function flattenDocs(sources: SourceNode[]): FlatDocument[] {
  return sources.flatMap((s) =>
    s.documents.map((d) => ({
      id: d.id,
      sourceId: s.id,
      sourceName: s.name,
      sourceType: s.type,
      title: d.title,
      version: d.version,
      description: d.description,
      status: d.status,
      chunkStatus: d.chunkStatus,
      embedStatus: d.embedStatus,
    })),
  );
}

export interface Citation {
  document_id: string;
  document_title: string;
  chunk_index: number;
  content_snippet: string;
}

export interface RetrievalChunk {
  chunk_id: string;
  content: string;
  score: number;
  document_title: string;
  citation: Citation;
}

export interface QaResponse {
  query: string;
  answer: string;
  sources: Citation[];
}

// ── Session & Chat ──

export interface SessionItem {
  id: string;
  knowledge_base_id: string;
  user_id: string;
  title: string;
  message_count: number;
  reference_document_ids: string[] | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MessageItem {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  created_at: string;
}

export interface SessionDetail extends SessionItem {
  messages: MessageItem[];
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  answer: string;
  citations: Citation[];
  persisted: boolean;
}

export interface ApiResponse<T> {
  code: string;
  message: string;
  data: T | null;
}

export interface PaginatedResponse<T> {
  code: string;
  message: string;
  data: T[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface PaginatedMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PresignRequest {
  filename: string;
  content_type: string;
}

export interface PresignResponse {
  provider: string;
  bucket: string;
  object_key: string;
  upload_url: string;
  upload_fields: Record<string, string>;
  expires_in: number;
  max_size_bytes: number;
}

export interface UploadCompleteRequest {
  bucket: string;
  object_key: string;
  etag?: string | null;
}

export interface UploadCompleteResponse {
  accepted: boolean;
  object_key: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
}

// ── Streaming events ──

export type StreamEvent =
  | { type: "session"; session_id: string; user_msg_id: string }
  | { type: "token"; text: string }
  | { type: "citation"; citations: Citation[] }
  | { type: "done"; persisted: boolean; ai_message_id?: string }
  | { type: "error"; message: string };

export class ApiError extends Error {
  code: string;
  status: number;
  requestId: string;

  constructor(code: string, message: string, status: number, requestId: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}
