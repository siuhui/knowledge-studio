# KnowledgeBase — 架构与演进设计

> **本文档是架构设计决策的唯一信源**——负责"为什么这样设计"和"未来怎么演进"。
> 数据模型见 @docs/data-model.md。工程惯例与命令见 @docs/engineering-standards.md。产品需求见 @docs/prd.md。

---

## 目录

1. [现有架构回顾](#一现有架构回顾)
2. [v0.1.0 目标与范围](#二v010-目标与范围)
3. [Agent 运行时设计](#三agent-运行时设计)
4. [检索策略层](#四检索策略层)
5. [Studio 模块：报告生成](#五studio-模块报告生成)
6. [对话 vs 报告](#六对话-vs-报告)
7. [优化路线](#七优化路线)
8. [评测体系](#八评测体系)
9. [v0.2.0 展望](#九v020-展望)
10. [开发计划](#十开发计划)
11. [附录：完整目录结构](#附录完整目录结构)

---

## 一、现有架构回顾

### 1.1 分层结构

```
api/            → 薄层：提取参数，调用 service，包装 ApiResponse[T]
services/       → 业务逻辑：编排 repository，调外部 API
repositories/   → 数据访问：封装 SQLAlchemy 查询
models/         → ORM 映射：纯表定义，无逻辑
core/           → 横切：config, errors, security, logging, trace, telemetry
```

调用方向：`api → service → repository → db`。所有 service 和 repository 类使用静态方法。

### 1.2 数据模型链

```
User ──1:N──> KnowledgeBase ──1:N──> Source ──1:N──> Document ──1:N──> Chunk
                                            │                      │
                                     ChatSession ──1:N──> ChatMessage

Document ──1:1──> DocumentIndexStatus
```

9 张表。`document.text_hash`（SHA-256）用于去重。`chunk.embedding` 为 nullable pgvector Vector。`document_index_status` 是 Document 的 1:1 扩展表，追踪 chunk/embed 生命周期。

> 完整字段定义见 @docs/data-model.md。

### 1.3 入库 pipeline

```
upload → MinIO presigned POST → /complete → background index pipeline:
  Stage 1: parse (PDF/MD/TXT) → Document.full_text + text_hash
  Stage 2: chunk (512 tokens, 50 overlap) → Chunk
  Stage 3: embed (OpenAI API) → Chunk.embedding
```

### 1.4 检索与问答

```
Chat: route_and_rewrite → direct (hybrid + CRAG, 单次检索) / agentic (AgentRunner multi-round, 多轮检索) → build_context → LLM answer (同步 / SSE streaming)
```

### 1.5 当前约束（v0.1.0 完成态）

| 项目 | 状态 |
|------|------|
| 信息来源 | 文件上传（PDF/MD/TXT）+ URL 导入（trafilatura + Playwright 兜底，含 SSRF 防护） |
| 检索策略 | direct（单次 hybrid + CRAG）与 agentic（多轮 agent）两种模式，由 `route_and_rewrite()` LLM 按查询复杂度**逐条自动路由**二选一，无产品层面的默认/可选之分；`ChatRequest.search_mode` 可强制覆盖 |
| Chunk + Embed | 入库必做。两种检索模式都依赖 Chunk 表（agentic 和 direct 共用 `hybrid_retrieve`） |
| 产出物 | 问答 + 研究报告（Studio Report，markdown）。PPT 未做（见 §五） |
| 用户选择 | 后端 `search_mode` 字段可选传入覆盖路由；**前端暂无 StrategySelector UI，从不发送该字段**，实际全走 LLM 自动路由 |

---

## 二、v0.1.0 目标与范围

### 2.1 目标

打通从"文档入库"到"智能回答"到"报告产出"的完整流程。核心新增两个能力：

1. **Agentic search**：用 AgentRunner 做多轮推理检索（hybrid_search + read_document + list_documents），适合需要多步推理的复杂问题
2. **Studio 报告生成**：对知识库文档进行深度分析，产出结构化多章节报告文件

### 2.2 范围边界

```
v0.1.0 完成态
═══════════════════════════════════════════════════════════════════════

  信息来源                检索                        消费
  ───────                ────                        ────
  upload (已有)    ┌─ direct  (单次 hybrid + CRAG)   Chat 问答 (已有)
  URL 导入 (NEW)   └─ agentic (多轮 agent, NEW)      Studio 报告 (NEW, markdown)

  路由: route_and_rewrite() 每次按查询复杂度 LLM 自动二选一（无默认/可选之分）；
        search_mode 可强制覆盖，但前端未接线，实际全走自动路由

  入库 pipeline (已有, 保留)
    parse → chunk → embed
```

### 2.3 关键决策

| 决策 | 理由 |
|------|------|
| **保留现有 chunk+embed pipeline 不变** | agentic 和 direct 共用同一套 Chunk 级检索基础设施（`hybrid_retrieve` + RRF） |
| **direct / agentic 由 LLM 按查询路由，无固定默认** | `route_and_rewrite()` 按复杂度选：简单问题走 direct（单次 hybrid + CRAG），需多步推理走 agentic（多轮 agent）。`search_mode` 可强制覆盖 |
| **两条路径共享检索原语** | agentic 的 `hybrid_search` 工具内部也调 `hybrid_retrieve` + RRF，与 direct 同源 |
| **Studio 先做报告** | 报告是最高频需求，markdown 输出验证整个 workflow；PPT 留到后续 |
| **Agent 运行时独立于检索和 Studio** | 同一个 AgentRunner 被两者复用，`AgentRunner` 本身是业务无关的 |
| **chunk+embed 入库必做** | 两种模式都依赖 Chunk 表，管道始终跑全流程（parse → chunk → embed） |

### 2.4 不入 v0.1.0 的东西

| 项目 | 何时做 | 原因 |
|------|--------|------|
| web_search / media_crawler | v0.2.0 | 信息来源扩展需独立设计调度层 |
| mixed 检索策略 | v0.2.0 | 依赖 agentic + hybrid 先稳定 |
| 并行 tool calls | v0.2.0 | 依赖 LLM provider 的 native parallel tool calling |
| Level 2 回答评测（LLM-as-Judge）| v0.2.0 | 先立检索层组件级指标（Level 1 进 v0.1.0），回答评测紧跟其后 |

---

## 三、Agent 运行时设计

Agent 运行时（Agent Runtime）是本版本的核心新增模块。设计思路：参考了 **smolagents** 的极简 ReAct 循环、**OpenAI Agents SDK** 的 Config/Runner 无状态分离、**Atomic Agents** 的 Schema 驱动组合思想。在保持项目分层纪律的前提下，取三者精华。

### 3.1 设计原则

```
┌─────────────────────────────────────────────────────┐
│  一个底座，两种配置                                   │
│                                                     │
│  AgentRunner (通用 ReAct 循环)                       │
│  ─ 不绑定任何具体工具                                │
│  ─ 不假设任何输出格式                                │
│  ─ 只管: think → act → observe → repeat → stop       │
│                                                     │
│  不同 AgentConfig 注入 → 不同行为                     │
│  SearchAgent: 回答问题 (max 5 轮)                    │
│  GatherAgent: 收集素材 (max 8 轮)                    │
└─────────────────────────────────────────────────────┘
```

AgentRunner 和 AgentConfig 分离。Config 是可序列化的纯数据（可在进程级缓存复用），Runner 是无状态执行器（每个请求独立创建，天然适合并发）。

### 3.2 目录结构

```
services/agent/              # NEW — Agent 运行时
  __init__.py                # 公开: AgentRunner, AgentConfig, Tool, AgentResult
  runner.py                  # AgentRunner: ~120 行 ReAct 循环
  types.py                   # AgentConfig, AgentStep, AgentResult, ToolResult, Tool
  tools.py                   # 内置工具: hybrid_search, read_document, list_documents
  configs.py                 # 预置配置: SEARCH_AGENT_CONFIG, GATHER_AGENT_CONFIG
```

### 3.3 核心类型

```python
# services/agent/types.py

@dataclass
class ToolContext:
    """工具执行的共享上下文。不直接传 db，而是通过 context 携带，
    避免 Tool 接口和数据库强耦合。v0.1.0 仅含 db 和 kb_id，后续自然扩展。"""
    db: Session
    kb_id: str
    user_id: str | None = None

@dataclass
class AgentConfig:
    """Agent 的完整配置。同一个 Runner + 不同 Config = 不同 Agent。"""
    tools: list["Tool"]                       # 可用工具集
    system_prompt: str                        # 告诉 agent 它是谁、要产出什么
    max_rounds: int = 5                       # 硬上限，防止 token 烧穿
    early_stop_patience: int = 2              # 连续 N 轮无新信息则提前终止
    output_schema: type[BaseModel] | None = None  # 结构化输出 schema（Pydantic model）

    def __post_init__(self):
        """构建 tool registry：防重复 name + O(1) 查找。"""
        self._tool_registry: dict[str, "Tool"] = {t.name: t for t in self.tools}
        if len(self._tool_registry) != len(self.tools):
            raise ValueError("Duplicate tool names in AgentConfig")

    def get_tool(self, name: str) -> "Tool":
        return self._tool_registry[name]

class Tool(Protocol):
    """工具协议。任何实现此协议的对象都可用作 agent 工具。"""
    name: str
    description: str                          # 自然语言描述，注入 system prompt
    parameters: dict                          # JSON Schema，注入 function calling
    def execute(self, ctx: ToolContext, **kwargs) -> "ToolResult": ...

@dataclass
class Artifact:
    """一条工具产出的数据。

    在构造时校验 JSON 可序列化，保证下游（SSE、API 响应）不会碰到不可序列化数据。
    工具实现侧如果塞了不可序列化的东西，在这里立刻失败，而不是跑到 SSE 层才炸。
    """
    data: dict[str, object]                   # JSON-serializable dict
    source: str | None = None                 # 数据来源（如 document_id），用于 citation

    def __post_init__(self):
        try:
            json.dumps(self.data)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Artifact data must be JSON-serializable: {e}"
            ) from e

    def to_json(self) -> str:
        return json.dumps(self.data)

@dataclass
class ToolResult:
    """工具执行结果。

    summary:   给 LLM 看的摘要（200-500 字），节省 token。
    artifacts: 完整数据列表，给调用方收集。每个 Artifact 在构造时已校验 JSON 可序列化。
    metadata:  工具执行的运行时指标，用于 trace 和监控。
    """
    summary: str
    artifacts: list[Artifact]                 # 替代 Any，构造时强制 JSON 校验
    artifact_count: int                       # 本工具产出的有效 artifact 数量
    metadata: dict = field(default_factory=dict)
    # metadata 示例: {"latency_ms": 130, "document_ids": [...], "cache_hit": False}

@dataclass
class AgentStep:
    """单步记录 — 支持 SSE 事件流和调试回溯。

    thought 仅供调试和前端展示。Runner 循环逻辑不依赖此字段。
    Provider 无法提供 reasoning 时设为 None，不影响执行。
    """
    thought: str | None
    tool_name: str | None
    tool_args: dict | None
    tool_result: ToolResult | None
    is_final: bool
    new_info_count: int

@dataclass
class AgentUsage:
    """LLM token 消耗统计。每轮调用的用量汇总。"""
    input_tokens: int
    output_tokens: int
    total_tool_calls: int                     # tool 调用次数（不等于轮数）
    latency_ms: float

@dataclass
class AgentResult:
    """Agent 运行的最终产物。"""
    steps: list[AgentStep]                    # 完整推理链路
    collected_artifacts: list[Artifact]         # 所有 tool 的 Artifact 汇总
    final_answer: str | None                  # is_final 时的自然语言输出
    total_rounds: int
    total_tool_calls: int
    usage: AgentUsage | None                  # token 消耗
```

### 3.4 AgentRunner（核心循环）

```python
# services/agent/runner.py

class StepEvent:
    """循环内部事件。_run_impl() 每步 yield 一个事件，消费方自行决定如何处理。"""
    type: str         # "thought" | "tool_call" | "tool_result" | "final" | "error"
    data: dict
    step: AgentStep   # 完整的 step 对象，run() 收集、run_stream() 丢弃

class AgentRunner:
    """通用 ReAct agent 执行引擎。

    无状态。不绑定任何业务。不假设输出格式。
    每次调用 run() / run_stream() 创建新的内部状态，实例本身可复用。
    """

    def __init__(self, llm: LLMProvider, config: AgentConfig):
        self.llm = llm
        self.config = config

    def _run_impl(self, task: str, ctx: ToolContext) -> Generator[StepEvent]:
        """唯一的循环实现。yield StepEvent，不关心消费方是 run() 还是 run_stream()。

        流程:
          1. 构建初始 messages: [config.system_prompt, task]
          2. 循环 (最多 config.max_rounds):
             a. llm.generate_with_tools(messages, config.tools, config.output_schema)
             b. 解析 LLM 返回的 ToolCallDecision:
                - is_final=True  → 记录 → yield final → break
                - is_final=False → 执行 tool → 追加 observe 到 messages
                - error          → yield error → break
             c. ToolResult.summary 追加到 messages（不喂 artifacts 给 LLM）
             d. 检查早停: 连续 early_stop_patience 轮 artifact_count=0 → break
             e. 检查 max_rounds → break
          3. 循环结束
        """
        ...

    def run(self, task: str, ctx: ToolContext) -> AgentResult:
        """同步执行。消费 _run_impl 的全部事件，组装 AgentResult。"""
        steps: list[AgentStep] = []
        collected: list[Artifact] = []
        usage = AgentUsage(input_tokens=0, output_tokens=0, total_tool_calls=0, latency_ms=0)

        for event in self._run_impl(task, ctx):
            steps.append(event.step)
            if event.type == "tool_result":
                collected.extend(event.step.tool_result.artifacts)
                usage.total_tool_calls += 1

        return AgentResult(
            steps=steps,
            collected_artifacts=collected,
            final_answer=steps[-1].tool_result.summary if steps and steps[-1].is_final else None,
            total_rounds=len(steps),
            total_tool_calls=usage.total_tool_calls,
            usage=usage,
        )

    async def run_stream(self, task: str, ctx: ToolContext) -> AsyncIterator[str]:
        """流式执行。yield SSE JSON 字符串。

        事件类型:
          {"type": "thought",      "text": "...", "round": 1}
          {"type": "tool_call",    "tool": "hybrid_search", "args": {...}, "round": 1}
          {"type": "tool_result",  "tool": "hybrid_search", "count": 5, "round": 1}
          {"type": "final",        "answer": "..."}
          {"type": "error",        "message": "..."}
        """
        for event in self._run_impl(task, ctx):
            yield json.dumps(event.data)
```

**循环逻辑（对应 OpenAI SDK 的三态分发）**：

```
每轮 LLM 返回后：
  ┌─ is_final = True  → 结束循环，收集 final_answer
  ├─ is_final = False → 执行 tool，追加 observe，continue
  └─ 异常 / 超限      → 记录 error，break
```

### 3.5 内置工具

三个工具都对 Chunk 表操作，走统一的 `hybrid_retrieve()` + `merge_results()` 管道（FTS + vector + RRF）。Agent 通过 `read_document` 深入阅读 `Document.full_text` 获取完整上下文。

```python
# services/agent/tools.py

hybrid_search = Tool(
    name="hybrid_search",
    description=(
        "Hybrid search (full-text + semantic vector) across all documents in one call. "
        "embedding_query 用于语义相似度搜索，lexical_queries 用于全文关键词匹配。"
        "返回 chunk 级结果，含 start_offset/end_offset 供 read_document 使用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "embedding_query": {
                "type": "string",
                "description": "本轮搜索的自然语言意图描述",
            },
            "lexical_queries": {
                "type": "array", "items": {"type": "string"},
                "description": "1-3 个关键词短语用于全文匹配",
            },
            "document_ids": {
                "type": "array", "items": {"type": "string"},
                "description": "限定文档 ID 列表",
            },
            "top_k": {
                "type": "integer", "default": 5,
                "description": "返回结果数量",
            },
        },
        "required": ["embedding_query"],
    },
    execute=_hybrid_search_impl,
)

read_document = Tool(
    name="read_document",
    description=(
        "按字符偏移量读取文档全文的指定部分。"
        "先用 hybrid_search 或 list_documents 获取文档 UUID，"
        "再用此工具深入阅读完整上下文。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "document_id": {"type": "string"},
            "offset": {"type": "integer", "description": "起始字符位置（0-based）"},
            "length": {"type": "integer", "default": 3000, "description": "读取字符数"},
        },
        "required": ["document_id"],
    },
    execute=_read_document_impl,
)

list_documents = Tool(
    name="list_documents",
    description="列出知识库中所有文档，返回 UUID、标题、格式和大小。每次搜索前先调用此工具了解可用文档。",
    parameters={"type": "object", "properties": {}},
    execute=_list_documents_impl,
)
```

**Tool 实现示例**（`_hybrid_search_impl` 核心流程）：

```python
def _hybrid_search_impl(ctx, embedding_query, lexical_queries=None, document_ids=None, top_k=5) -> ToolResult:
    raw = hybrid_retrieve(ctx.db, semantic_query=embedding_query, lexical_queries=lexical_queries or [embedding_query],
                          knowledge_base_id=ctx.kb_id, embedder=embedder, top_k=top_k, document_ids=document_ids)
    merged = merge_results(raw, top_k=top_k)
    # 构建 Chunk 级 artifacts，含 start_offset/end_offset 供 read_document 定位
    ...
    return ToolResult(summary=summary, artifacts=artifacts, artifact_count=len(artifacts), metadata={...})
```

`hybrid_search` 调用 `services/retrieval/retriever.py` 的统一 `hybrid_retrieve()` + `merge_results()` 管道——两条检索路径（FTS + vector）独立执行，任一失败另一条继续，RRF 自然处理空列表。

**Tool 返回设计原则**：`summary` 字段只给 LLM 看 200-500 字摘要 + 元数据，避免大段文本撑爆 context。`artifacts` 存结构化完整数据（每个 `Artifact` 在构造时校验 JSON 可序列化），由调用方收集用于最终输出。

### 3.6 两种预置配置

```python
# services/agent/configs.py

SEARCH_AGENT_CONFIG = AgentConfig(
    tools=[hybrid_search, read_document, list_documents],
    system_prompt="""\
You are a research assistant searching a knowledge base to answer questions.

IMPORTANT — Document IDs are UUIDs:
  Every document has a UUID like '550e8400-e29b-41d4-a716-446655440000'.
  You can only obtain valid UUIDs from list_documents() or hybrid_search() results.
  Never pass a document title, filename, or any string that is not a UUID
  to read_document() or hybrid_search()'s document_ids parameter.

Workflow:
1. Call list_documents() first to discover available documents and their UUIDs
2. Use hybrid_search() to find relevant passages — note the UUIDs in results
3. Use read_document() with the exact UUID from step 1 or 2 to get full context
4. Cross-validate with additional searches from different angles
5. When you have enough information, give a final answer with citations

Stop when you can fully answer the question, or after searching from 2-3 different angles.
Do NOT stop after the first search — always verify with at least one cross-check.""",
    max_rounds=5,
    early_stop_patience=2,
)

GATHER_AGENT_CONFIG = AgentConfig(
    tools=[hybrid_search, read_document, list_documents],
    system_prompt="""\
You are a research assistant collecting materials for a report chapter.

Your goal is NOT to write the report — it's to gather the most relevant source material.

For each piece of information you find, note:
- Which document it comes from
- Why it's relevant to the chapter topic
- Whether it contradicts or supports other findings

When you have collected comprehensive material covering all aspects of the chapter topic,
output a structured summary of what you found.

The output should be a JSON object:
{
  "chapter_topic": "...",
  "subtopics": [
    {"title": "...", "key_findings": ["...", "..."], "source_doc_ids": ["..."]},
    ...
  ]
}""",
    max_rounds=8,
    early_stop_patience=3,
)
```

**两者共用完全相同的工具集**，差别仅在 system prompt 定义了不同的"终点"——Search 以自然语言回答结束，Gather 以结构化 JSON 素材结束。

### 3.7 LLM Provider 扩展

现有 `LLMProvider.generate()` 返回纯文本，agent 需要 LLM 结构化返回 tool call 决策。扩展 Protocol，保持两个方法分离（不合并为一个 `generate(messages, tools=None, ...)` 参数爆炸的方法）：

```python
# services/llm.py — 新增

class ToolCallDecision(NamedTuple):
    """LLM 的归一化工具调用决策，屏蔽底层 provider 差异。

    thought 仅供调试和前端展示，Runner 循环逻辑只依赖 is_final 做分支判断。
    """
    is_final: bool              # True = 最终答案，False = 需执行工具
    thought: str | None         # Agent 推理过程（调试用，可能为空）
    tool_name: str | None       # is_final=False 时：要调用的工具名
    tool_args: dict | None      # is_final=False 时：工具参数
    content: str | None         # is_final=True 时：最终答案文本


class LLMProvider(Protocol):
    def generate(self, *, system_prompt: str, messages: list[dict[str, str]]) -> str: ...

    def generate_with_tools(
        self, *,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list["Tool"],
        output_schema: type[BaseModel] | None = None,
    ) -> ToolCallDecision:
        """让 LLM 在给定的工具集中选择调用，或输出最终答案。

        各 provider 实现：
        - OpenAI: chat.completions.create(tools=[...], tool_choice="auto")
                  有 output_schema 时用 response_format
        - Anthropic: messages.create(tools=[...])
        返回归一化的 ToolCallDecision，AgentRunner 无需感知 provider 差异。

        设计决策：generate() 和 generate_with_tools() 不合并。
        generate() 是简单问答接口（Chat、Studio Plan/Generate 使用），
        generate_with_tools() 是 agent 模式接口。两者调用方不同，参数不同，
        provider 内部可以共享 client 实例，但 Protocol 层面保持清晰。
        """
        ...
```

### 3.8 复用关系

```
AgentRunner(SEARCH_AGENT_CONFIG)  ──→  RetrievalService._agentic_search()
AgentRunner(GATHER_AGENT_CONFIG)  ──→  ReportWorkflow.gather()

同一个 Runner，同一套 tools，不同 config。
```

**ReportWorkflow 哪个阶段用 Agent、哪个不用：**

| 阶段 | 工具 | 用 Agent 吗 | 原因 |
|------|------|------------|------|
| **Plan** | `llm.generate()` | ❌ | 一次 LLM 调用，规划章节结构，无需工具 |
| **Gather** | `AgentRunner(GATHER_AGENT_CONFIG)` | ✅ | 需要多轮"搜→读→判断→再搜" |
| **Generate** | `llm.generate()` | ❌ | 带上下文素材的单次 LLM 写作，无需工具 |
| **Assemble** | 纯字符串拼接 | ❌ | 无 LLM 调用 |
| **Format** | markdown.py | ❌ | 纯代码 |
| **Store** | MinIO | ❌ | 纯代码 |

---

## 四、检索策略层

两种检索模式在 `RetrievalService.search()` 中通过内联分发（if/elif），不再使用独立的策略类和注册表。两种模式都返回统一的 `RetrievalQueryResponse`。

### 4.1 service.py — 内联分发

```python
# services/retrieval/service.py

class RetrievalService:
    DEFAULT_MODE = "direct"

    @staticmethod
    def search(
        db: Session, *,
        query: str, knowledge_base_id: str, top_k: int = 10,
        document_ids: list[str] | None = None,
        mode: str | None = None,
        lexical_queries: list[str] | None = None,
    ) -> RetrievalQueryResponse:
        mode_name = mode or RetrievalService.DEFAULT_MODE

        if mode_name == "direct":
            return RetrievalService._direct_search(db, query=query, ...)
        elif mode_name == "agentic":
            return RetrievalService._agentic_search(db, query=query, ...)
        else:
            raise ValidationError(
                code=ResponseCode.SEARCH_STRATEGY_UNKNOWN,
                message=f"Unknown search mode: '{mode_name}'. Available: ['direct', 'agentic']",
            )
```

### 4.2 两种模式

#### Direct — `_direct_search()`

单次 hybrid retrieval：调用 `hybrid_retrieve()`（FTS + vector + RRF on Chunk），然后 `rerank()` → `build_citations()` → 返回 `RetrievalQueryResponse`。无需 agent。

> `DEFAULT_MODE = "direct"` 只是 `RetrievalService.search()` 对 `mode=None` 直接调用方的**代码级兜底**，不是产品语义上的"默认模式"。经 Chat 走的请求由 `route_and_rewrite()` 显式传入 mode，从不落到这个兜底；两种模式在产品层是 LLM 按查询复杂度**二选一**，不存在默认/可选之分。

#### Agentic — `_agentic_search()`

多轮 ReAct agent 循环：创建 `AgentRunner(SEARCH_AGENT_CONFIG)`，通过 `hybrid_search`、`read_document`、`list_documents` 三个工具执行多轮搜索推理。从 `AgentResult.collected_artifacts` 构建 `RetrievalQueryResponse`，同时将 `AgentStep` 列表转换为 `agent_steps`（SSE `agent_progress` 事件）供前端展示。

两种模式共享同一 `hybrid_retrieve()` + `merge_results()` 管道（agent 的 `hybrid_search` 工具内部调用它），chunk 级结果统一经过 RRF 融合。

### 4.4 接入 ChatService

```python
# schemas/chat.py — ChatRequest 字段

class ChatRequest(BaseModel):
    knowledge_base_id: str
    session_id: str | None = None
    content: str = Field(min_length=1, max_length=2000)
    reference_document_ids: list[str] | None = None
    search_mode: str | None = None             # "direct" | "agentic" | None（None 时由 LLM 自动路由）
```

```python
# services/chat.py — 流程

class ChatService:
    @staticmethod
    def send_message(db, *, kb_id, user_id, session_id,
                     content, reference_document_ids=None, search_mode=None):
        # ... session resolve (不变) ...

        # 0. Route & Rewrite — 1 LLM call: complexity check + decontextualize
        route_result = route_and_rewrite(llm_provider, content, history=history)
        effective_mode = search_mode if search_mode is not None else route_result.mode.value

        # 1. Retrieve — mode dispatch with CRAG in direct path
        if effective_mode == "agentic":
            retrieval = RetrievalService.search(db, query=..., mode="agentic", ...)
        else:
            retrieval = RetrievalService.search(db, query=..., mode="direct", lexical_queries=..., ...)
            # CRAG gate — evaluate relevance; correct once if needed
            crag_result = crag_evaluate_and_act(db, query=..., retrieval=retrieval, ...)
            ...

        # 2. Build context + messages → LLM generate
        context = _build_context(retrieval)     # ← 不感知策略
        ...
```

**ChatService 和 `_build_context()` 完全不感知策略差异**——它们只消费 `RetrievalQueryResponse`。路由由 `route_and_rewrite()` 自动完成（LLM 判断复杂度），用户可显式传 `search_mode` 覆盖。

---

## 五、Studio 模块：报告生成

### 5.1 设计思路

Studio 是数据消费层，输入是知识库中的一个或多个文档，输出是文件。Report 是第一个产出类型——"基于这些文档，生成一份 XXX 报告"。

核心流程是 5 阶段 pipeline，其中只有 **Gather** 阶段用到 AgentRunner，其余阶段都是普通 LLM 调用或纯代码：

```
Plan ──→ Gather ──→ Generate ──→ Assemble ──→ Store
1次LLM    Agent(N)   LLM(N)      纯代码        MinIO
```

### 5.2 目录结构

```
services/studio/              # 已实现（report only）
  __init__.py
  runner.py                   # execute_studio_task — 后台入口，状态/进度持久化 + MinIO 存储
  service.py                  # StudioTask CRUD
  types.py                    # ReportConfig, ReportResult, OutputFormat
  workflows/
    base.py                   # Workflow Protocol（execute → (s3_key, chapter_count)）
    report.py                 # ReportWorkflow: plan → gather → generate → assemble → store
  generators/
    markdown.py               # Markdown 拼接 + 格式化
# PPT（ppt.py / python-pptx）尚未实现，推迟到后续版本
```

### 5.3 数据模型

```python
# models/studio_task.py

class StudioTask(Base):
    __tablename__ = "studio_task"

    id: str (PK, UUID)
    knowledge_base_id: str (FK, indexed)
    user_id: str (FK)

    task_type: str              # "report" | "ppt" | "analysis" | "summary"
    title: str                  # 产出物标题
    config: dict (JSON)         # 任务特定配置

    # config 示例 (report type):
    # {
    #   "instruction": "基于这些文档，生成一份安全架构评估报告",
    #   "document_ids": ["doc-1", "doc-2"],
    #   "style": "professional",             # casual | professional | academic
    #   "length": "medium",                  # short | medium | long
    #   "sections": ["摘要", "背景", "分析", "结论"]  # 用户自定义章节，或留空让 LLM 规划
    # }

    status: str                 # pending → running → completed → failed
    progress: float             # 0.0 ~ 1.0
    status_message: str | None  # 当前阶段描述，如 "正在规划章节结构..."

    output_format: str          # "markdown" | "html" | "pptx"
    output_s3_key: str | None   # MinIO object key
    output_metadata: dict | None  # { file_size, char_count, chapter_count }

    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

### 5.4 ReportWorkflow 详细流程

```python
# services/studio/workflows/report.py

class ReportWorkflow:
    """报告生成的 5 阶段流程。

    其中 Gather 阶段用 AgentRunner(GATHER_AGENT_CONFIG) 收集素材。
    其他阶段是普通 LLM 调用或纯代码。
    """

    def __init__(self):
        self._gather_agent = AgentRunner(llm_provider, GATHER_AGENT_CONFIG)

    async def execute(self, db: Session, task: StudioTask) -> ReportResult:
        ctx = {"kb_id": task.knowledge_base_id, "doc_ids": task.config.get("document_ids")}

        # 1. Plan — 1 次 LLM：规划章节结构
        chapters = await self._plan(task.config["instruction"], task.config)

        # 2. Gather — N 个 Agent 并行：每章独立收集素材
        materials = await self._gather(db, chapters, ctx)

        # 3. Generate — N 次 LLM 并行：每章独立生成
        content = await self._generate(materials, task.config["style"])

        # 4. Assemble — 纯代码：拼接所有章节
        markdown = self._assemble(content, task.title)

        # 5. Store — 纯代码：写入 MinIO
        s3_key = await self._store(markdown, task, format="markdown")

        return ReportResult(s3_key=s3_key, markdown=markdown, chapters=len(chapters))

    async def _gather(self, db, chapters, ctx):
        """每章用一个 GatherAgent 独立收集素材（章节间可并行）。"""
        tool_ctx = ToolContext(db=db, kb_id=ctx["kb_id"])
        async def gather_one(ch):
            result = self._gather_agent.run(
                task=f"Gather materials for chapter '{ch['title']}': {ch['plan']}",
                ctx=tool_ctx,
            )
            return {**ch, "materials": result.collected_artifacts}

        return await asyncio.gather(*[gather_one(c) for c in chapters])
```

### 5.5 API 设计

```
POST   /api/v1/knowledge-bases/{kb_id}/studio/tasks     # 创建报告任务
GET    /api/v1/studio/tasks/{task_id}                    # 查询状态 + 进度
GET    /api/v1/studio/tasks/{task_id}/download            # 下载产出文件
GET    /api/v1/knowledge-bases/{kb_id}/studio/tasks       # 历史任务列表
DELETE /api/v1/studio/tasks/{task_id}                     # 删除任务及 MinIO 文件
```

**创建任务请求体**：
```json
{
  "task_type": "report",
  "title": "安全架构评估报告",
  "config": {
    "instruction": "基于知识库中的安全相关文档，生成一份全面的安全架构评估",
    "document_ids": ["doc-id-1", "doc-id-2"],
    "style": "professional",
    "length": "medium"
  }
}
```

**查询状态响应体**：
```json
{
  "code": "OK",
  "data": {
    "id": "task-uuid",
    "task_type": "report",
    "title": "安全架构评估报告",
    "status": "running",
    "progress": 0.35,
    "status_message": "正在收集第 2/3 章的素材..."
  }
}
```

**执行方式**：FastAPI BackgroundTasks 异步执行，前端轮询 `GET /tasks/{id}` 获取进度。

---

## 六、对话 vs 报告

两个概念容易混淆，这里明确区分：

### 对比

| | 对话（Chat） | 报告（Report） |
|---|---|---|
| **输入** | 单一问题 + 可选文档范围 | 主题描述 + 文档范围 + 偏好 |
| **过程** | 检索 → 生成答案（1 次 LLM） | 规划 → 多轮检索 → 逐章生成（N 次 LLM，N = 章节数） |
| **编排** | 单 Agent 循环 | 多阶段 pipeline |
| **产物** | ChatMessage（数据库行） | 文件（.md，存在 MinIO，可下载） |
| **交互** | 流式输出，多轮对话 | 创建任务 → 等待 → 下载 |
| **agent 用法** | SearchAgent（回答用户） | GatherAgent（收集每章的素材），其他阶段是普通 LLM 调用 |

### 共享基础设施

```
对话                                   报告
────                                   ────
ChatService                          StudioTaskRunner
  ├─ RetrievalService.search()         ├─ Plan:  llm.generate()
  ├─ llm_provider.generate()           ├─ Gather: AgentRunner(GATHER) ← 同源
  └─ SessionService.add_qa()           ├─ Generate: llm.generate()
                                       ├─ Assemble: markdown.py
                                       └─ Store: MinIO
共享:
  RetrievalService / AgentRunner / LLMProvider / Document.full_text
```

---

## 七、优化路线

### 7.1 Chunk 策略优化

**现状**：固定窗口 512 tokens，50 overlap，纯粹按 token 切分。句子被截断、代码块被拆散。

| 优化 | v0.1.0 | 说明 |
|------|--------|------|
| **段落感知边界** | ✅ | token 切到边界时回退到最近的段落/句子边界 |
| **结构化元素保护** | 📋 Phase 3 | 标题层级（`#` / `##`）、代码块（`` ``` ``）、表格：不跨边界切分 |
| Semantic chunking | v0.2.0 | 用 embedding 判断相邻段落语义相似度 |
| Agentic chunking | v0.2.0 | 用 LLM 按语义单元切分 |
| Adaptive sizing | v0.2.0 | 根据文档类型和标题层级调整 chunk 大小 |

> agentic 和 direct 共用同一套 Chunk 级检索管道。chunk 质量影响所有检索路径 → chunk 优化仍有价值。

### 7.2 Agent 优化

| 优化 | v0.1.0 | 说明 |
|------|--------|------|
| **早停机制** | ✅ | 连续 N 轮无新信息 → 提前终止，`early_stop_patience` |
| **Tool 返回摘要** | ✅ | `ToolResult.summary` 200-500 字，不喂全文给 LLM |
| **搜索 query 重写** | v0.2.0 | Agent 在 hybrid_search 前自扩展关键词 |
| 并行 tool calls | v0.2.0 | LLM 原生支持 parallel function calling 时启用 |
| System prompt 优化 | v0.2.0 | 基于实际使用数据添加 few-shot 示例 |
| Memory | v0.2.0 | Agent 记住读过哪些区域，避免重复读取 |

### 7.3 Studio 优化

| 优化 | v0.1.0 | 说明 |
|------|--------|------|
| **章节并行生成** | ✅ | Gather 和 Generate 阶段各章节并行 |
| 流式预览 | v0.2.0 | SSE 推送已生成的章节内容 |
| 单章重生成 | v0.2.0 | 允许用户指定"第 3 章重新生成" |
| 模板系统 | v0.2.0 | 用户可选报告模板（学术 / 商业 / 技术） |

---

## 八、评测体系

回答"检索质量好不好？回答准不准？"需要分层评测。**Level 1（检索评测）进 v0.1.0**，Level 2（回答评测）留到 v0.2.0。

> Level 1 的落地方案（语料构造、anchor 标注、灌库、判定口径、CLI）见 @docs/retrieval-eval-plan.md，是本节的唯一实现信源。本节只讲顶层设计决策。

### 8.1 Level 1：检索评测（组件级，v0.1.0）

**判定口径：passage 级 offset-overlap，不是文档级。** 一篇文档几千字，真正回答问题的只有一两句；「命中文档任意 chunk 就算命中」测的是相关文档召回率，数字虚高。golden 是字符区间 `(doc_key, start, end)`，一个 retrieved chunk 命中 ⟺ 同文档 AND 区间重叠。

**测试集**：`EvalQuery` dataclass —— 每题标注 `answer_anchors`（逐字判别性短语），seed 时 `full_text.find()` 解析成 golden offset span：

```python
# apps/api/tests/eval/test_set.py
@dataclass(frozen=True)
class EvalQuery:
    id: str
    question: str
    relevant_docs: tuple[str, ...]      # 文档 key，用于 Doc Recall 对比口径
    answer_anchors: tuple[str, ...]     # 逐字短语，seed 时解析成 golden span
    difficulty: str                     # easy | medium | hard
```

**指标**（四个并列上报，k=5 主 / 10 辅）：Answer-Context Recall@k（主，诚实口径）、Doc Recall@k（次，量化文档级高估）、Hit@k、MRR@k。同时报 Answer-Ctx 和 Doc Recall，量化「文档级口径高估了多少」。

**只测 `direct`**。agentic 复用同一套 `hybrid_retrieve` + RRF 检索原语（agent 的 `hybrid_search` 工具内部调它），direct 是这套共享栈的单次直接暴露，跑 direct 就把组件级检索质量测干净了。agentic 多出来的是编排层（多轮、query 改写、read_document），其产物是「答案」而非「排好序的 chunk 列表」，且非确定、出口按 doc 去重——它的收益归 Level 2 回答评测衡量，不套 chunk 级 recall。

**命令**：`python -m tests.eval.retrieval_eval --top-k 10`（检索出 10 条，切片算 @5/@10）

### 8.2 Level 2：回答评测（端到端，v0.2.0）

**方法**：LLM-as-Judge（用更强的模型当裁判）

**指标**：Correctness、Faithfulness（有无幻觉）、Citation Accuracy、Completeness

**命令**：`python -m tests.eval.answer_eval --mode agentic`

### 8.3 目录

```
apps/api/tests/eval/
  __init__.py
  corpus/                  # 英文语料，按主题簇构造，簇内互为 distractor
  test_set.py              # EvalQuery 列表（question → anchors + difficulty）
  seed.py                  # 幂等灌库 + validate_anchors() 标注校验闸
  metrics.py               # 四个指标 + overlap()，纯函数
  retrieval_eval.py        # Level 1 CLI 主入口
  answer_eval.py           # Level 2: LLM-as-Judge（v0.2.0）
  results/                 # 带时间戳 JSON，版本对比
  test_metrics.py          # 纯函数单测，进 CI
```

### 8.4 执行频率

```
pytest tests/unit                   # CI 阶段 1：纯单元，无需 Postgres，秒级
pytest tests/integration            # CI 阶段 2：API + tool 执行，需 pgvector service
python -m tests.eval.*_eval         # 手动跑 / 大改动后跑（依赖实时 Postgres + embedding API，不进 CI）
results/ 目录存版本对比             # 追踪退化
```

> `tests/eval/`（含 `test_metrics.py`）是手动评测工具，整体不进 CI——它测的是评测指标自身，不是被测系统。

---

## 九、v0.2.0 展望

v0.1.0 打通基本流程后，v0.2.0 做以下扩展：

| 模块 | 内容 |
|------|------|
| **信息来源** | Web Search + Git 仓库同步 |
| **检索策略** | `mixed`（agent 缩范围 + hybrid 精确搜）+ query 重写 |
| **Agent** | 并行 tool calls、Memory、System prompt 持续优化 |
| **Studio** | 数据分析、思维导图、流式预览、单章重生成 |
| **评测** | CI 集成评测、Leaderboard |

---

## 十、开发计划

```
Phase 1: Agent 运行时 ✅ 已完成
  ── services/agent/ (runner.py, types.py, tools.py, configs.py)
  ── LLMProvider 扩展 generate_with_tools()
  ── 单元测试: runner 循环 / tool 执行 / 早停 (27 tests, 12/12 pass without DB)

Phase 2: 检索策略层 ✅ 已完成
  ── RetrievalService.search() 内联分发 direct/agentic，DEFAULT_MODE="direct"
  ── ChatRequest 加 search_mode，ChatService 透传（None 时 route_and_rewrite 自动路由）
  ── SSE 事件扩展（agent_progress: listing/searching/reading/analyzing/error）
  ── 前端 SSE 客户端（parseSSEStream callback + 工作区 agent 步骤展示）

Phase 3: v0.1.0 剩余 ✅ 已完成
  ── URL 导入（Source type=url，trafilatura 抓取 + Playwright JS 兜底 + SSRF 防护 → parse → index）
  ── StudioTask 模型 + repository + schema
  ── services/studio/ (runner.py, service.py, types.py, workflows/report.py, generators/markdown.py)
  ── Chunk: 结构化元素保护（代码块 offset 回映射、标题层级路径、递归分隔符链）
  ── BackgroundTasks 执行 + 前端轮询进度
  ── Studio API (create / status / download / list / delete)
  ── Level 1 检索评测: apps/api/tests/eval/ (corpus 28 篇, test_set, seed, metrics, retrieval_eval)
       方案见 @docs/retrieval-eval-plan.md
  前端: StudioPanel + CreateReportModal + ReportViewerModal（agent 步骤内联在工作区页面）

Phase 3 未做（改期或废弃）:
  ── ❌ PPT 生成（python-pptx）—— 改期 v0.2.0
  ── ❌ StrategySelector 前端组件 —— 废弃：改为 LLM 自动路由，search_mode 保留为可选 override，前端暂不暴露 UI
  ── ⊘ chunk+embed 按需触发 —— 废弃：入库始终跑全流程（决策改为「chunk+embed 入库必做」，见 §2.3）

Phase 4: v0.2.0
  ── Web Search
  ── Git 仓库同步
  ── PPT 生成（python-pptx）
  ── Level 2 回答评测: answer_eval.py (LLM-as-Judge)
  ── 评测结果汇总脚本 + CI 集成
  ── StrategySelector 前端 UI（若需手动切换检索模式）
```

每个 Phase 独立上线、不破坏现有功能。

---

## 附录：v0.1.0 新增/修改文件清单

> 当前完整目录结构见 @docs/engineering-standards.md。

### ✅ 已实现（Phase 1 + 2 + 3）

```
Phase 1 + 2 — Agent 运行时 + 检索策略层:
  services/agent/               # runner.py, types.py, tools.py, configs.py
  core/telemetry.py             # Langfuse tracing
  services/llm.py               # generate_with_tools, generate_stream, ToolCallDecision
  services/chat.py              # stream_message, search_mode 透传
  services/retrieval/           # service.py 内联分发 DEFAULT_MODE="direct"；
                                # retriever.py, crag.py, query_rewriter.py, rewrite.py
  schemas/chat.py               # search_mode 字段
  api/chat.py                   # SSE streaming 端点
  config.py, main.py            # EmbeddingConfig, TelemetryConfig, router 注册

Phase 3 — URL 导入 + Studio + 结构化分块 + 评测:
  services/ingestion/           # parser.py (PDF/MD/TXT), extractors.py (URL: trafilatura + Playwright), service.py
  services/indexing/pipeline.py # 结构化分块（代码块保护 + 标题层级 + 递归分隔）+ chunk/embed
  services/studio/              # runner.py, service.py, types.py, workflows/report.py, generators/markdown.py
  models/studio_task.py, repositories/studio_task.py, schemas/studio.py, api/studio.py
  models/source.py              # type 枚举含 url
  services/source.py            # URL 导入：validate_url (SSRF) → 抓取 → parse → index
  apps/api/tests/eval/          # Level 1: corpus (28 篇), test_set, seed, metrics, retrieval_eval
  tests/integration/api/test_studio.py, tests/unit/services/test_chunking.py, test_crag.py, test_rewrite.py, test_parser_markdown.py
  前端: components/knowledge-bases/StudioPanel.tsx, CreateReportModal.tsx, ReportViewerModal.tsx
```

### ⏳ 待实现（Phase 4 / v0.2.0）

```
  services/studio/workflows/ppt.py   # PPT 生成（python-pptx）
  apps/api/tests/eval/answer_eval.py # Level 2 回答评测（LLM-as-Judge）
  Web Search / Git 仓库同步
  components/knowledge-bases/StrategySelector.tsx  # 手动切换检索模式的前端 UI（当前为 LLM 自动路由）
  .github/workflows/                 # CI 集成（lint + typecheck + test，已添加）
  components/studio/StudioPanel.tsx, TaskCard.tsx, TaskProgress.tsx
  hooks/useStudioTask.ts
```
