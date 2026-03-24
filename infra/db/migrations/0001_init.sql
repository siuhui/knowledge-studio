-- 0001_init.sql
-- Base schema for v0.1 development

CREATE TABLE IF NOT EXISTS knowledge_source (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  source_type VARCHAR(50) NOT NULL,
  sync_mode VARCHAR(20) NOT NULL DEFAULT 'scheduled',
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  config_json JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_document (
  id UUID PRIMARY KEY,
  source_id UUID NOT NULL REFERENCES knowledge_source(id),
  title VARCHAR(255) NOT NULL,
  path TEXT,
  doc_version VARCHAR(32) NOT NULL DEFAULT '1',
  department VARCHAR(100),
  permission_scope VARCHAR(100) NOT NULL DEFAULT 'default',
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_chunk (
  id UUID PRIMARY KEY,
  doc_id UUID NOT NULL REFERENCES knowledge_document(id),
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  token_count INT NOT NULL DEFAULT 0,
  index_version VARCHAR(32) NOT NULL DEFAULT '1',
  permission_scope VARCHAR(100) NOT NULL DEFAULT 'default',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS index_job (
  id UUID PRIMARY KEY,
  source_id UUID NOT NULL REFERENCES knowledge_source(id),
  mode VARCHAR(20) NOT NULL DEFAULT 'incremental',
  status VARCHAR(20) NOT NULL DEFAULT 'queued',
  error_message TEXT,
  total_documents INT NOT NULL DEFAULT 0,
  indexed_documents INT NOT NULL DEFAULT 0,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS qa_session (
  id UUID PRIMARY KEY,
  user_id VARCHAR(100),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS qa_message (
  id UUID PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES qa_session(id),
  role VARCHAR(20) NOT NULL,
  content TEXT NOT NULL,
  confidence VARCHAR(20),
  grounded BOOLEAN,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS qa_citation (
  id UUID PRIMARY KEY,
  message_id UUID NOT NULL REFERENCES qa_message(id),
  doc_id UUID NOT NULL REFERENCES knowledge_document(id),
  chunk_id UUID NOT NULL,
  score NUMERIC(6,5) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feedback_record (
  id UUID PRIMARY KEY,
  message_id UUID NOT NULL REFERENCES qa_message(id),
  rating VARCHAR(10) NOT NULL,
  comment TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY,
  actor_id VARCHAR(100),
  action VARCHAR(100) NOT NULL,
  resource_type VARCHAR(100) NOT NULL,
  resource_id VARCHAR(100) NOT NULL,
  trace_id VARCHAR(64) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_index_job_source_status ON index_job(source_id, status);
CREATE INDEX IF NOT EXISTS idx_document_source ON knowledge_document(source_id);
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON knowledge_chunk(doc_id, chunk_index);
