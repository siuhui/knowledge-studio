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
  source_id: string;
  title: string;
  source_format: string;
  status: string;
  created_at: string;
  updated_at: string;
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

export interface ApiResponse<T> {
  code: string;
  message: string;
  data: T;
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
