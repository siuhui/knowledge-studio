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
Chat: agentic_search (LLM + PostgreSQL FTS, 默认) 或 hybrid_search (vector + keyword + RRF) → build_context → LLM answer (同步 / SSE streaming)
```

### 1.5 当前约束（v0.1.0 Phase 2 完成后）

| 项目 | 状态 |
|------|------|
| 信息来源 | 文件上传（PDF/MD/TXT）+ URL 导入 |
| 检索策略 | agentic 为默认（零 embedding）；hybrid 可选。`ChatRequest.search_strategy` 已接入 |
| Chunk + Embed | 入库必做（待改为按需触发，当前 hybrid 依赖 chunk，agentic 不依赖） |
| 产出物 | 问答 + 研究报告 + PPT |
| 用户选择 | 前端待加策略切换 UI（`search_strategy` 字段已就绪，API 层支持） |

---

## 二、v0.1.0 目标与范围

### 2.1 目标

打通从"文档入库"到"智能回答"到"报告产出"的完整流程。核心新增两个能力：

1. **Agentic search**：用 LLM + keyword FTS 做多轮推理检索，替代 hybrid 成为默认策略，零 embedding 成本
2. **Studio 报告生成**：对知识库文档进行深度分析，产出结构化多章节报告文件

### 2.2 范围边界

```
v0.1.0 完成态
═══════════════════════════════════════════════════════════════════════

  信息来源                检索                        消费
  ───────                ────                        ────
  upload (已有)    ┌─ agentic (NEW, 默认)      Chat 问答 (已有)
  URL 导入 (NEW)   └─ hybrid  (已有, 可选)     Studio 报告 (NEW)

  入库 pipeline (已有, 保留)
    parse → chunk → embed
```

### 2.3 关键决策

| 决策 | 理由 |
|------|------|
| **保留现有 chunk+embed pipeline 不变** | agentic 不依赖 chunk/embed，两条线独立演进；本版本加按需触发入口，拆 pipeline 留给 v0.2.0 |
| **agentic 做默认策略** | 零 embedding 调用 |
| **hybrid 保留为可选** | 对已有 embed 的文档提供高精度语义搜索 |
| **Studio 先做报告，再做 PPT** | 报告是最高频需求，markdown 输出验证整个 workflow，PPT 紧跟其后 |
| **Agent 运行时独立于检索和 Studio** | 同一个 AgentRunner 被两者复用，`AgentRunner` 本身是业务无关的 |
| **chunk+embed 可按需触发** | 入库只做 parse，用户选择用 hybrid 时才跑 chunk+embed（Phase 3 待实现，当前入库仍跑全 pipeline） |

### 2.4 不入 v0.1.0 的东西

| 项目 | 何时做 | 原因 |
|------|--------|------|
| web_search / media_crawler | v0.2.0 | 信息来源扩展需独立设计调度层 |
| mixed 检索策略 | v0.2.0 | 依赖 agentic + hybrid 先稳定 |
| 并行 tool calls | v0.2.0 | 依赖 LLM provider 的 native parallel tool calling |
| 评测体系 | v0.2.0 | 先让功能可用，再系统化评测 |

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
  tools.py                   # 内置工具: search_keywords, read_document, list_documents
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
          {"type": "tool_call",    "tool": "search_keywords", "args": {...}, "round": 1}
          {"type": "tool_result",  "tool": "search_keywords", "count": 5, "round": 1}
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

三个工具全部对 `Document.full_text` 操作，跑在 PostgreSQL 上，不经过 Chunk，不依赖 embedding。

```python
# services/agent/tools.py

search_keywords = Tool(
    name="search_keywords",
    description=(
        "在知识库文档全文（full_text）中搜索关键词或短语。"
        "返回匹配的文档片段（ts_headline），适合查找特定概念、术语、事实。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索词或短语。普通文本即可，无需特殊语法",
            },
            "document_ids": {
                "type": "array", "items": {"type": "string"},
                "description": "限定文档 ID 列表。不传则搜索整个知识库。",
            },
            "top_k": {
                "type": "integer", "default": 5,
                "description": "返回结果数量",
            },
        },
        "required": ["query"],
    },
    execute=_search_keywords_impl,
)

