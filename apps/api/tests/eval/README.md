# 检索评测 — Level 1 (Recall@5 基线)

`direct` 模式的检索质量基线。判定口径是 **passage 级 offset-overlap**，不是「相关文档召回」。
方案的唯一实现信源见 [docs/retrieval-eval-plan.md](../../../../docs/retrieval-eval-plan.md)；顶层设计见 [docs/architecture.md](../../../../docs/architecture.md) §八。

---

## 快速开始

```bash
cd apps/api
source .venv/Scripts/activate

# 前置：Postgres + pgvector 运行中，embedding API key 已配
python -m tests.eval.seed --reset          # 灌库（首次或语料改动后）
python -m tests.eval.retrieval_eval --top-k 10
```

结果落到 `results/{timestamp}.json`，终端同时打印指标表。

只跑纯函数单测（进 CI，无需 DB / API）：

```bash
pytest tests/eval/test_metrics.py
```

---

## 配置来源（重要）

评测代码放在 `tests/` 下，但**用哪套配置由入口决定，不由目录决定**。有两条互不相干的入口：

| 入口 | 配置来源 | 打到哪个库 |
|------|---------|-----------|
| `python -m tests.eval.retrieval_eval` / `seed`（手动跑评测） | `app.config.settings` → `.env` / `.env.local` | **dev 库**（持久化，向量跨运行复用） |
| `pytest`（CI 跑 `test_metrics.py`） | `conftest.py` → `.env.test` override | 测试库——但纯函数单测不碰 DB / API，配置无所谓 |

原因：`.env.test` 只在 `tests/conftest.py` 里 `load_dotenv`，而 conftest 是 pytest 专属文件。`python -m` 直接执行模块，不经过 pytest，conftest 不加载，`.env.test` 不生效，于是评测走 dev 配置。

**坑：别用 `pytest tests/eval/retrieval_eval.py` 跑评测。** 那样 conftest 会把配置切成测试库，而测试库 fixture 每个 test 回滚——即使跑了 seed，embed 出来的向量也会当场丢，白烧 embedding API。评测灌库必须用 `python -m`，把语料留在持久化的 dev 库里，seed 幂等，之后 rerun 几乎零成本。

> dev 库 URL 默认是 docker-compose 内部主机名（`db:5432`）。在本机直接跑需覆盖为 `localhost`：
> `KS_DATABASE__URL=postgresql://postgres:postgres@localhost:5432/knowledge_studio python -m tests.eval.retrieval_eval --top-k 10`

---

## 判定口径

一篇文档几千字，真正回答问题的只有一两句。若「命中该文档任意 chunk 就算命中」，测的是*相关文档召回率*——检索把整篇文档里不相关段落捞上来也算赢，数字虚高。

所以 golden 是一段**字符区间** `(doc_key, start, end)`，判定核心：

```
一个 retrieved chunk 命中某 golden anchor  ⟺  同文档 AND 字符区间重叠
```

区间是 0-based 半开（`full_text[start:end]`）。相接不算重叠（`a_end == b_start` → False），与 chunker 的 `start_offset/end_offset` 半开约定一致。

### golden 从哪来

不手写裸整数 offset（语料改一个字全偏移，无法维护）。改为两层：

1. **标注侧**（人写，在 `test_set.py`）：`answer_anchors` —— 逐字出现、能回答问题的判别性短语（6–12 词）。
2. **seed 侧**（机器，`seed.py::validate_anchors`）：`full_text.find(anchor)` 解析成 `(doc_key, pos, pos+len)`。

`validate_anchors()` 是标注闸，任一 anchor 满足下列条件即报错（一次列全）：missing（任何文档都找不到）/ ambiguous（多篇文档都有）/ repeated（同篇出现多次）/ mislabeled（解析到的文档不在 `relevant_docs`）。烂 anchor 在灌库前就被挡下，不会静默按错误 span 打分。

---

## 四个指标（并列上报）

| 指标 | 定义 | 作用 |
|------|------|------|
| **Answer-Context Recall@k**（主）| top-k chunk 覆盖的 golden anchor 数 / 总 anchor 数 | 诚实口径 |
| **Doc Recall@k**（次）| top-k 覆盖的相关文档数 / 总相关文档数 | 对比主指标，量化「文档级高估」 |
| **Hit@k** | ≥1 个 anchor 被命中的问题占比 | 最直观「答案进没进上下文」|
| **MRR@k** | 首个命中 anchor 的 chunk 排名倒数 | 命中位置质量 |

