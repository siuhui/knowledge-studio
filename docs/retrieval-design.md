# 检索系统技术设计

> **本文档是检索系统的设计决策信源**，替代 `architecture.md` §三、§四 中关于检索策略层的部分。
> 现状分析见 §一，设计方案见 §二~§六，实施计划见 §七。

---

## 目录

1. [现状分析与问题](#一现状分析与问题)
2. [设计总览](#二设计总览)
3. [组件一：Route & Rewrite（路由 + 查询理解）](#三组件一route--rewrite路由--查询理解)
4. [组件二：Hybrid Retriever（统一检索器）](#四组件二hybrid-retriever统一检索器)
5. [组件三：CRAG 相关性评估](#五组件三crag-相关性评估)
6. [组件四：Agentic Mode（多轮推理）](#六组件四agentic-mode多轮推理)
7. [可观测性与评估指标](#七可观测性与评估指标)
8. [实施计划](#八实施计划)
9. [附录：LLM 调用次数对比](#附录llm-调用次数对比)

---

## 一、现状分析与问题

### 1.1 当前架构

```
策略A: agentic（默认）— AgentRunner + FTS on Document.full_text（'simple'）
        多轮 ReAct，zero embedding，不经过 Chunk
策略B: hybrid（可选）— pgvector cosine on Chunk.embedding
        + FTS on Chunk.content（'english'）+ RRF，单轮检索

ChatService → RetrievalService → AgenticSearchStrategy / HybridSearchStrategy
                                                      ↓
                                              LLM 生成回答（ChatService）
```

两条策略的 FTS 命中**不同的表**（Document.full_text vs Chunk.content），使用**不同的 pg config**（simple vs english）。这是"假选择"的底层原因之一——两条路径无法统一融合。

### 1.2 三个核心问题

| # | 问题 | 根因 | 影响 |
|---|------|------|------|
| 1 | **检索质量和 LLM 推理混在一起** | `agentic` 策略让 LLM 在 ReAct 循环里不断换关键词猜同义词，来弥补纯 FTS 的语义盲区 | 每轮 1 次 LLM 调用，5 轮才能覆盖 2-3 个搜索角度，token 消耗大且不稳定 |
| 2 | **两种策略是假选择** | `agentic` vs `hybrid` 的区别只是"纯FTS+多轮" vs "FTS+向量+单轮"，但它们本应分层——retrieval 方式和 reasoning 深度是正交的 | 用户面临无意义的选择，且两端都没覆盖最优路径 |
| 3 | **检索结果无质量把关** | 无论 FTS 或向量返回什么，ChatService 直接喂给 LLM 生成回答 | 检索结果不相关 → LLM 基于幻觉回答，用户得不到"我找不到"的诚实反馈 |

### 1.3 根因分析

当前 agentic search 的实际工作机制：

```
用户问："怎么加固系统防御"
  Round 1: FTS("加固 系统 防御")    → 0 结果（文档用词是"安全防护"）
  Round 2: FTS("安全防护")          → 3 结果（LLM 猜对了同义词）
  Round 3: read_document(...)        → 深入阅读
  Round 4: FTS("另一个角度")         → 交叉验证
  Round 5: 最终回答
```

LLM 在 ReAct 循环里做了三件不相关的事：**猜同义词**（应该是向量检索的事）、**搜文档**（应该是 retriever 的事）、**判断搜够了没**（应该是 CRAG 评估的事）。每件事都消耗一次 LLM 调用。

另外，pg 的 `'simple'` config 对中文不分词、不处理同义词，`plainto_tsquery` 基本是逐字匹配。对英文有停止词和词干提取的 `'english'` config 又完全不适用于中文。这个底层限制放大了语义盲区。

更深层的问题是**两条策略的 FTS 命中不同的表**——agentic 搜 `Document.full_text`，hybrid 搜 `Chunk.content`。这使得两者的检索结果无法统一融合，也无法共享同一套 FTS 索引。统一到 `Chunk.content` 是解决此问题的前提——两条路径返回同一实体类型，RRF 才能直接融合。

---

## 二、设计总览

### 2.1 核心原则

1. **Direct = Workflow，Agentic = Agent**：简单查询用硬编码 pipeline，复杂查询用 Agent 自主决策
2. **Route & Rewrite 合并为一**：复杂度判断和查询理解（生成聚焦短查询短语、拓展搜索角度）由同一次 LLM 调用完成——理解问题复杂度、提炼核心搜索方向、判断是否需要多角度覆盖，是同一个认知行为，分开反而浪费
3. **一个 retriever，两种用法**：`hybrid_retrieve()` 在 Direct mode 里被代码直接调用，在 Agentic mode 里被包装成 `hybrid_search` 工具
4. **检索粒度统一为 Chunk**：FTS 和 Vector 都命中 `Chunk` 表，返回 `(Chunk, score)`。RRF 直接在同类实体上融合，无需跨表转换。`Chunk.start_offset/end_offset` 提供在 `Document.full_text` 中精确定位和高亮的能力
5. **检索路径独立容错**：FTS 和 Vector 是两条独立路径，并行执行。任一失败 → 返回空列表，另一条继续
6. **CRAG 管质量，不管基础设施**：CRAG 处理"检索成功了但内容不相关"，Retriever 层处理"检索器挂了"。`correct_query` 是 CRAG 的内部 utility，不是独立组件

### 2.2 完整 Pipeline

```
                          Query
                            │
                            ▼
              ┌─ Route & Rewrite (1 LLM) ─┐
              │  decontextualize +       │
              │  classify + lexical_q    │
              └───────────┬──────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
         Direct Mode             Agentic Mode
         (Workflow)              (Agent)
              │                       │
              ▼                       ▼
      hybrid_retrieve()         Agent Loop (2-4 rounds)
      参数由 Route & Rewrite     ┌─────────────────────────┐
      预生成：                  │ Tools:                  │
      - semantic_query(消解后)   │  hybrid_search          │
      - lexical_queries=短查询   │  read_document          │
      (FTS on Chunk.content     │  list_documents         │
       + vector on              └────────────┬────────────┘
       Chunk.embedding                       │
       + RRF)                         Agent final_answer
      1 emb call                    (Agent 自己填 lexical_queries，
              │                      判断搜够了没 / 找不到)
              ▼
         ┌─ CRAG ──┐
         │ + 空判断 │
         │ 重试 1 次│
         └────┬─────┘
              │
              ▼
        Answer / not_found
```

**Route & Rewrite 输出固定 JSON schema，`lexical_queries` 永远有值**：

- **Direct mode**：`lexical_queries` 直接传给 `hybrid_retrieve()` 使用
- **Agentic mode**：`lexical_queries` 作为搜索建议写入 Agent 的 task 描述——Agent 自行决定用、改、还是全部自己生成

**CRAG 只用于 Direct Mode。** Agentic mode 不需要——Agent 自己就是纠错机制（搜不到会换词，不确定会深入读）。Agent 的 final_answer 就是最终判断。

**两种模式的关键区别**：

| | Direct Mode | Agentic Mode |
|---|---|---|
| 本质 | 硬编码 Workflow | LLM 驱动的 Agent |
| lexical_queries 来源 | Route & Rewrite 预生成 | Agent 调 tool 时内联生成 |
| 检索 | `hybrid_retrieve(semantic_query, lexical_queries)` → Chunk | `hybrid_search` → Chunk（Agent 每轮自己填参数） |
| 纠错 | **CRAG**——唯一的外部纠错机会 | **Agent 自己**——搜不到换关键词，不确定深入读 |
| 读取 | 不读全文 | `read_document` — 直接读 `Document.full_text` |
| 找不到 | CRAG 重试 1 次 → not_found | Agent 自己判断并告诉用户 |
| 适用 | 简单 factoid/概念查询 | 多文档对比、多跳推理、隐含假设 |

**为什么不给 Agentic mode 加 CRAG**：Agent 运行完 2-4 轮后已经做出了判断——搜到了就回答，搜不到就说没找到。在循环外面再加一层 CRAG 等于质疑 Agent 的判断。Direct mode 才需要 CRAG——它只做一次检索，没有自我纠错能力。

**Direct Mode 三分支判断**：

```
hybrid_retrieve() → merge_results() → MergedResult
                                    |
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              both_failed      有结果但空       有结果正常
              (两边都挂)    (检索成功,无匹配)       │
                    │               │               │
                    ▼               ▼               ▼
              不进 CRAG         CRAG 评估        CRAG 评估
              fallback_note   (空 → irrelevant)  (质量判断)
              "检索服务          │               │
               暂不可用"          ▼               ▼
                                 │          relevant/partial
                          correct_query 纠正   → 正常回答
                          再空 → not_found
                                 │
                                 ▼
                    三种 fallback 统一交给 LLM
                    用 FALLBACK_SYSTEM_PROMPT
                    让 LLM 基于自身知识回答
                    并告知用户检索状态
```

三种"空/无"的区别：

| | both_failed | not_found | no_documents |
|---|---|---|---|
| 原因 | 基础设施挂了 | KB 确实没有此信息 | 用户没选文档 |
| 检索器 | 两条都异常 | 正常 | 未执行 |
| 处理 | 不进 CRAG | CRAG 纠正后承认 | 直接进入 fallback |
| 回落 | fallback_note → LLM 生成回答，告知用户检索出错 | fallback_note → LLM 生成回答，告知用户未找到 | fallback_note → LLM 生成回答，告知用户未选文档 |

**三种 fallback 不返回硬编码消息，而是交给 LLM**：设置 `fallback_note` 描述具体原因（未选文档 / 未找到 / 检索出错），用 `FALLBACK_SYSTEM_PROMPT` 让 LLM 根据自身知识回答，同时向用户透明说明检索状态。

### 2.3 LLM 调用次数

| 阶段 | Direct | Agentic |
|------|--------|---------|
| Route & Rewrite | 1（decontextualize + classify + lexical_queries） | 1（decontextualize + classify + lexical_queries，作为建议传入 Agent） |
| Agent loop | — | 2-4 |
| CRAG 评估 + 纠错 | 1-2 | —（Agent 自己纠错） |
| Answer Generation | 1 | 0（Agent 的 final_answer） |
| **LLM 总计** | **3-4** | **3-5** |
| **Embedding 调用** | **1** | **1-3** |

**Embedding 数量推理：**

`hybrid_retrieve(semantic_query=original_question, lexical_queries=[...])` 每次调用 1 次 embedding。FTS 对 `lexical_queries` 多路执行，不产生额外 embedding。

- **Direct mode**：`hybrid_retrieve()` 调用 1 次 → **1 emb**
- **Agentic mode**：Agent 调 `hybrid_search`。每轮 1 emb，最多 2-4 轮，但 Agent 不每轮都搜（有 `list_documents` 和 `read_document` 轮次）→ **1-3 emb**

**两条路径用不同输入——这是设计要点：**

```
Route & Rewrite → lexical_queries = ["安全架构设计", "认证与授权机制"]  ← 聚焦短查询，适合 FTS 精确匹配
                   semantic_query = "知识库系统的安全架构是怎么设计的" ← 完整自然语言，适合 vector 语义搜索

hybrid_retrieve(
    semantic_query="知识库系统的安全架构是怎么设计的",
    lexical_queries=["安全架构设计", "认证与授权机制", "system security"])
    ↓
embed("知识库系统的安全架构是怎么设计的") → vector search   ← 1 emb
FTS("安全架构设计") + FTS("认证与授权机制") + FTS("system security")  ← 0 emb
    ↓
RRF 融合
```

---

## 三、组件一：Route & Rewrite（路由 + 查询理解）

### 3.1 职责

判断用户问题复杂度，同时生成语义检索和精确匹配各自需要的输入——`semantic_query`（完整自然语言）和 `lexical_queries`（聚焦短查询短语）。

**复杂度判断和查询理解是同一个认知行为。** 判断"这个问题是简单还是复杂"和"这个问题该从哪几个角度搜"都需要理解问题。分开做两次 LLM 调用是浪费——一次调用同时产出路由决策和检索参数。

- 判为 **simple**（→ Direct mode）：`lexical_queries` 直接传入 `hybrid_retrieve()` 使用
- 判为 **complex**（→ Agentic mode）：`lexical_queries` 作为搜索建议写入 Agent 的 task 描述，Agent 自行决定用、改、或全部自己生成

### 3.2 什么算复杂查询

| Direct mode（简单） | Agentic mode（复杂） |
|---------------------|---------------------|
| 事实查找："JWT 过期时间多久" | 分析："比较文档 A 和 B 的安全方案" |
| 单概念："X 是什么" | 多跳推理："X 为什么导致 Y，怎么解决" |
| 明确有大段文档可回答 | 需要综合多篇文档的碎片信息 |
| 不需要多文档交叉对比 | 包含隐含假设，需要多角度搜索 |

### 3.3 设计

```python
# services/retrieval/rewrite.py

@dataclass
class RewriteResult:
    mode: str                        # "direct" | "agentic"
    reason: str                      # 复杂度判断依据
    semantic_query: str              # 消解代词 + 补全上下文后的自包含问题
    lexical_queries: list[str]       # 聚焦短查询短语，永远有值；Agent 作为建议使用


def route_and_rewrite(
    llm: LLMProvider,
    question: str,
    history: list[tuple[str, str]] | None = None,  # [(role, content), ...]
) -> RewriteResult:
    """1 次 LLM 调用，消解对话引用 + 判断复杂度 + 生成搜索短语。

    输入包含对话历史时，利用上下文将用户问题改写为自包含查询：
    - 消解代词："它" → "知识库系统"
    - 补全省略："认证机制" → 隐含的"怎么设计/实现/配置"
    - 首轮对话 history 为 None 时，semantic_query = 原始问题

    输出固定 JSON schema，不因 mode 而改变结构：
    - semantic_query 永远是消解后的自包含问题
    - lexical_queries 永远有值——direct 时直接使用，agentic 时作为搜索建议
    """
    # ── 构建 prompt（含对话历史消解）──
    if history:
        history_text = "\n".join(f"{role}: {content}" for role, content in history[-6:])
        context_block = f"\nPrevious conversation:\n{history_text}\n\n"
    else:
        context_block = "\n"

    prompt = f"""\
Analyze this question for a RAG retrieval system.{context_block}
Current question: {question}

Step 1 — Decontextualize:
If the question contains pronouns (它/其/这/they/it/this) or is a follow-up that
depends on the conversation above, rewrite it into a self-contained question.
Example: "它的认证机制呢" after discussing "知识库系统安全架构" → rewrite the
semantic_query as "知识库系统的认证机制是怎么设计的". For the first question in a
conversation, the semantic_query stays unchanged from the original.

Step 2 — Complexity classification:
   - "simple": factoid lookup, single concept, one round of retrieval suffices
   - "complex": multi-document comparison, multi-hop reasoning, implicit assumptions

Step 3 — Generate 1-3 focused short query phrases for word-level matching.
   Each phrase targets one search angle — not isolated words but concise phrases.
   Include an English version when the topic has standard English terminology.
   Example: "数据库如何防止SQL注入" → ["SQL注入防护", "参数化查询", "SQL injection prevention"]

Output JSON:
{{"mode": "direct|agentic", "reason": "...", "semantic_query": "<decontextualized>",
  "lexical_queries": ["短语1", "短语2"]}}"""

    response = llm.generate(system_prompt="", messages=[{"role": "user", "content": prompt}])
    return _parse_rewrite_result(response)
```

**lexical_queries 示例**：

```python
# 问题: "知识库系统的安全架构是怎么设计的"
# lexical_queries = ["安全架构设计", "认证与授权机制", "system security architecture"]
#   ↑ 聚焦短语           ↑ 多角度覆盖                ↑ 英文术语（文档中常有对应英文概念）

# 问题: "JWT token 过期时间是多久"
# lexical_queries = ["JWT过期时间", "token expiry"]  — 问题足够明确，不需要拓展角度
```

**lexical_queries 不是孤立关键词，是聚焦短查询短语。** 每个短语是一个独立的搜索方向。在多路 FTS 中，每个短语各自命中；在 RRF 融合中，互补覆盖。

**语义消解示例（多轮对话）**：

```python
# 第一轮: semantic_query 保持原样
route_and_rewrite(
    question="知识库系统的安全架构是怎么设计的",
    history=None)
→ semantic_query = "知识库系统的安全架构是怎么设计的"
  lexical_queries = ["安全架构设计", "认证授权机制"]

# 第二轮（复杂查询——需要多文档对比）: "它" 被消解为 "知识库系统"
route_and_rewrite(
    question="对比它和传统方案的认证机制差异",
    history=[("user", "知识库系统的安全架构是怎么设计的"),
             ("assistant", "该系统采用分层安全架构，包括...")])
→ semantic_query = "对比知识库系统和传统方案的认证机制差异"
  mode = "agentic"
  lexical_queries = ["认证机制对比", "传统方案认证", "authentication comparison"]
  # ↑ 永远有值。Agentic mode 下作为建议写入 Agent task 描述
```

### 3.4 为什么合并路由和查询理解

| | 分开（路由 + 查询理解 各 1 次） | 合并（Route & Rewrite 1 次） |
|---|---|---|
| LLM 调用 | 2 | 1 |
| 共享认知 | 复杂度判断和搜索短语生成都需理解问题——同一件事 | 一次理解产出两项结果 |
| 误判代价 | simple→agentic：Agent 1 轮完成，略多 1 LLM | 同左 |
| | complex→direct：单轮检索不完整，但 CRAG 的 supplement + rewrite 兜底 | 同左 |

### 3.5 为什么用 LLM 而不是规则引擎

- 问题复杂度和问题长度、问号数量没有稳定关联——短问题也可以很复杂（"X 和 Y 什么关系"），长问题也可以很简单
- 生成搜索短语需要语义理解——"怎么加固系统防御"对应的是"安全防护"、"系统加固"，不是字面拆词
- 规则引擎需要持续维护，LLM 成本极低（单次调用，~200 tokens 输出）

---

## 四、组件二：Hybrid Retriever（统一检索器）

### 4.1 职责

唯一的数据检索入口。FTS + 向量两条独立路径，并行执行，任一失败自动退化到另一条。RRF 融合时允许任一为空。

删除 `strategies/agentic.py`，`strategies/hybrid.py` 的逻辑升级后成为唯一的 retriever。

### 4.2 并行检索引擎

```
              语义 + 词汇，双路并行
                         │
         ┌───────────────┼───────────────┐
         ▼                               ▼
   lexical_queries                 semantic_query
   ["短语1", "短语2", "短语3"]     "完整自然语言问题"
         │                               │
         ▼                               ▼
   FTS(q1) FTS(q2) FTS(q3)        Vector Search
   Chunk.content 多路并行          Chunk.embedding
   jieba 分词 → tsvector           pgvector cosine
         │                               │
         ▼                               ▼
    fts_results                     vector_results
    [(Chunk, rank)]                 [(Chunk, similarity)]
    (可以为 [])                      (可以为 [])
         │                               │
         └───────────────┬───────────────┘
                         ▼
                    RRF Merge
              (同类型实体，直接融合)
                         │
                         ▼
                   merged_results
                  [(Chunk, score)]
                         │
                         ▼
              Chunk.start_offset/end_offset
                → Document.full_text 定位/高亮
```

**双路互补**：Vector 做语义兜底（"安全防护" ≈ "系统加固"），FTS 做精确命中（"SQL 注入"这三个字必须在文本中出现）。两条路用不同的输入——`semantic_query` 保留完整自然语言语法，`lexical_queries` 是聚焦短查询短语（1-3 个，每个代表一个独立的搜索方向）。

**FTS 走多路**：`lexical_queries` 有 N 个短语 → FTS 并行执行 N 路 → 合并去重 → RRF 融合。Vector 始终对 `semantic_query` 做一次 embedding。

检索返回 Chunk 后，通过 `start_offset/end_offset` 可在 `Document.full_text` 中精确定位和高亮命中位置。`read_document` 工具仍然直接操作 `Document.full_text`，用于深度阅读。

### 4.3 容错原则

1. **两条检索路径完全独立**——Vector 失败不回滚 FTS，FTS 失败不回滚 Vector
2. **失败 = 返回空列表，不是抛异常**——`embed()` 超时 / pgvector 无索引 / FTS 配置错误 → 对应路径返回 `[]`，另一条继续
3. **RRF 天然处理空列表**——一边为空时退化为纯另一边排序，不需要特殊分支
4. **空结果需要区分原因**——调用方拿到 merged 结果后，根据 error 信息判断：

   | 情况 | FTS | Vector | 含义 | 处理 |
   |------|-----|--------|------|------|
   | 两边成功，都没匹配 | 成功，空 | 成功，空 | KB 里确实没有相关内容 | CRAG → correct_query 纠正 |
   | 一边挂，另一边没匹配 | 挂了，空 | 成功，空 | 可能漏了（挂的那条也许有） | CRAG → correct_query 纠正 |
   | 两边都挂了 | 挂了，空 | 挂了，空 | **检索服务不可用** | 不进 CRAG，设 `fallback_note` → LLM 告知用户检索不可用 |
   | 两边成功，有结果 | 成功 | 成功 | 正常 | CRAG 评估质量 |

   关键：**两边都挂 ≠ 没搜到。** 如果两边都挂还交给 CRAG，会陷入 "空 → correct_query → 重新检索 → 还是空 → ..." 的死循环。

### 4.4 数据结构设计

```python
# services/retrieval/retriever.py（现有文件扩展）

@dataclass
class RetrievalResult:
    """两路检索的原始结果 + 健康信息。
    
    两条路径都返回 Chunk 实体，FTS 命中 Chunk.content (tsvector)，
    Vector 命中 Chunk.embedding (pgvector)。"""
    fts: list[tuple[Chunk, float]]        # 可以为 []
    vector: list[tuple[Chunk, float]]     # 可以为 []
    fts_error: str | None = None          # FTS 路径异常信息
    vector_error: str | None = None       # Vector 路径异常信息


def hybrid_retrieve(
    db: Session,
    *,
    semantic_query: str,            # 完整自然语言问题——用于向量检索
    lexical_queries: list[str],     # 聚焦短查询短语——多路 FTS 精确匹配
    knowledge_base_id: str,
    embedder: Embedder,
    top_k: int = 20,
    document_ids: list[str] | None = None,
) -> RetrievalResult:
    """统一的混合检索入口。

    两条路径用不同的输入，命中同一张表（Chunk）：
    - semantic_query  → embedding → pgvector cosine on Chunk.embedding（语义相似）
    - lexical_queries → 多路 FTS on Chunk.content（jieba 分词后精确匹配）
    
    Chunk.start_offset/end_offset 可用于在 Document.full_text 中定位和高亮。
    """
    # ── FTS 路径（多路并行，独立容错）──
    fts_results: list[tuple[Chunk, float]] = []
    fts_error: str | None = None
    try:
        all_fts: dict[str, tuple[Chunk, float]] = {}
        for query in lexical_queries:
            for chunk, score in _fts_search(db, query, document_ids, top_k):
                if chunk.id not in all_fts or score > all_fts[chunk.id][1]:
                    all_fts[chunk.id] = (chunk, score)
        fts_results = sorted(all_fts.values(), key=lambda x: x[1], reverse=True)[:top_k]
    except Exception as exc:
        fts_error = str(exc)
        logger.warning("fts search failed, degraded to vector-only", error=fts_error)

    # ── Vector 路径（对完整问题做 embedding，独立容错）──
    vector_results: list[tuple[Chunk, float]] = []
    vector_error: str | None = None
    try:
        query_embedding = embedder.embed([semantic_query])[0]
        vector_results = _vector_search(db, query_embedding, document_ids, top_k)
    except Exception as exc:
        vector_error = str(exc)
        logger.warning("vector search failed, degraded to fts-only", error=vector_error)

    # ── 两边都失败 → 不抛异常，返回空结果 ──
    if fts_error and vector_error:
        logger.error("both retrieval paths failed", fts_error=fts_error, vector_error=vector_error)

    return RetrievalResult(
        fts=fts_results,
        vector=vector_results,
        fts_error=fts_error,
        vector_error=vector_error,
    )


@dataclass
class MergedResult:
    """RRF 融合后的最终结果 + 诊断信息。

    chunks 为空时，调用方必须检查 both_failed：
    - both_failed=True  → 检索不可用，不进 CRAG，返回错误
    - both_failed=False → 检索成功但无匹配，交给 CRAG 处理
    """
    chunks: list[tuple[Chunk, float]]
    both_failed: bool = False       # 两路都挂
    fts_error: str | None = None    # 诊断/监控用，调用方自行消费
    vector_error: str | None = None


def merge_results(result: RetrievalResult, top_k: int = 20) -> MergedResult:
    """RRF 融合两路结果。任一路为空时自动退化。

    保留 error 信息，让调用方能区分「检索挂了」和「确实没搜到」。
    """
    merged = _rrf_fusion(result.fts, result.vector, top_k=top_k)
    both_failed = result.fts_error is not None and result.vector_error is not None

    return MergedResult(
        chunks=merged,
        both_failed=both_failed,
        fts_error=result.fts_error,
        vector_error=result.vector_error,
    )
```

**为什么不在 retriever 里抛异常**：三种空结果需要三种处理方式。抛异常只能表达一种（"出错了"），无法区分"两边成功但没搜到"和"两边都挂"。返回 `MergedResult` + error 元数据，让调用方做判断。

### 4.5 RRF 融合与容错退化

RRF（Reciprocal Rank Fusion）的本质是对排名位置加分，而不是信任原始 score 的绝对值：

```
RRF score = Σ 1 / (k + rank_i)    k 默认 60
```

每条结果路径的排名转化为 RRF 分后累加，多路命中同一实体的分数叠加。

**容错退化的实现方式**：`hybrid_retrieve()` 中每条路径失败时返回 `[]`，不是抛异常。`_rrf_fusion()` 的三个循环天然处理四种情况：

```python
def _rrf_fusion(
    vector_results: list[tuple[Chunk, float]],
    fts_results: list[tuple[Chunk, float]],
    top_k: int = 20,
    k: int = 60,
) -> list[tuple[Chunk, float]]:
    scores: dict[str, tuple[Chunk, float]] = {}

    for rank, (chunk, _) in enumerate(vector_results):   # [] → 跳过
        scores[chunk.id] = (chunk, 1.0 / (k + rank + 1))

    for rank, (chunk, _) in enumerate(fts_results):       # [] → 跳过
        rrf = 1.0 / (k + rank + 1)
        if chunk.id in scores:
            prev_chunk, prev_score = scores[chunk.id]
            scores[chunk.id] = (prev_chunk, prev_score + rrf)
        else:
            scores[chunk.id] = (chunk, rrf)

    return sorted(scores.values(), key=lambda x: x[1], reverse=True)[:top_k]
```

| FTS 结果 | Vector 结果 | RRF 输出 | 含义 |
|----------|------------|----------|------|
| 有结果 | 有结果 | 融合排序 | 正常 |
| `[]` | 有结果 | Vector 独占排序 | 退化为纯向量检索 |
| 有结果 | `[]` | FTS 独占排序 | 退化为纯关键词检索 |
| `[]` | `[]` | `[]` | 调用方 `if not merged.chunks` 接管 |

**不需要特殊降级分支**——空列表不参与 RRF 累加，另一边的排名独占最终结果。这就是设计里"RRF 天然处理空列表"的含义。

### 4.6 调用方的空结果处理

调用 `merge_results()` 的代码先判断 `both_failed`，再决定走 CRAG 还是 fallback：

```python
# Direct mode / CRAG 入口（伪代码）

merged = merge_results(hybrid_retrieve(...))

if merged.both_failed:
    # 两边都挂 → 不进 CRAG，设 fallback_note 交给 LLM 生成回答
    fallback_note = "检索服务暂不可用，请稍后重试。"

if not merged.chunks:
    # 检索成功但无结果 → 交给 CRAG（会触发 correct_query → 重新检索）
    pass  # fall through to CRAG

# 正常流程 → CRAG 评估质量 → relevant/partial 正常回答
# CRAG 返回 not_found/error → fallback_note 交给 LLM 生成回答
grade = evaluate_relevance(query, merged.chunks)
# ...
```

**三种 fallback 都交给 LLM 而不是返回硬编码消息**：
- `fallback_note` 描述具体原因（未选文档 / 未找到 / 检索出错）
- 使用 `FALLBACK_SYSTEM_PROMPT` 让 LLM 基于自身知识回答
- LLM 在回答开头向用户透明说明检索情况

### 4.7 Agent tool 也使用同一个 retriever

Agentic mode 的 tool 从 `search_keywords`（纯 FTS）升级为包装 `hybrid_retrieve` + `merge_results`：

```python
# services/agent/tools.py

def _hybrid_search_impl(
    ctx: ToolContext, embedding_query: str, lexical_queries: list[str] | None = None, top_k: int = 5
) -> ToolResult:
    """Agent tool：混合检索（FTS+向量+RRF）。

    - embedding_query: 原始用户问题，用于向量语义检索
    - lexical_queries: 聚焦短查询短语列表，用于 FTS 精确匹配。不传则只用 embedding_query
    内部自动容错——向量挂了走纯 FTS，FTS 挂了走纯向量。
    """
    raw = hybrid_retrieve(
        ctx.db,
        semantic_query=embedding_query,
        lexical_queries=lexical_queries or [embedding_query],
        knowledge_base_id=ctx.kb_id,
        embedder=embedder,
        top_k=top_k,
    )
    merged = merge_results(raw, top_k=top_k)

    # 两边都挂了 → 检索不可用，Agent 无法继续
    if merged.both_failed:
        return ToolResult(
            summary=(
                f"Search is currently unavailable. "
                f"FTS error: {merged.fts_error}. Vector error: {merged.vector_error}. "
                f"Tell the user to try again later."
            ),
            artifacts=[],
            artifact_count=0,
            metadata={"fts_error": merged.fts_error, "vector_error": merged.vector_error},
        )

    # 检索成功但无结果 → 告诉 Agent 换搜索方向
    if not merged.chunks:
        return ToolResult(
            summary=(
                f"No results found. "
                f"Try different lexical_queries or broader terms."
            ),
            artifacts=[],
            artifact_count=0,
            metadata={},
        )

    # ... 构建 ToolResult，与现有一致 ...
```

`read_document` 和 `list_documents` 不变——前者仍直接读 `Document.full_text` 做深度阅读，后者仍列举 `Document` 表。`hybrid_search` 返回 Chunk 粒度结果，Agent 通过 `read_document` 获取完整上下文。

### 4.8 FTS：当前状态与局限

| config | 中文 | 英文 | 使用位置 |
|--------|------|------|----------|
| `'simple'` | 全句视为单 token，基本无效 | 仅 lowercase | `tools.py` — Agent FTS on `Document.full_text` |
| `'english'` | 全句视为单 token，基本无效 | stemming + stopword 归一化 | `retriever.py` — hybrid FTS on `Chunk.content` |

两种 config 对中文都不分词——这是已知局限。设计上由两处补偿：

1. **Vector（语义相似）兜底**：中文"系统加固" ≈ "安全防护"，pgvector cosine 直接覆盖同义词和语义变体，不依赖分词
2. **lexical_queries（多角度精确命中）**：Route & Rewrite 和 Agent 各自生成多路聚焦短查询短语，每个短语从不同角度覆盖搜索意图。一个角度碰不上，另一个角度能命中

当前迭代不做中文分词扩展。后续可考虑 PGroonga / OpenSearch 等方案。

### 4.9 lexical_queries 来源策略

不存在独立的 "Query Rewrite" 步骤。`lexical_queries` 是调用方在调用 `hybrid_retrieve()` 或 `hybrid_search()` 时传入的参数——谁调用、谁决定传什么：

| 来源 | 触发时机 | 内容 | 本质 |
|------|----------|------|------|
| Route & Rewrite（§3） | 检索前，对所有查询 | 1-3 个聚焦短查询短语 | 永远生成——Direct 直接使用，Agentic 作为建议传入 |
| Agent 内联生成（§6） | Agent 调 `hybrid_search` 时 | 根据搜索进展动态生成，可能直接复用建议、修改、或全新生成 | Agent 拥有最终决定权 |
| CRAG `correct_query`（§5） | CRAG irrelevant 后纠正重搜 | 分析上次为什么搜歪了，换方向 | CRAG 内部 utility 函数，输入含失败结果 |

---

## 五、组件三：CRAG 相关性评估

### 5.1 职责

评估检索结果是否足以回答用户问题——**只处理"检索成功但质量不足"。**

| CRAG 负责 | 不属于 CRAG |
|-----------|------------|
| 结果全部不相关（搜歪了） | Vector/FTS 基础设施故障（已在 §4 Retriever 层容错） |
| 结果部分相关（缺角度） | embedding API 超时 |
| 结果不够完整（需补充） | 数据库连接断开 |

如果两边检索器都挂了 → `both_failed=True` → 不进 CRAG，设 `fallback_note` 交给 LLM，让 LLM 告知用户检索不可用。

### 5.2 死循环问题：搜不到 vs 不存在

CRAG 的 `irrelevant` 分支会触发 correct_query + 重新检索。但如果知识库里**真的没有**用户要的信息，会出现：

```
搜索 → 空 → CRAG(irrelevant) → correct_query → 重新检索 → 空 → CRAG(irrelevant) → correct_query → ...
```

**这跟两边都挂是不同的：**

| 情况 | 原因 | 检索器状态 | 处理 |
|------|------|-----------|------|
| 两边都挂 | embedding API 超时 + FTS 异常 | `both_failed=True` | 不进 CRAG，设 fallback_note → LLM 告知用户检索不可用 |
| 搜不到（query 差） | 用词不对，换个角度就有 | 正常，空或 irrelevant | CRAG 纠正 → 重新检索 → 可能找到 |
| **KB 确实没有** | 知识库不包含此信息 | 正常，空或 irrelevant | 纠正后也找不到 → **承认找不到** |

**解决：重试上限 = 1 次。** CRAG 的 correct_query 最多执行一次。第二次还是 irrelevant → 承认找不到。

```python
# CRAG 决策（伪代码）

def crag_evaluate_and_act(
    query: str,
    merged: MergedResult,
    retry_count: int,              # 0 = 首次检索，1 = 已纠正过一次
    llm: LLMProvider,
    retriever: ...,
) -> CragResult:
    # 基础设施故障 → 不进 CRAG
    if merged.both_failed:
        return CragResult(action="error", message="检索服务暂不可用")

    # 检索成功但结果为空，且已重试过 → 承认找不到
    if not merged.chunks and retry_count >= 1:
        return CragResult(action="not_found", message="知识库中未找到相关信息")

    # CRAG 评估
    grade, reason = evaluate_relevance(llm, query, merged.chunks)

    if grade == "relevant":
        return CragResult(action="answer", chunks=merged.chunks)

    if grade == "partial":
        supplement = _supplement_search(llm, query, merged.chunks, retriever)
        return CragResult(action="answer", chunks=merged.chunks + supplement)

    if grade == "irrelevant":
        if retry_count >= 1:
            # 已重试过，KB 确实没有
            return CragResult(action="not_found", message="知识库中未找到相关信息")
        # 首次 irrelevant → correct_query 纠正方向后重新检索
        corrected = correct_query(llm, query, _summarize(merged.chunks))
        new_retrieval = RetrievalService.search(db, query=corrected.queries[0], ...)
        new_chunks = _chunks_from_response(new_retrieval)
        return crag_evaluate_and_act(query, MergedResult(chunks=new_chunks), retry_count=1, ...)
```

**关键：最多一次 rewrite。** 不需要 LLM 判断"KB 里有没有"（它判断不了），靠经验法则——搜了两次，换了角度，还是找不到，就是没有。

### 5.3 相关性评估实现

```python
# services/retrieval/crag.py

from enum import StrEnum

class RelevanceGrade(StrEnum):
    RELEVANT = "relevant"        # 结果充分，直接生成回答
    PARTIAL = "partial"          # 部分相关，需要补充一次定向检索
    IRRELEVANT = "irrelevant"    # 完全不相关，需要换方向重搜


def evaluate_relevance(
    llm: LLMProvider,
    question: str,
    results: list[RetrievalChunk],
) -> tuple[RelevanceGrade, str]:
    """CRAG 相关性评估 — 1 次 LLM 调用。

    返回 (等级, 理由)。理由是 LLM 的判断依据，用于前端展示和日志。
    """
    if not results:
        return RelevanceGrade.IRRELEVANT, "No results found"

    # 构建结果摘要——不传全文，只传 snippet，控制 token
    summaries = []
    for i, r in enumerate(results[:10]):
        summaries.append(
            f"[{i+1}] {r.document_title}: {r.content[:200]}..."
        )

    prompt = f"""\
Evaluate whether these search results can answer the user's question.

Question: {question}

Search results:
{chr(10).join(summaries)}

Judge:
- "relevant"   — results contain enough information to answer the question
- "partial"    — results are on-topic but incomplete, need targeted supplementary search
- "irrelevant" — results are off-topic or empty

Output JSON:
{{"grade": "relevant|partial|irrelevant", "reason": "brief explanation"}}"""

    response = llm.generate(system_prompt="", messages=[{"role": "user", "content": prompt}])
    return _parse_crag_result(response)
```

### 5.4 完整决策流程（含重试上限）

```python
@dataclass
class CragResult:
    action: str           # "answer" | "not_found" | "error"
    chunks: list[RetrievalChunk]
    message: str | None   # not_found 或 error 时的用户消息


def crag_evaluate_and_act(
    db: Session,
    query: str,
    merged: MergedResult,
    retry_count: int,              # 0 = 首次检索，1 = 已纠正过一次
    llm: LLMProvider,
    kb_id: str,
) -> CragResult:
    """CRAG 完整流程：评估 + 决策 + 重试控制。

    retry_count 上限 = 1。也就是最多纠正一次。
    超过后仍 irrelevant → 承认 KB 中没有相关信息。
    
    重搜通过 RetrievalService.search() —— 在 Phase 1（CRAG 引入时）兼容两种现有策略，
    Phase 3 后统一走 Direct mode 的 hybrid_retrieve。
    """
    # ── 基础设施故障 → 不进 CRAG ──
    if merged.both_failed:
        return CragResult(action="error", message="检索服务暂不可用，请稍后重试", chunks=[])

    # ── 检索成功但结果为空，且已重试过 → not_found ──
    if not merged.chunks and retry_count >= 1:
        return CragResult(action="not_found", message="知识库中未找到相关信息，请尝试换个问题", chunks=[])

    # ── CRAG 评估 ──
    grade, reason = evaluate_relevance(llm, query, merged.chunks)

    if grade == "relevant":
        return CragResult(action="answer", message=None, chunks=merged.chunks)

    if grade == "partial":
        supplement = _generate_supplement_query(llm, query, merged.chunks)  # 额外 1 次 LLM
        sup_retrieval = RetrievalService.search(db, query=supplement, knowledge_base_id=kb_id, ...)
        sup_chunks = _chunks_from_response(sup_retrieval)
        all_chunks = merged.chunks + sup_chunks
        return CragResult(action="answer", message=None, chunks=all_chunks)

    if grade == "irrelevant":
        if retry_count >= 1:
            # 已重试过一次，知识库确实没有
            return CragResult(action="not_found", message="知识库中未找到相关信息", chunks=[])
        # 首次 irrelevant → correct_query 纠正方向 + 重新检索（retry_count=1）
        corrected = correct_query(llm, query, _summarize(merged.chunks))
        new_retrieval = RetrievalService.search(db, query=corrected.queries[0], knowledge_base_id=kb_id, ...)
        new_chunks = _chunks_from_response(new_retrieval)
        return crag_evaluate_and_act(
            db, query, MergedResult(chunks=new_chunks), retry_count=1, llm=llm, kb_id=kb_id,
        )
```

**为什么是 1 次纠错上限**

不需要 LLM 判断 "KB 里有没有"——它判断不了。靠经验法则：搜两次（原始 query + correct_query 纠正），换了角度，还是找不到 → 就是没有。再多也是浪费 token。

**LLM 调用计数说明**

CRAG 流程最多产生 2 次 LLM 调用（`partial` 分支的 `_generate_supplement_query` 是额外的 1 次 LLM 调用，用于生成定向补充查询；加上 `evaluate_relevance` 本身，共 2 次）。`relevant` 和 `irrelevant`（首次）各只需 1 次 evaluate。所以附录中 CRAG 列计为 1-2 次。

**三种终态**（CRAG 返回给 chat.py 的决策；chat.py 按 action 分流）

| action | 触发条件 | chat.py 处理 |
|--------|---------|-------------|
| `answer` | relevant 或 partial（补充后） | chunks → RAG context → LLM 正常回答 |
| `not_found` | 两次检索仍 irrelevant，或结果始终为空且已 retry | `fallback_note` → `FALLBACK_SYSTEM_PROMPT` → LLM 基于自身知识回答并告知用户 |
| `error` | both_failed | `fallback_note` → `FALLBACK_SYSTEM_PROMPT` → LLM 告知用户检索不可用 |

### 5.5 为什么是 1 次 LLM 调用而不是 FTS 和向量各评估一次

- RRF 已经把两路结果融合成一个排序列表，不需要分别评估
- 要回答的问题是"这些文档能回答用户吗"，不是"FTS 搜得好不好"或"向量搜得好不好"
- 分别评估增加 LLM 调用次数且产生不一致的判断——FTS 结果评委说 "relevant"、向量评委说 "irrelevant"，然后呢？

---

## 六、组件四：Agentic Mode（多轮推理）

### 6.1 职责

处理需要多跳推理、跨文档综合、迭代搜索的复杂查询。保留当前的 AgentRunner + ReAct 循环，但做以下改动：

Route & Rewrite 输出的 `lexical_queries` 作为搜索建议写入 Agent task 描述——Agent 不是从零理解问题，而是收到分析过的搜索方向：

```python
# Direct mode — 直接传给 retriever
result = hybrid_retrieve(
    semantic_query=rewrite.semantic_query,
    lexical_queries=rewrite.lexical_queries,
    ...)

# Agentic mode — 作为建议写入 task，Agent 拥有最终决定权
task = f"""Answer this question using the knowledge base.

Question: {rewrite.semantic_query}

Suggested starting search angles: {rewrite.lexical_queries}
Use hybrid_search() to explore. You may start from these suggestions,
modify them, or generate entirely new search phrases as needed."""

agent.run(task, ctx)
```

Agent 在每轮调 `hybrid_search` 时自己填 `lexical_queries`——可以直接复用 Route & Rewrite 的建议、改一两个方向、或者搜了一轮发现方向不对后全部替换。

| 项目 | 现状 (agentic) | 改造后 (agentic) |
|------|---------------|-------------------|
| 检索 tool | `search_keywords`（纯 FTS on Document.full_text） | `hybrid_search`（FTS on Chunk.content + Vector on Chunk.embedding + RRF） |
| 深度阅读 | `read_document`（Document.full_text） | `read_document`（不变，仍直接读 Document.full_text） |
| `max_rounds` | 5 | 4 |
| system prompt | 强调 "cross-validate, search from different angles" | task 描述中包含 Route & Rewrite 建议的 lexical_queries，Agent 自行决定用、改或替换 |
| 适用场景 | 所有查询（默认策略） | 仅复杂查询 |
| 早停 | `early_stop_patience=2` | 不变 |

### 6.2 工具设计原则

Agent 模式只有三个工具——刻意为之。每多一个工具，模型在决策时就要多考虑一个选项。评判标准来自 Anthropic 的 ACI（Agent-Computer Interface）理念和行业四层评估框架：

**工具数量**：Claude Code 总共约 20 个工具，RAG Agent 只需 3 个——`list_documents`（发现）、`hybrid_search`（搜索）、`read_document`（阅读）。三个职责正交：Agent 不会困惑"该用哪个"。

**四层评估**：

| 层 | 指标 | `hybrid_search` | `list_documents` | `read_document` |
|----|------|-----------------|-------------------|-----------------|
| **1. Tool Selection** | Agent 是否选对工具 | 中风险：需关注 Agent 是否跳过搜索直接盲读 | 低风险 | 低风险 |
| **2. Argument Extraction** | 参数是否正确 | **高风险**：`lexical_queries` 质量决定检索效果；`embedding_query` 需随搜索意图演进 | 无参数 | 中风险：`offset` 可能算错 |
| **3. Result Utilization** | 是否真正使用工具返回的内容 | Agent 的回答能否追溯到 Chunk 内容 | N/A | Agent 是否引用实际读到的内容 |
| **4. Error Recovery** | 失败时如何恢复 | 空结果时应换 `lexical_queries`，而非用幻觉填充 | N/A | 错误 UUID 时从错误信息学习，重新获取正确 UUID |

**关键设计决策**：

1. **不拆 `hybrid_search` 为 `vector_search` + `keyword_search`**：Agent 不需要知道底层有两个检索引擎。拆成两个会制造"我该用哪个"的选择负担，且两者的结果在 RRF 融合后才形成完整图景——分开调用反而让 Agent 拿到不完整的信息做判断。

2. **`embedding_query` 不锁死在原始问题上**：首轮用原始问题是对的（保留完整语义），但 Agent 在多轮搜索中意图会演进——Round 2 可能在深入某个具体子话题。锁死 `embedding_query` 会让向量检索的语义优势在多轮中失效。（见 §6.3 `hybrid_search` 参数描述）

3. **`read_document` 需要明确的 Chunk→Document 映射引导**：Agent 从 `hybrid_search` 拿到 Chunk（带 `start_offset`），需要在 tool description 里明确告诉它"用 chunk 的 start_offset 作为 read_document 的 offset"——这对人类是常识，对 Agent 是一个容易出错的推理跳转。

4. **`list_documents` 是 `hybrid_search` 的前置依赖**：Agent 必须先用 `list_documents` 获取 UUID，才能用 `document_ids` 限定搜索范围。这个依赖关系在 system prompt 的工作流描述中明确写出。

### 6.3 Agent 的 tool 集（共三个）

```python
# services/agent/tools.py

hybrid_search = _ToolDef(
    name="hybrid_search",
    description=(
        "Hybrid search (full-text + semantic vector) across all documents in one call. "
        "Takes two kinds of input that serve different purposes: "
        "embedding_query for semantic (vector) similarity, "
        "lexical_queries for exact word matching via full-text search. "
        "If lexical_queries is omitted, the embedding_query is used for FTS as well."
    ),
    parameters={
        "type": "object",
        "properties": {
            "embedding_query": {
                "type": "string",
                "description": (
                    "A natural language description of what you're looking for in THIS search round. "
                    "For the first search, use the original user question. "
                    "In follow-up rounds when you've narrowed your focus (e.g. from '对比A和B的安全方案' "
                    "to 'OAuth token刷新的具体实现'), refine this to match your current search intent — "
                    "the semantic search works better when the query reflects what you actually want to find."
                ),
            },
            "lexical_queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "1-3 focused short query phrases for exact word matching. "
                    "Not isolated keywords — use concise phrases like 'SQL注入防护' or 'RBAC权限模型'. "
                    "Generate phrases that target different search angles. "
                    "Each phrase runs as an independent FTS query; results are merged via RRF. "
                    "Omit to use embedding_query for FTS as well."
                ),
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of document UUIDs to limit the search scope. Omit to search all documents.",
            },
            "top_k": {"type": "integer", "default": 5},
        },
        "required": ["embedding_query"],
    },
    execute=_hybrid_search_impl,
)

read_document = _ToolDef(
    name="read_document",
    description=(
        "Read a portion of a document's full text by character offset. "
        "Use this to get full surrounding context after hybrid_search finds relevant chunks. "
        "IMPORTANT: document_id must be a UUID, never a document title. "
        "TIP: when reading context around a chunk found via hybrid_search, "
        "use the chunk's start_offset directly as the offset parameter."
    ),
    parameters={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": (
                    "UUID of the document to read (e.g. '550e8400-e29b-41d4-a716-446655440000'). "
                    "Must be an exact UUID obtained from list_documents or hybrid_search results. "
                    "Do NOT pass a document title, filename, or any other string — only a UUID."
                ),
            },
            "offset": {
                "type": "integer",
                "default": 0,
                "description": (
                    "Starting character position (0-based). "
                    "When reading around a chunk from hybrid_search, use the chunk's start_offset value directly."
                ),
            },
            "length": {
                "type": "integer",
                "default": 3000,
                "description": "Number of characters to read (default 3000).",
            },
        },
        "required": ["document_id"],
    },
    execute=_read_document_impl,
)

list_documents = _ToolDef(
    name="list_documents",
    description=(
        "List all documents in the knowledge base with their UUIDs, titles, formats, and sizes. "
        "Always call this first to discover what documents are available. "
        "The returned UUIDs are needed for hybrid_search (document_ids parameter) and read_document."
    ),
    parameters={"type": "object", "properties": {}},
    execute=_list_documents_impl,
)
```

`hybrid_search` 返回 Chunk 粒度的搜索结果，`read_document` 仍直接操作 `Document.full_text`。两者分工：search 负责"找到哪些 Chunk 相关"，read 负责"深入读全文"。`Chunk.start_offset/end_offset` 提供从 Chunk 到 Document 的精确映射。

### 6.4 SEARCH_AGENT_CONFIG（改造后）

```python
SEARCH_AGENT_CONFIG = AgentConfig(
    tools=[hybrid_search, read_document, list_documents],
    system_prompt="""\
You are a research assistant answering complex questions from a knowledge base.

Workflow:
1. Call list_documents() to discover available documents and their UUIDs
2. Call hybrid_search(embedding_query=..., lexical_queries=[...]).
   - embedding_query: describe what you're looking for in THIS round.
     First search: use the user's question. Follow-up rounds: refine to match
     your current focus (e.g. if drilling into "OAuth implementation details"
     after an initial comparison search, set embedding_query accordingly).
   - lexical_queries: 1-3 focused short query phrases for exact word matching.
     Use concise phrases (not isolated words), each targeting a different search angle.
     Example: for "数据库SQL注入防护" use ["SQL注入防护", "参数化查询", "SQL injection prevention"].
   - document_ids: if the user has specified which documents to search, pass
     those UUIDs to scope the search. Otherwise omit to search all documents.
3. Use read_document() to get full context around relevant chunks.
   TIP: hybrid_search returns chunks with start_offset — use that value
   directly as the offset parameter in read_document.
4. If a search didn't find what you need, try different lexical_queries
   AND refine the embedding_query to match your new search angle.
5. Synthesize findings and give a final answer with citations, or honestly
   state if the information cannot be found

Stop when you can fully answer the question. Don't over-search.""",
    max_rounds=4,
    early_stop_patience=2,
)
```

轮数从 5 降到 4 的理由：不再需要 LLM 在循环里猜同义词，hybrid retriever 一步覆盖语义变体。但复杂多跳查询仍需 `list_documents → hybrid_search → read_document → hybrid_search（新角度）→ final_answer` 至少 4 轮工具调用，留 1 轮余量。

`GATHER_AGENT_CONFIG` 同步更新：`search_keywords` → `hybrid_search`，其余不变。tools 集与 SEARCH_AGENT_CONFIG 保持一致（`[hybrid_search, read_document, list_documents]`）。

---

## 七、可观测性与评估指标

> 项目已有 Langfuse 基建（`core/telemetry.py`，Langfuse v4 SDK），提供 `@observe()`、`update_current_span()`、`trace_context()`、`get_current_trace_id()`——全部 no-op safe。LLM/Embedding 调用由 `langfuse.openai` 自动追踪。本节定义检索管线的观测规范。

### 7.1 设计原则

1. **基建已有，只加规范**：不引入新依赖。所有埋点使用现有的 `@observe` + `update_current_span`。LLM/Embedding 调用由 `langfuse.openai` 自动捕获为 `generation` / `embedding` 类型，不需要手动 span。
2. **每个 `@observe` 都有 `as_type`**：Langfuse 支持 typed observations（`agent`、`tool`、`retriever`、`chain`、`evaluator`、`generation`、`embedding`），在 UI 中可按类型过滤和聚合。设计中的每个 span 都显式指定 `as_type`，不再依赖 name prefix 区分组件角色。
3. **关键决策点作为 score**：CRAG 的 relevance grade、Route & Rewrite 的 mode classification、Agent 的 final_answer——这些是判断系统行为的核心信号，以 score 形式写入 trace，方便后续过滤和聚合。
4. **Agent tool 调用透传 tool name**：`hybrid_search`、`read_document`、`list_documents` 的每次调用作为 `@observe(as_type="tool")` span，name 为 tool 名称，metadata 中标记 latency、result count。

### 7.2 完整 Trace 层级与 Observation Type

以下展示 Direct mode 和 Agentic mode 的完整 span 树。每个 span 标注了 `(type)`——Langfuse 的 observation type。`[auto]` 标记表示由 `langfuse.openai` 自动捕获，不需要手动埋点。

**Direct Mode**：

```
chat.message (chain)                              # ChatService.send_message
├── tags: [kb_id, session_id, user_id]
├── metadata: {search_mode: "direct"}
│
├── search.rewrite (chain)                        # Route & Rewrite（1 次 LLM）
│   └── [auto] LLM generation                     #   自动捕获的 LLM 调用
│   output: {mode, semantic_query, lexical_queries}
│
├── search.retrieve (retriever)                   # hybrid_retrieve() + merge_results()
│   ├── input: {semantic_query, lexical_queries, top_k}
│   ├── metadata: {fts_config, vector_model}
│   ├── output: {merged_count, both_failed, fts_error, vector_error}
│   │
│   ├── [auto] embedding                          #   semantic_query → vector
│   └── search.retrieve.fts (retriever)           #   多路 FTS（子 span）
│       input: {queries: lexical_queries}
│       output: {hit_count_per_query: [...]}
│
├── search.crag.evaluate (evaluator)              # CRAG 相关性评估
│   └── [auto] LLM generation                     #   自动捕获
│   input: {question, chunk_count, retry_count}
│   output: {grade, reason}
│   score: {relevance_grade: "relevant"}          #   核心信号
│
├── search.crag.correct_query (chain, 条件)        # CRAG 纠正重搜（irrelevant 时）
│   └── [auto] LLM generation
│   output: {corrected_queries}
│   └── search.retrieve (retriever, retry=1)      #   重新检索
│       └── search.crag.evaluate (evaluator, retry=1)
│
└── [auto] LLM generation                         # Answer Generation
    metadata: {input_tokens, output_tokens, model}
```

**Agentic Mode**：

```
chat.message (chain)                              # ChatService.send_message
├── tags: [kb_id, session_id, user_id]
├── metadata: {search_mode: "agentic"}
│
├── search.rewrite (chain)                        # Route & Rewrite（同 Direct）
│   output: {mode: "agentic", semantic_query, lexical_queries}
│
├── agent.run (agent)                             # AgentRunner.run()
│   input: {task, lexical_queries_suggestions}
│   output: {total_rounds, total_tool_calls, final_answer_length}
│   │
│   ├── list_documents (tool)                     #   Round 1
│   │   metadata: {latency_ms, count}
│   │
│   ├── hybrid_search (tool)                      #   Round 2
│   │   metadata: {latency_ms, result_count}
│   │   ├── [auto] embedding
│   │   └── search.retrieve.fts (retriever)       #      FTS 路径
│   │
│   ├── read_document (tool)                      #   Round 3
│   │   metadata: {document_id, offset, latency_ms}
│   │
│   └── hybrid_search (tool)                      #   Round 4（新角度）
│       metadata: {latency_ms, result_count}
│
└── [auto] LLM generation × N                     # Agent 每轮的 LLM 调用（自动）
```

**Type 决定 UI 行为**：`retriever` 类型的 span 在 Langfuse 中会展示检索输入/输出对比；`evaluator` 类型会高亮评分结果；`agent` 类型会展示决策轨迹；`tool` 类型会展示工具调用延迟分布。不在 name 里编码类型信息，靠 `as_type` 让 UI 自动分组。

### 7.3 Observation Type 映射

Langfuse v4 SDK（`>=3.3.1`，项目用 `4.13`）支持 `@observe(as_type="...")` 指定 observation type。默认无 `as_type` 时为 generic `span`。我们给每个 span 显式指定 type，让 Langfuse UI 可以按类型分组、过滤、展示专用面板。

**新增 span 的类型映射**：

| Span Name | `as_type` | 位置 | 说明 |
|-----------|-----------|------|------|
| `chat.message` | `chain` | `chat.py` — `send_message()` / `stream_message()` | 编排多个子步骤的 pipeline（已有，建议加上 `as_type`） |
| `search.rewrite` | `chain` | `rewrite.py` — `route_and_rewrite()` | LLM 调用 + 结构化输出转换 |
| `search.retrieve` | `retriever` | `retriever.py` — `hybrid_retrieve()` | 数据检索（PostgreSQL + pgvector） |
| `search.retrieve.fts` | `retriever` | `retriever.py` — `_fts_search()` | FTS 子检索步骤 |
| `search.crag.evaluate` | `evaluator` | `crag.py` — `evaluate_relevance()` | 评估检索结果相关性 |
| `search.crag.correct_query` | `chain` | `query_rewriter.py` — `correct_query()` | LLM 纠错重写 |
| `search.crag.supplement` | `chain` | `crag.py` — `_generate_supplement_query()` | LLM 定向补充查询 |
| `agent.run` | `agent` | `runner.py` — `AgentRunner.run()` | Agent 决策循环 |
| `agent.run.stream` | `agent` | `runner.py` — `AgentRunner.run_stream()` | Agent 流式决策循环 |
| `hybrid_search` | `tool` | `tools.py` — `_hybrid_search_impl()` | Agent 工具：混合检索 |
| `read_document` | `tool` | `tools.py` — `_read_document_impl()` | Agent 工具：阅读文档 |
| `list_documents` | `tool` | `tools.py` — `_list_documents_impl()` | Agent 工具：列举文档 |

**已有 span 的类型补全**（本次改动中顺手加上）：

| Span Name | `as_type` | 说明 |
|-----------|-----------|------|
| `search.retrieve` | `retriever` | 已在 `service.py` 中，加 `as_type` |
| `agent.run` | `agent` | 已在 `runner.py` 中，加 `as_type` |
| `agent.run.stream` | `agent` | 已在 `runner.py` 中，加 `as_type` |
| `index.pipeline` | `chain` | 已在 `pipeline.py` 中，加 `as_type` |
| `studio.report` | `chain` | 已在 `report.py` 中，加 `as_type` |
| `studio.report.gather` | `agent` | 子 Agent，加 `as_type` |

**Auto-traced（不需要手动埋点，类型自动正确）**：

| 来源 | Type | 说明 |
|------|------|------|
| `langfuse.openai` → LLM calls | `generation` | 所有 `llm.generate()` / `llm.generate_with_tools()` |
| `langfuse.openai` → Embedding calls | `embedding` | 所有 `embedder.embed()` |

**使用方式**：

```python
# 每个 @observe 都带 as_type
@observe(name="search.retrieve", as_type="retriever", capture_input=False, capture_output=False)
def hybrid_retrieve(...) -> RetrievalResult:
    ...

@observe(name="search.crag.evaluate", as_type="evaluator", capture_input=False, capture_output=False)
def evaluate_relevance(...) -> tuple[RelevanceGrade, str]:
    ...

@observe(name="agent.run", as_type="agent", capture_input=False, capture_output=False)
def run(self, task: str, ctx: ToolContext) -> AgentResult:
    ...

@observe(name="hybrid_search", as_type="tool", capture_input=False, capture_output=False)
def _hybrid_search_impl(ctx, ...) -> ToolResult:
    ...
```

### 7.4 关键 Score 定义

Score 写入 trace 后，可在 Langfuse UI 中按 score 值过滤、聚合、设置 CI gate。

| Score Name | 来源 | 类型 | 含义 |
|------------|------|------|------|
| `relevance_grade` | CRAG `evaluate_relevance()` | categorical: `relevant` / `partial` / `irrelevant` | 检索质量的核心信号。聚合 `irrelevant` 占比可发现检索器退化 |
| `mode_classification` | Route & Rewrite | categorical: `direct` / `agentic` | 路由决策准确率。与最终用户满意度关联分析 |
| `crag_action` | CRAG `crag_evaluate_and_act()` | categorical: `answer` / `not_found` / `error` | CRAG 的最终决策。`not_found` 占比反映 KB 覆盖率 |
| `agent.rounds` | `agent.run` span output | numeric | 复杂查询的实际轮数。分布变化反映检索质量变化 |
| `agent.early_stop` | `agent.run` span output | boolean | Agent 是否因早停机制结束。过高说明检索结果信息密度不足 |
| `fts_error` / `vector_error` | `search.retrieve` span output | boolean | 检索路径健康状况 |

Score 写入方式（以 CRAG 为例）：

```python
# services/retrieval/crag.py

@observe(name="search.crag.evaluate", as_type="evaluator", capture_input=False, capture_output=False)
def evaluate_relevance(llm, question, results) -> tuple[RelevanceGrade, str]:
    update_current_span(
        input={"question": question, "chunk_count": len(results)},
    )
    # ... LLM call ...
    update_current_span(
        output={"grade": grade, "reason": reason},
    )
    # 写入 score → 可在 UI 中按数值过滤、聚合
    if _client := _get_langfuse_client():
        _client.create_score(
            trace_id=get_current_trace_id(),
            name="relevance_grade",
            value={"relevant": 1.0, "partial": 0.5, "irrelevant": 0.0}[grade],
            comment=reason,
        )
    return grade, reason
```

### 7.5 Agent Tool 调用的观测

每个 Agent tool 用 `as_type="tool"`，span name 直接用 tool 名称（`hybrid_search`、`read_document`、`list_documents`）。Langfuse 中按 `as_type="tool"` 过滤即可看到所有工具调用的延迟分布和成功率，无需靠 name prefix。

```python
# services/agent/tools.py — 以 _hybrid_search_impl 为例

@observe(name="hybrid_search", as_type="tool", capture_input=False, capture_output=False)
def _hybrid_search_impl(ctx, embedding_query, lexical_queries=None, top_k=5) -> ToolResult:
    t0 = time.perf_counter()
    update_current_span(
        input={"embedding_query": embedding_query, "lexical_queries": lexical_queries},
        metadata={"kb_id": ctx.kb_id},
    )
    # ... 执行检索 ...
    elapsed_ms = (time.perf_counter() - t0) * 1000
    update_current_span(
        output={"result_count": artifact_count, "both_failed": merged.both_failed},
        metadata={"latency_ms": round(elapsed_ms, 2)},
    )
    return tool_result
```

`read_document` 和 `list_documents` 同理，span name 分别用 `"read_document"` 和 `"list_documents"`，`as_type="tool"`。

### 7.6 为什么现在做

| 理由 | 说明 |
|------|------|
| **基建已就绪** | `core/telemetry.py` 完整，`@observe` / `update_current_span` / `trace_context` 全部 no-op safe。加观测 = 加 decorator + 几行 `update_current_span`，不是引入新技术栈 |
| **检索是黑盒中最关键的一段** | 用户问 → 检索引擎 → LLM 回答。检索那一段如果不可观测，回答质量差时你只能猜是 retrieval 的问题还是 generation 的问题 |
| **CRAG 的正确性需要 trace 验证** | CRAG 的 `correct_query` 逻辑靠经验法则（"搜两次找不到就是没有"），没有 trace 你永远不知道这个法则是太保守（本可以搜到的放弃了）还是太激进（搜了三次还是幻觉） |
| **Agent 工具调用需要 profiling** | Agent 的 `max_rounds=4` 是拍脑袋还是数据驱动？`agent.tool_call` span 的轮数分布直接告诉你答案 |
| **成本极低** | 每个 span 加 ~10 行代码。四个 Phase 总计新增埋点不超过 100 行。Langfuse 异步批量发送，不影响请求延迟 |

### 7.7 不做的事

- **不做实时告警**：v0.1.0 阶段 trace 数据量小，人工在 Langfuse UI 中查看即可。告警规则留给 v0.2.0。
- **不做 CI 评测 gate**：检索评测（Recall@K、MRR）是离线跑脚本，不是每次 PR 自动跑的 CI gate。评测体系留在 v0.2.0。
- **不在前端展示 trace**：前端不需要嵌入 Langfuse trace viewer。开发/调试时直接打开 Langfuse UI。

---

## 八、实施计划

### 8.1 四个 Phase

```
Phase 1: CRAG gate（最小改动，立即可用）
  ── 新文件: services/retrieval/crag.py
  ── 新文件: services/retrieval/query_rewriter.py（correct_query utility）
  ── 修改: services/chat.py（在检索和回答之间插入 CRAG，通过 RetrievalService.search 重新检索）
  ── 两种现有策略都受益（CRAG 不感知策略细节，只消费 RetrievalQueryResponse）

Phase 2: Hybrid Retriever 统一
  ── 修改: services/retrieval/retriever.py（multi-query + 统一入口）
  ── 修改: services/retrieval/strategies/hybrid.py（改用升级后的 hybrid_retrieve）
  ── 修改: services/agent/tools.py（新增 hybrid_search tool，search_keywords 保留兼容）
  ── 修改: services/agent/configs.py（SEARCH_AGENT_CONFIG + GATHER_AGENT_CONFIG 加入 hybrid_search，max_rounds=4）

Phase 3: Route & Rewrite + 旧策略下线
  ── 新文件: services/retrieval/rewrite.py（一次 LLM：decontextualize + classify + 生成 lexical_queries）
  ── 修改: services/retrieval/service.py（search_mode 替换 search_strategy）
  ── 修改: services/chat.py（先 Route & Rewrite，再按 mode 分流 direct/agentic）
  ── 修改: schemas/chat.py（ChatRequest 字段更新）
  ── 删除: services/retrieval/strategies/agentic.py（逻辑已迁入 retriever + rewrite）
  ── 删除: services/retrieval/strategies/hybrid.py（逻辑已迁入 retriever）

Phase 4: 清理 + 测试
  ── 删除: agent/tools.py 的 _search_keywords_impl（已被 hybrid_search 替代）
  ── 新增: tests/services/test_crag.py, test_rewrite.py
  ── 更新: tests/services/test_agent_runner.py（hybrid_search 替代 search_keywords）
```

### 8.2 新增/修改文件清单

```
新增:
  services/retrieval/crag.py            # CRAG 相关性评估
  services/retrieval/query_rewriter.py   # correct_query（CRAG utility）
  services/retrieval/rewrite.py          # Route & Rewrite
  tests/services/test_crag.py
  tests/services/test_rewrite.py

修改:
  services/retrieval/retriever.py       # 中文分词 + multi-query + 统一入口
  services/retrieval/strategies/hybrid.py  # 改用升级后的 hybrid_retrieve
  services/retrieval/service.py         # search_mode 替换 search_strategy
  services/agent/tools.py               # 新增 hybrid_search tool
  services/agent/configs.py             # 更新 SEARCH_AGENT_CONFIG + GATHER_AGENT_CONFIG
  services/chat.py                      # Route & Rewrite + CRAG gate + mode 分流
  schemas/chat.py                       # 字段更新

删除（Phase 3-4）:
  services/retrieval/strategies/agentic.py   # 逻辑已迁入 retriever + rewrite
  services/retrieval/strategies/hybrid.py    # 逻辑已迁入 retriever
  services/agent/tools.py _search_keywords_impl  # 被 hybrid_search 替代
```

### 8.3 兼容性

- `ChatRequest.search_strategy` 改为 `search_mode`，前端同步更新
- `RetrievalService.DEFAULT_STRATEGY` 改为 `DEFAULT_MODE`
- SSE 事件格式不变（`agent_progress` 事件仍然表示 agent 步骤，direct mode 不产生此类事件）
- `RetrievalQueryResponse` schema 不变

---

## 附录：LLM 调用次数对比

### 典型简单查询："JWT token 的过期时间是多久"

| 方案 | Route & Rewrite | 检索 | CRAG | Answer | embedding | 总计 |
|------|---------------|------|------|--------|-----------|------|
| 现在 agentic | — | 4-5 LLM | — | 1 | 0 | 5-6 LLM |
| 现在 hybrid | — | 0 | — | 1 | 1 | 1 LLM + 1 emb |
| **Direct mode** | **1** | **0** | **1-2** | **1** | **1** | **3-4 LLM + 1 emb** |

### 典型复杂查询："比较项目中 A 方案和 B 方案的安全设计差异"

| 方案 | Route & Rewrite | Agent loop（含 final_answer） | CRAG | embedding | 总计 |
|------|---------------|-----|------|-----------|------|
| 现在 agentic | — | 4-5 LLM | — | 0 | 5-6 LLM |
| 现在 hybrid | — | — | — | 1 | 1 LLM + 1 emb（结果可能不完整） |
| **Agentic mode** | **1** | **2-4** | **—** | **1-3** | **3-5 LLM + 1-3 emb** |

Agentic mode embedding 次数分析：
- Agent 直接调 `hybrid_search` → **1 emb**（每轮 1 emb，非每轮都调——有 list_documents 和 read_document 轮次）
- Agent 换方向再搜 → 额外 1 次 → **2-3 emb**

Agentic mode 和现在 agentic 比：
1. **LLM 调用少 1-2 次**——Agent 的 final_answer 就是最终答案
2. **无 CRAG**——Agent 自己纠错
3. **Hybrid retriever** 一步覆盖语义变体，轮数 5→2-4
4. **lexical_queries 内联生成**——Agent 调 tool 时顺手填参数，不产生额外调用

### 成本总结

| | 现在（agentic 默认） | 改造后（direct + agentic 自适应） |
|---|---|---|
| 90% 的查询走 direct | — | 3-4 LLM + 1 emb |
| 10% 的查询走 agentic | — | 3-5 LLM + 1-3 emb |
| 当前平均 | 5-6 LLM | ~3.5 LLM + 1.1 emb |
| **LLM 成本降低** | — | **~40%** |
