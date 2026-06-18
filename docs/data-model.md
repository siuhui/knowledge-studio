# 核心数据模型

一图：

```
User ──1:N──> KnowledgeBase ──1:N──> Source ──1:N──> Document ──1:N──> Chunk
```

5 张表。身份认证 ≠ 权限鉴权——有 User，但**没有** Team / Role / Permission / Audit。

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
| type | enum(`upload`, `url`, `github`) | 数据源类型（v0.1 仅启用 `upload`，`url`/`github` 预留给 v0.2） |
| config | JSON | 类型相关配置 |
| source_hash | str(64)? | SHA-256 原始文件哈希（预留，v0.2 启用去重） |
| status | enum(`active`,`inactive`,`error`) | |
| created_at | datetime | |
| updated_at | datetime | |

## 4. document（文档）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| source_id | UUID FK → source | |
| title | str(255) | 文档标题 / 文件名 |
| path | text? | 原始路径或 URL |
| source_format | str(50) | 原始文件格式（pdf / markdown / text），解析后 content 统一为纯文本 |
| content | text | 解析后的全文（清洗后） |
| content_hash | str(64) | SHA-256 解析文本哈希，决定是否重新 chunk |
| status | enum(`active`,`processing`,`error`) | |
| doc_version | str(32) | 版本号，默认 "1" |
| created_at | datetime | |
| updated_at | datetime | |

## 5. chunk（切片）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| doc_id | UUID FK → document | |
| chunk_index | int | 切片序号 |
| content | text | 文本内容 |
| token_count | int | token 数 |
| embedding | vector(1536) | pgvector 向量，维度按 embedding 模型定 |
| index_version | str(32) | 索引版本，默认 "1" |
| created_at | datetime | |

---

## 处理管线 vs 数据模型

```
处理管线（函数）              数据模型（表）
─────────────                ────────────
Source 配置                  → source 表
  ↓
拉取原始文件                  → 对象存储/本地文件（不建表）
  ↓
解析 + 清洗 → 纯文本          → document.content
  ↓
分块                         → chunk 表（content + chunk_index）
  ↓
向量化                       → chunk.embedding
```

中间步骤是管道里的临时变量，只需在 document 和 chunk 两层持久化。不要为每个管线阶段建表。

---

## 版本对比与去重

两层哈希，职责不同：

```
source_hash        → "原始文件变没变？"     → 决定是否重新解析
content_hash       → "解析结果变没变？"     → 决定是否重新 chunk + embedding
```

| Hash | 位置 | 算法 | MVP 状态 |
|------|------|------|----------|
| `source.source_hash` | Source 表 | SHA-256 原始文件 | **预留字段**，暂不启用逻辑 |
| `document.content_hash` | Document 表 | SHA-256 解析后的纯文本 | **现在就验** |

**MVP 只启用 `content_hash`**，因为它直接决定要不要重新 chunk 和 embedding——这是 RAG 管道里最贵的步骤。

**示例**：

```
第一次上传 A.pdf → 解析出 "Hello World" → content_hash = "abc123" → 索引
第二次上传同一个 A.pdf → 解析出 "Hello World" → content_hash = "abc123" → 跳过
升级解析器后 A.pdf → 解析出 "Hello World !" → content_hash = "def456" ≠ "abc123" → 重新索引
```

source_hash 的逻辑（原始文件去重）留到 v0.2 启用，那时候数据源类型多了（GitHub/URL 定时同步），文件级去重才有实际价值。

---

---

## 设计要点

- **身份认证**：register / login，JWT token。只回答"你是谁"，不回答"你能干什么"
- **无权限体系**：没有 Role / Team / Permission / Membership
- **knowledge_base 归属**：`knowledge_base.user_id` 标注归属，隔离靠查询过滤
- **Hash 去重**：`document.content_hash` 避免重复 chunk + embedding，`source.source_hash` 预留
- **embedding 存储**：pgvector `vector(1536)` 原生向量类型，支持 `<=>` 余弦距离算子
- **混合检索**：pgvector 语义检索 + PostgreSQL `tsvector` 全文搜索，结果融合排序
