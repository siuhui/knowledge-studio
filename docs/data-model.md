# 核心数据模型

完整数据模型关系图：

```
User ──1:N──> KnowledgeBase ──1:N──> Source ──1:N──> Document ──1:N──> Chunk
                                            │                      │
                                     ChatSession ──1:N──> ChatMessage

Document ──1:1──> DocumentIndexStatus  (chunk/embed 生命周期追踪)
```

9 张表。身份认证 ≠ 权限鉴权——有 User，但**没有** Team / Role / Permission / Audit。

---

## 1. user（用户）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| username | str(64) | 唯一 |
| password_hash | str(256) | bcrypt |
| created_at | datetime | |
| updated_at | datetime | |

## 2. knowledge_base（知识库）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| user_id | UUID FK → user | 归属用户 |
| name | str(255) | 名称 |
| description | text? | 描述 |
| created_at | datetime | |
| updated_at | datetime | |

## 3. source（数据源）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| knowledge_base_id | UUID FK → knowledge_base | 归属 |
| type | enum(`upload`, `url`, `github`) | 数据源类型（v0.1.0 启用 `upload`/`url`，`github` 预留给 v0.2.0） |
| config | JSON | 类型相关配置 |
| source_hash | str(64)? | SHA-256 原始文件哈希（预留字段，v0.2.0 启用去重逻辑） |
| status | enum(`pending`, `active`, `invalid`) | 配置有效性（非索引进度） |
| created_at | datetime | |
| updated_at | datetime | |

Source `status` 反映配置有效性（S3 对象还在吗？URL 可访问吗？），不反映文档是否已向量化。索引进度归 Document 和 DocumentIndexStatus 管。

## 4. document（文档）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| source_id | UUID FK → source (nullable, SET NULL on delete) | 来源数据源 |
| knowledge_base_id | UUID FK → knowledge_base | 所属知识库（`source_id` 可为 NULL，此字段是 document→KB 的唯一可靠路径） |
| title | str(255) | 文档标题 / 文件名 |
| path | text? | 原始路径或 URL |
| source_format | str(50) | 原始文件格式（pdf / markdown / text），解析后内容统一为纯文本 |
| full_text | text | 解析后的全文（清洗后） |
| text_hash | str(64) | SHA-256 解析文本哈希，决定是否重新 chunk + embed |
| status | enum(`pending`, `processing`, `ready`, `failed`) | 内容生命周期（不含 chunk/embed 状态） |
| doc_version | str(32) | 版本号，默认 "1" |
| created_at | datetime | |
| updated_at | datetime | |

`Document.status` 只管内容解析（parse 是否成功），chunk 和 embed 的状态拆分到 `DocumentIndexStatus` 1:1 扩展表。

## 5. document_index_status（索引状态）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| document_id | UUID FK → document (unique, CASCADE) | 1:1 关联 |
| chunk_status | enum(`pending`, `running`, `done`, `failed`) | 分块阶段状态 |
| chunk_count | int? | 分块数量 |
| chunked_at | datetime? | 分块完成时间 |
| embed_status | enum(`pending`, `running`, `done`, `failed`) | 向量化阶段状态 |
| embed_count | int? | 向量化数量 |
| embedded_at | datetime? | 向量化完成时间 |
| error_stage | str(20)? | 失败阶段（chunk / embed） |
| error_message | text? | 错误详情 |
| embedding_model | str(100)? | 使用的 embedding 模型名 |
| index_version | str(32)? | 索引版本号 |
| created_at | datetime | |
| updated_at | datetime | |

**为什么拆成 1:1 扩展表**：Document 管内容生命周期，DocumentIndexStatus 管派生数据（chunk + embed）的管线执行状态。分开避免把业务状态和管线执行状态混在一张表里。

## 6. chunk（切片）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| doc_id | UUID FK → document | 归属文档 |
| chunk_index | int | 切片序号 |
| content | text | 文本内容 |
| token_count | int | token 数 |
| embedding | vector(N) | pgvector 向量（nullable，embed 阶段写入；维度由 `KS_EMBEDDING__DIMENSION` 配置，默认 1024） |
| index_version | str(32) | 索引版本，默认 "1" |
| created_at | datetime | |

## 7. chat_session（对话会话）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| knowledge_base_id | UUID FK → knowledge_base | 所属知识库 |
| user_id | UUID FK → user | 所属用户 |
| title | str(255) | 会话标题（首条消息自动生成） |
| reference_document_ids | JSON | 限定检索的文档 ID 列表 |
| last_message_at | datetime? | 最后一条消息时间 |
| created_at | datetime | |
| updated_at | datetime | |

## 8. chat_message（对话消息）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| session_id | UUID FK → chat_session (CASCADE) | 所属会话 |
| role | str(20) | `user` / `assistant` |
| content | text | 消息内容 |
| citations | JSON | 引用来源列表 |
| created_at | datetime | |

---

## 处理管线 vs 数据模型

```
处理管线（函数）              数据模型（表）
─────────────                ────────────
Source 配置                  → source 表
  ↓
拉取原始文件                  → 对象存储/MinIO（不建表）
  ↓
解析 + 清洗 → 纯文本          → document.full_text + text_hash
  ↓
分块                         → chunk 表（content + chunk_index）
  ↓                             document_index_status.chunk_status
向量化                       → chunk.embedding
                                document_index_status.embed_status
```

中间步骤是管道里的临时变量，只需在 document、document_index_status 和 chunk 三层持久化。不要为每个管线阶段建表。

---

## 版本对比与去重

两层哈希，职责不同：

```
source_hash        → "原始文件变没变？"     → 决定是否重新解析
text_hash          → "解析结果变没变？"     → 决定是否重新 chunk + embedding
```

| Hash | 位置 | 算法 | v0.1.0 状态 |
|------|------|------|----------|
| `source.source_hash` | Source 表 | SHA-256 原始文件 | **预留字段**，暂不启用逻辑 |
| `document.text_hash` | Document 表 | SHA-256 解析后的纯文本 | **已启用** |

**v0.1.0 只启用 `text_hash`**，因为它直接决定要不要重新 chunk 和 embedding——这是 RAG 管道里最贵的步骤。

**示例**：

```
第一次上传 A.pdf → 解析出 "Hello World" → text_hash = "abc123" → 索引
第二次上传同一个 A.pdf → 解析出 "Hello World" → text_hash = "abc123" → 跳过
升级解析器后 A.pdf → 解析出 "Hello World !" → text_hash = "def456" ≠ "abc123" → 重新索引
```

`source_hash` 的逻辑（原始文件去重）留到 v0.2.0 启用，那时候数据源类型多了（GitHub/URL 定时同步），文件级去重才有实际价值。

---

## 设计要点

- 身份认证 vs 权限鉴权分离——有 User，无 Role/Team/Permission
- `knowledge_base.user_id` 标注归属，多用户隔离靠查询过滤
- `document.text_hash` 去重（启用），`source.source_hash` 预留（v0.2.0）
- pgvector `vector(N)`，维度可配置（`KS_EMBEDDING__DIMENSION`），`<=>` 余弦距离
- `DocumentIndexStatus` 1:1 解耦内容生命周期与管线执行状态
- `ChatSession` + `ChatMessage` 管理多轮对话历史与引用

> 架构决策（检索策略、agent 运行时、SSE 流式）见 @docs/architecture.md。
