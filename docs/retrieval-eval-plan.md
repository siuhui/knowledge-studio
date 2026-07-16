# 检索评测方案 — Recall@5 基线

> 本文档定义 v0.1.0 检索质量评测的**实现方案**：语料构造、ground truth 标注、指标定义、灌库流程、执行方式。
> 目标：产出一个可信、可复现、可版本对比的检索质量基线数字。
> **评测对象只有 `direct`**——它是共享检索栈（`hybrid_retrieve` + RRF + chunk 切分）的直接单次暴露；agentic 只是在同一套检索原语上加了多轮编排，编排收益归 Level 2 回答评测衡量（见决策 3）。
> 评测体系的顶层设计见 @docs/architecture.md §八。

---

## 一、目标与非目标

### 目标

- 产出一张 `direct` 模式的检索质量基线表：Answer-Context Recall@5 / Doc Recall@5 / Hit@5 / MRR@10。
- 判定口径用 passage 级 offset-overlap，不是「相关文档召回」这种虚高口径。
- 幂等灌库、结果带时间戳落盘，任何检索改动都能 rerun 抓退化。

### 非目标（不进本轮）

- Level 2 回答评测（LLM-as-Judge）——先把检索层的组件级指标立起来。
- 中文语料评测——`simple` FTS 分词对中文基本失效，会让 recall 全压在向量路径上，失去 hybrid 的意义。中文 FTS 弱点单列为后续待评测项，不混进基线。
- CI 集成——评测脚本慢且依赖实时 Postgres + embedding API，走 `python -m` 手动跑；只有纯函数单测进 CI。

---

## 二、核心设计决策

### 决策 1：Ground truth 用 offset-overlap（passage 级），不是文档级

**为什么不用文档级**：一篇文档几千字，真正回答问题的只有一两句。若「命中该文档任意 chunk 就算命中」，测的是*相关文档召回率*，检索把整篇文档里不相关段落捞上来也算赢，数字虚高。

**判定核心**：golden 是一段字符区间 `(doc_key, start, end)`；一个 retrieved chunk 命中 ⟺ **同文档 AND 区间重叠**。相关 chunk 和 golden 区间有重合才算命中，只要检索命中的 chunk 落在能回答问题的那段字符范围内。

```python
def overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and a_end > b_start
```

### 决策 2：golden 用 anchor 短语标注，seed 时解析成 offset

不手写裸整数 `(start, end)`——语料改一个字，所有 offset 全偏移，无法维护。改为：

- **标注侧**（人写）：一段逐字出现、能回答问题的判别性短语（anchor，6–12 词）。
- **seed 侧**（机器）：`full_text.find(anchor)` 解析成 `(doc_key, pos, pos+len(anchor))`，并校验唯一性。

兼得 anchor 的编辑鲁棒性 + offset 的精确判定。

### 决策 3：只测 direct，不测 agentic

Level 1 是**组件级**检索质量指标，测的是共享检索原语——`hybrid_retrieve()`（FTS + vector + RRF）加上 chunk 切分。agentic 的 `hybrid_search` 工具内部调的就是同一个 `hybrid_retrieve()`，direct 是这个原语的单次直接暴露。**跑 direct 就已经把两种模式共享的检索栈测干净了。**

agentic 多出来的是编排层（多轮循环、query 改写、read_document、交叉验证），它有三个特性让它不适合 Level 1 的 chunk 级 recall：

1. **产物是答案不是排好序的 chunk 列表**——agentic 的价值在最终回答，chunk 级 recall 套不上。
2. **非确定**——每轮 query 由 LLM 决定，recall 跑一次一个数，无法作为可复现基线。
3. **出口按 `doc_id` 去重**（`_agentic_search` 用 `seen_ids`，每文档最多留 1 chunk），与 direct 的 chunk 粒度口径不对称，强行对比不公平。

因此 agentic 的收益归 **Level 2 回答评测**（LLM-as-Judge，v0.2.0）衡量，在那里它的多轮推理优势才有意义。Level 1 只出 direct 一个诚实、可复现、可版本对比的基线。

评测读 `RetrievalChunk.citation.start_offset/end_offset`——direct 的 `build_citations()` 从 `Chunk.start_offset/end_offset` 填入权威值。

> ⚠️ 注意：`RetrievalChunk.citation` 是 chunk 级 1:1（保留粒度），**不能**用下游 `chat.py::_build_citations()` 的文档级去重结果——那个会把同文档多 chunk 塌成一条，丢失 chunk 粒度，正是决策 1 要避免的高估。

### 决策 4：语料英文 + 按簇构造 distractor