read_document = Tool(
    name="read_document",
    description=(
        "读取文档的指定部分。先用 search_keywords 找到相关位置，"
        "再用此工具深入阅读完整上下文。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "document_id": {"type": "string"},
            "offset": {"type": "integer", "description": "从第几个字符开始（0-based）"},
            "length": {"type": "integer", "default": 3000, "description": "读取字符数"},
        },
        "required": ["document_id"],
    },
    execute=_read_document_impl,
)

list_documents = Tool(
    name="list_documents",
    description="列出知识库中所有文档，返回标题和大小。用于了解有哪些文档可用。",
    parameters={"type": "object", "properties": {}},
    execute=_list_documents_impl,
)
```

**Tool 实现示例**（`_search_keywords_impl` 签名示意）：

```python
def _search_keywords_impl(ctx: ToolContext, query: str, document_ids=None, top_k=5) -> ToolResult:
    rows = _execute_fts(ctx.db, ctx.kb_id, query, document_ids, top_k)
    artifacts = [
        Artifact(
            data={"doc_id": r["id"], "title": r["title"], "snippet": r["snippet"], "rank": r["rank"]},
            source=r["id"],
        )
        for r in rows
    ]
    summary = _build_summary(rows, max_chars=500)
    return ToolResult(
        summary=summary,
        artifacts=artifacts,
        artifact_count=len(artifacts),
        metadata={"latency_ms": 45, "documents_scanned": len(rows)},
    )
```

**Tool 返回设计原则**：`summary` 字段只给 LLM 看 200-500 字摘要 + 元数据，避免大段文本撑爆 context。`artifacts` 存结构化完整数据（每个 `Artifact` 在构造时校验 JSON 可序列化），由调用方（AgenticSearchStrategy / ReportWorkflow）收集用于最终输出。

### 3.6 两种预置配置

```python
# services/agent/configs.py

SEARCH_AGENT_CONFIG = AgentConfig(
    tools=[search_keywords, read_document, list_documents],
    system_prompt="""\
You are a research assistant searching a knowledge base to answer questions.

IMPORTANT — Document IDs are UUIDs:
  Every document has a UUID like '550e8400-e29b-41d4-a716-446655440000'.
  You can only obtain valid UUIDs from list_documents() or search_keywords() results.
  Never pass a document title, filename, or any string that is not a UUID
  to read_document() or search_keywords()'s document_ids parameter.

Workflow:
1. Call list_documents() first to discover available documents and their UUIDs
2. Use search_keywords() to find relevant passages — note the UUIDs in results
3. Use read_document() with the exact UUID from step 1 or 2 to get full context
4. Cross-validate with additional searches from different angles
5. When you have enough information, give a final answer with citations

Stop when you can fully answer the question, or after searching from 2-3 different angles.
Do NOT stop after the first search — always verify with at least one cross-check.""",
    max_rounds=5,
    early_stop_patience=2,
)