`k` 取 5（主）和 10（辅），都从一次 `top_k=10` 检索里切片算。同时报 Answer-Ctx Recall 和 Doc Recall，是为了让「文档级口径高估了多少」一目了然。

---

## 只测 direct，不测 agentic（决策 3）

Level 1 是**组件级**检索质量指标，测的是共享检索原语——`hybrid_retrieve()`（FTS + vector + RRF）加 chunk 切分。agentic 的 `hybrid_search` 工具内部调的就是同一个 `hybrid_retrieve()`，direct 是这个原语的单次直接暴露，**跑 direct 就把共享栈测干净了**。

agentic 多出来的是编排层（多轮循环、query 改写、read_document）：产物是答案不是排好序的 chunk 列表；每轮 query 由 LLM 决定，非确定、无法作可复现基线；出口按 `doc_id` 去重，与 direct 的 chunk 粒度口径不对称。它的收益归 **Level 2 回答评测**（LLM-as-Judge, v0.2.0）。

评测读 `RetrievalChunk.citation.start_offset/end_offset`——direct 的 `build_citations()` 从 `Chunk.start_offset/end_offset` 填入权威值，保留 chunk 级 1:1 粒度（**不是** `chat.py::_build_citations()` 的文档级去重结果，那个会把同文档多 chunk 塌成一条，正是要避免的高估）。

---

## 语料（~28 篇，7 簇）

英文技术短文，每篇 800–1500 词（保证多 chunk）。簇内文档**互为 distractor**（词汇/主题重叠但答案不同），Recall 才有区分度——主题正交的语料会让 embedding 一击必中、recall 恒等于 1。

| 簇 | 文档 |
|----|------|
| 向量检索 | pgvector / FAISS / Milvus / HNSW |
| 注意力机制 | self-attention / flash attention / cross-attention / multi-head |
| 排序与融合 | BM25 / TF-IDF / RRF / cross-encoder rerank |
| 容器编排 | Docker / Kubernetes / docker-compose / 容器网络 |
| Python 并发 | asyncio / threading / multiprocessing / GIL |
| 认证 | JWT / OAuth2 / session cookie / API key |
| Postgres | B-tree / GIN / 查询计划器 / VACUUM |

**英文**：让 FTS 路径（`simple` 分词按空白/标点）和向量路径都真实参与，hybrid 才有意义。中文语料评测不进本轮（`simple` 对中文分词失效，recall 全压向量路径，失去 hybrid 意义）。

难度分层：`easy`（簇间区分，关键词直命，考 FTS）/ `medium`（簇内语义改写，需区分 distractor，考向量 + 融合）/ `hard`（答案跨 2 篇 / 语义间接，考向量召回 + 多路 FTS 覆盖）。

---

## 已知误差

- **anchor 跨 chunk 边界被切断** → 该 anchor 记为 miss。chunker 按句子边界切、overlap 只挪 offset 不复制内容，sub-sentence 锚点几乎不会被切断，误差可忽略。
- **持久化 DB，非回滚 fixture**：灌进 dev DB（embedding 有成本，跨运行复用）。`--reset` 删旧 eval KB 重建。

---

## 目录

```
tests/eval/
  corpus/            28 篇英文短文，7 簇，簇内互为 distractor
  test_set.py        EvalQuery 列表：question → relevant_docs + answer_anchors + difficulty
  seed.py            幂等灌库 + validate_anchors() 标注闸
  metrics.py         answer_ctx_recall / doc_recall / hit_at_k / mrr_at_k + overlap（纯函数）
  retrieval_eval.py  CLI 主入口（direct 模式）
  test_metrics.py    纯函数单测，进 CI
  results/           带时间戳 JSON，版本对比
```

**执行频率**：`test_metrics.py` 进 CI 每次跑；`seed.py` / `retrieval_eval.py` 依赖实时 Postgres + embedding API，手动跑（大改动后），结果落 `results/` 追踪退化。