- **英文**：让 FTS 路径（`simple` 分词按空白/标点）和向量路径都真实参与，hybrid 才有意义。
- **按簇**：主题正交的语料会让 embedding 一击必中、recall 恒等于 1，无区分度。改为 7 个主题簇、每簇约 4 篇**近邻文档**（词汇/主题重叠但答案不同），簇内互为语义 distractor，Recall 才成为有区分度的数字。

---

## 三、语料库设计（~28 篇，7 簇）

英文技术短文，每篇约 800–1500 词（保证多 chunk）。簇内文档互为 distractor。

| 簇 | 文档（互为 distractor）|
|----|------|
| 向量检索 | pgvector / FAISS / Milvus / HNSW 算法 |
| 注意力机制 | transformer self-attention / flash attention / cross-attention / multi-head |
| 排序与融合 | BM25 / TF-IDF / RRF / cross-encoder rerank |
| 容器编排 | Docker / Kubernetes / docker-compose |
| Python 并发 | asyncio / threading / multiprocessing |
| 认证 | JWT / OAuth2 / session cookie |
| Postgres | B-tree 索引 / GIN 索引 / 查询计划器 |

---

## 四、测试集设计（~30 问题）

```python
# tests/eval/test_set.py

@dataclass(frozen=True)
class EvalQuery:
    id: str
    question: str
    relevant_docs: tuple[str, ...]      # 文档 key（文件名），用于 Doc Recall 对比口径
    answer_anchors: tuple[str, ...]     # 逐字短语，seed 时解析成 golden offset span
    difficulty: str                     # easy | medium | hard

TEST_QUERIES: list[EvalQuery] = [...]
```

难度分层（对齐簇结构）：

| 难度 | 定义 | 主要考验 |
|------|------|---------|
| easy | 簇间区分，关键词直命 | FTS 路径 |
| medium | 簇内语义改写，需区分 distractor | 向量路径 + 融合 |
| hard | 答案跨 2 篇文档 / 语义间接 | 向量召回 + 多路 FTS 覆盖 |

---

## 五、指标定义（四个并列上报）

| 指标 | 定义 | 作用 |
|------|------|------|
| **Answer-Context Recall@k**（主）| top-k chunk 覆盖的 golden anchor 数 / 总 anchor 数 | 诚实口径 |
| **Doc Recall@k**（次）| top-k 覆盖的相关文档数 / 总相关文档数 | 对比主指标，量化「文档级高估」的差距 |
| **Hit@k**（success rate）| ≥1 个 anchor 被命中的问题占比 | 最直观「答案进没进上下文」|
| **MRR@k** | 首个命中 anchor 的 chunk 排名倒数 | 命中位置质量 |

> 同时报 Answer-Ctx Recall 和 Doc Recall，是为了量化「文档级口径高估了多少」——两个数字并排，高估的差距一目了然。

`k` 取 5（主）和 10（辅）。

---

## 六、目录结构

```
apps/api/tests/eval/
  __init__.py
  corpus/                    # 28 篇英文短文，7 簇，簇内互为 distractor
    01_pgvector.md
    02_faiss.md
    ...
  test_set.py                # EvalQuery 列表：question → relevant_docs + answer_anchors + difficulty
  seed.py                    # 幂等灌库 + validate_anchors() 标注校验闸
  metrics.py                 # answer_ctx_recall / doc_recall / hit_at_k / mrr_at_k（纯函数）
  retrieval_eval.py          # CLI 主入口
  results/                   # 带时间戳 JSON，版本对比
    .gitkeep
  test_metrics.py            # 纯函数快速单测，进 CI
  README.md                  # 指标定义 + 判定口径 + 已知误差 + 跑法
```

---

## 七、各模块职责

### `metrics.py` — 纯函数，零依赖

```python
def answer_ctx_recall_at_k(hit_spans: list[tuple[int, int]], golden_spans: list[tuple[int, int]], k: int) -> float
def doc_recall_at_k(retrieved_doc_keys: list[str], relevant: set[str], k: int) -> float
def hit_at_k(...) -> float
def mrr_at_k(...) -> float
```

输入是已解析好的 span / doc key 列表，判定核心是 §二 的 `overlap()`。可单测，进 CI。

### `seed.py` — 幂等灌库 + 标注校验