GATHER_AGENT_CONFIG = AgentConfig(
    tools=[search_keywords, read_document, list_documents],
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
AgentRunner(SEARCH_AGENT_CONFIG)  ──→  AgenticSearchStrategy.search()
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

### 4.1 策略注册表

```python
# services/retrieval/strategies/__init__.py

class SearchStrategy(Protocol):
    """检索策略协议。每个策略实现 search()，返回统一的 RetrievalQueryResponse。"""
    def search(
        self, db: Session, *,
        query: str, knowledge_base_id: str, top_k: int,
        document_ids: list[str] | None,
    ) -> RetrievalQueryResponse: ...


STRATEGIES: dict[str, SearchStrategy] = {}

def register(name: str):
    """装饰器注册策略。"""
    def decorator(cls):
        STRATEGIES[name] = cls()
        return cls
    return decorator
```

### 4.2 service.py — 策略分发器

```python
# services/retrieval/service.py (改造后)

class RetrievalService:
    DEFAULT_STRATEGY = "agentic"

    @staticmethod
    def search(
        db, *, query, knowledge_base_id, top_k=10,
        document_ids=None, strategy: str | None = None,
    ) -> RetrievalQueryResponse:
        strategy_name = strategy or RetrievalService.DEFAULT_STRATEGY
        impl = STRATEGIES.get(strategy_name)
        if impl is None:
            raise ValidationError(
                f"Unknown search strategy: {strategy_name}. "
                f"Available: {list(STRATEGIES.keys())}"
            )
        return impl.search(
            db, query=query, knowledge_base_id=knowledge_base_id,
            top_k=top_k, document_ids=document_ids,
        )
```

### 4.3 两种策略

#### AgenticSearchStrategy（默认）

```python
# services/retrieval/strategies/agentic.py

@register("agentic")
class AgenticSearchStrategy:
    """Agent 多轮推理检索 — 零 embedding 成本。"""

    def __init__(self):
        self._agent = AgentRunner(llm_provider, SEARCH_AGENT_CONFIG)

    def search(self, db, *, query, knowledge_base_id, top_k, document_ids):
        ctx = ToolContext(db=db, kb_id=knowledge_base_id)
        result = self._agent.run(
            task=f"Answer this question using the knowledge base:\n{query}",
            ctx=ctx,
        )
        # 从 collected_artifacts 构建 RetrievalQueryResponse
        return _artifacts_to_response(db, query=query, artifacts=result.collected_artifacts)
```

不调用 embedding API。不依赖 Chunk 表。只依赖 PostgreSQL FTS + Document.full_text。

#### HybridSearchStrategy（保留）

```python
# services/retrieval/strategies/hybrid.py

@register("hybrid")
class HybridSearchStrategy:
    """现有 hybrid search — 从 service.py 搬迁，逻辑不变。"""

    def search(self, db, *, query, knowledge_base_id, top_k, document_ids):
        query_embedding = embedder.embed([query])[0]
        chunk_scores = hybrid_search(db, query=query, query_embedding=query_embedding, ...)
        # ... 现有逻辑不变
```

### 4.4 接入 ChatService

```python
# schemas/chat.py — ChatRequest 加一个字段

class ChatRequest(BaseModel):
    knowledge_base_id: str
    session_id: str | None = None
    content: str = Field(min_length=1, max_length=2000)
    reference_document_ids: list[str] | None = None
    search_strategy: str = "agentic"          # NEW
```

```python
# services/chat.py — 只加一个参数

class ChatService:
    @staticmethod
    def send_message(db, *, kb_id, user_id, session_id,
                     content, reference_document_ids=None, search_strategy="agentic"):
        # ... session resolve (不变) ...

        retrieval = RetrievalService.search(
            db,
            query=content, knowledge_base_id=kb_id, top_k=10,
            document_ids=doc_ids,
            strategy=search_strategy,          # ← 唯一新增参数
        )

        context = _build_context(retrieval)     # ← 不感知策略
        # ... LLM generate (不变) ...
```

**ChatService 和 `_build_context()` 完全不感知策略差异**——它们只消费 `RetrievalQueryResponse`。

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
services/studio/              # NEW
  __init__.py
  runner.py                   # StudioTaskRunner — 接收 StudioTask，执行 workflow
  types.py                    # ReportConfig, ReportResult, OutputFormat
  templates/
    report.py                 # ReportWorkflow: plan → gather → generate → assemble → store
    ppt.py                    # PPTWorkflow
  generators/
    markdown.py               # Markdown 拼接 + 格式化
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
# services/studio/templates/report.py

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

> agentic search 跑在 Document.full_text 上，不依赖 chunk。但 hybrid 依赖 chunk → chunk 质量影响 hybrid 精度。优化仍有价值。

### 7.2 Agent 优化

| 优化 | v0.1.0 | 说明 |
|------|--------|------|
| **早停机制** | ✅ | 连续 N 轮无新信息 → 提前终止，`early_stop_patience` |
| **Tool 返回摘要** | ✅ | `ToolResult.summary` 200-500 字，不喂全文给 LLM |
| **搜索 query 重写** | v0.2.0 | Agent 在 search_keywords 前自扩展关键词 |
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

回答"检索质量好不好？回答准不准？"需要分层评测：

### 8.1 Level 1：检索评测（组件级）

**测试集**：对 KB 预埋 N 个问题，每个问题标注相关文档：

```python
# tests/eval/test_set.py
TEST_QUERIES = [
    {
        "question": "安全架构中的认证机制是什么？",
        "relevant_docs": ["doc-A", "doc-B"],
        "relevant_chunks": ["chunk-3", "chunk-7"],
        "difficulty": "medium",
    },
    # ...
]
```

**指标**：Recall@K、MRR、NDCG@K

**命令**：`python -m tests.eval.retrieval_eval --strategy agentic --kb-id xxx`

### 8.2 Level 2：回答评测（端到端）

**方法**：LLM-as-Judge（用更强的模型当裁判）

**指标**：Correctness、Faithfulness（有无幻觉）、Citation Accuracy、Completeness

**命令**：`python -m tests.eval.answer_eval --strategy agentic --kb-id xxx`

### 8.3 目录

```
tests/eval/
  __init__.py
  test_set.py              # 测试集定义
  retrieval_eval.py        # Level 1: Recall@K, MRR, NDCG
  answer_eval.py           # Level 2: LLM-as-Judge
  results/                 # 评测结果输出（JSON），含历史版本对比
```

### 8.4 执行频率

```
pytest -m "not slow"               # CI 每次都跑（单元测试）
python -m tests.eval.*_eval         # 手动跑 / 大改动后跑
results/ 目录存版本对比             # 追踪退化
```

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
  ── strategies/ (__init__.py, agentic.py, hybrid.py)
  ── RetrievalService 改为分发器，DEFAULT_STRATEGY="agentic"
  ── ChatRequest 加 search_strategy，ChatService 透传
  ── SSE 事件扩展（agent_progress: listing/searching/reading/analyzing/error）
  ── 前端 SSE 客户端（parseSSEStream + 工作区 agent 步骤展示）

Phase 3: v0.1.0 剩余
  ── URL 导入（新增 Source type=url，HTTP 抓取 → parse → index）
  ── StudioTask 模型 + repository + schema
  ── services/studio/ (runner.py, types.py, templates/report.py, generators/markdown.py, generators/pptx.py)
  ── chunk+embed 按需触发（入库只做 parse，用户选 hybrid 时才跑）
  ── PPT 生成（python-pptx）
  ── Chunk: 结构化元素保护（标题、代码块、表格不跨边界切分）
  ── BackgroundTasks 执行 + 前端轮询进度
  ── Studio API (create / status / download / list / delete)
  前端: StrategySelector + StudioPanel + TaskCard

Phase 4: v0.2.0
  ── Web Search
  ── Git 仓库同步
  ── tests/eval/ (test_set.py, retrieval_eval.py, answer_eval.py)
  ── 评测结果汇总脚本
```

每个 Phase 独立上线、不破坏现有功能。

---

## 附录：v0.1.0 新增/修改文件清单

> 当前完整目录结构见 @docs/engineering-standards.md。

### ✅ 已实现（Phase 1 + 2）

```
新增:
  services/agent/__init__.py, runner.py, types.py, tools.py, configs.py
  services/retrieval/strategies/__init__.py, agentic.py, hybrid.py
  core/telemetry.py                                 # Langfuse tracing
  tests/services/test_agent_runner.py

修改:
  services/llm.py               # 加 generate_with_tools, generate_stream, ToolCallDecision
  services/chat.py              # 加 stream_message, search_strategy
  services/retrieval/service.py # 策略分发器，DEFAULT_STRATEGY="agentic"
  schemas/chat.py               # 加 search_strategy
  api/chat.py                   # SSE streaming 端点
  config.py                     # 加 EmbeddingConfig, TelemetryConfig
  main.py                       # 注册 sessions router, telemetry init
```

### ⏳ 待实现（Phase 3–4）

```
新增:
  services/studio/              # StudioTaskRunner, ReportWorkflow, generators/markdown.py, generators/pptx.py
  models/studio_task.py
  repositories/studio_task.py
  schemas/studio.py
  api/studio.py
  tests/api/test_studio.py
  tests/eval/                   # test_set.py, retrieval_eval.py, answer_eval.py（v0.2.0）

修改:
  services/indexing/pipeline.py  # chunk+embed 按需触发，入库只做 parse
  models/source.py              # type 枚举扩展 url，新增 url 抓取逻辑
  services/source.py            # URL 导入：抓取 → parse → index

前端:
  components/chat/StrategySelector.tsx
  components/studio/StudioPanel.tsx, TaskCard.tsx, TaskProgress.tsx
  hooks/useStudioTask.ts
```