- 建固定命名的 eval 用户 + KB（`【EVAL】retrieval-baseline`）+ 一个 eval Source（`type="upload"`，直接 `active`）。`DocumentService.create()` 的 `source_id` 必填（见 `services/document.py`），语料不走真实 upload/URL 管线，需先建这个占位 Source 供所有 eval 文档挂靠。
- 每篇语料：`DocumentService.create(source_id=eval_source_id, ...)`（text_hash 去重天然幂等）→ `chunk_document()`（有 chunk 则跳过）→ `embed_document()`（已 embed 则跳过）。
- 灌进**持久化 DB**（默认 dev DB，非回滚型测试 fixture——embed 有成本，要跨运行复用）。
- **`validate_anchors()`**：断言每个 anchor 在其目标文档 `full_text` 中出现，且**不在其他文档出现**（出现即标注歧义 → 报错让人改标注）。这道闸挡住烂 anchor。
- 返回 `kb_id` + `{doc_key: document_id}` 映射（评测侧用它把 `citation.document_id` 反查回 doc_key）+ `{query_id: [golden_span]}`。
- `--reset` 标志：删旧 eval KB 重建。

### `retrieval_eval.py` — CLI 主入口

```bash
python -m tests.eval.retrieval_eval --top-k 10
```

> Level 1 只测 `direct`（`RetrievalService.DEFAULT_MODE`）。agentic 复用同一套 `hybrid_retrieve` + RRF 检索原语，direct 已把这个共享栈测干净；agentic 多出来的是编排层（多轮、query 改写、read_document），其价值是「答案质量」而非「chunk 排序」，留给 Level 2 回答评测。`--top-k` 是检索深度，固定取 **10**（覆盖 MRR@10），@5 / @10 都从这 10 条里切片算。

流程：

1. `seed.py` 幂等灌库，拿到 doc_key 映射 + golden spans。
2. 逐题 `RetrievalService.search(top_k=10)`（direct）。
3. 每个 `RetrievalChunk`：`citation.document_id` → 反查 doc_key；`citation.start_offset/end_offset` → chunk span。
4. 对每题：chunk spans vs golden spans 跑 `overlap()`，算四个指标。
5. 聚合（总均值 + 按难度分组）→ 写 `results/{ts}.json` + 终端打印指标表。

**输出 JSON**：

```json
{
  "timestamp": "...", "top_k": 10,
  "corpus_size": 28, "query_count": 30,
  "aggregate": {
    "answer_ctx_recall@5": 0.0, "answer_ctx_recall@10": 0.0,
    "doc_recall@5": 0.0, "doc_recall@10": 0.0,
    "hit@5": 0.0, "hit@10": 0.0, "mrr@10": 0.0
  },
  "by_difficulty": {"easy": {...}, "medium": {...}, "hard": {...}},
  "per_query": [{"id": "...", "retrieved": [...], "golden": [...], "hit": true}, ...]
}
```

`per_query` 存 retrieved vs golden，方便定位哪些题挂了。

### `test_metrics.py` — 纯函数单测

硬编码 span/doc 列表，无 DB/API，验证四个指标 + `overlap()` 的正确性。进 CI。

---

## 八、执行前置条件

- Postgres + pgvector 运行中（`knowledge_studio` dev DB 或指定 DB）。
- embedding API key（一次性 embed 成本，之后幂等复用）。
- 评测脚本**不进** `pytest` 默认集；只有 `test_metrics.py` 进 CI。

### 已知误差（写进 README）

- anchor 极小概率跨 chunk 边界被切断 → 该 anchor 记为 miss。chunker 按句子边界切、overlap 只挪 offset 不复制内容，sub-sentence 锚点几乎不会被切断，误差可忽略。

---

## 九、交付顺序

1. `metrics.py` + `test_metrics.py`——四个指标 + `overlap()` 纯逻辑，先立正确性。
2. `corpus/` 28 篇 + `test_set.py`——标注 anchor。
3. `seed.py` + `validate_anchors()`——灌库并校验标注（这步会逼出烂 anchor）。
4. `retrieval_eval.py`——串联。
5. 跑 `retrieval_eval.py`，产出 `results/` 首个基线，README 记录数字。

---

## 十、预期产出

一张 direct 模式的检索质量基线表：

| 指标 | @5 | @10 |
|------|------|------|
| Answer-Ctx Recall（主，诚实口径）| 0.xx | 0.xx |
| Doc Recall（次，暴露文档级高估）| 0.xx（更高）| 0.xx |
| Hit | 0.xx | 0.xx |
| MRR | — | 0.xx |

以及 `results/` 里带时间戳的 JSON，后续任何检索改动都能 rerun 对比、抓退化。

---

## 附录：前置修复（已完成）

评测依赖「`direct` 模式的 `RetrievalChunk.citation` 带真实 chunk 级 offset」。本方案落地前已修复检索出口的字段漂移：

- `Chunk` 模型加了 `start_offset/end_offset` 后未同步到检索出口。
- `build_citations()` 从 `Chunk.start_offset/end_offset` 填入权威值。
- `RetrievalChunk` 不重复存 offset，评测统一读 `citation.start_offset/end_offset`。
