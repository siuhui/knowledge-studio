# 知识库系统总体技术设计（可演进架构）

## 1. 目标与原则

本设计基于 PRD《knowledge-base-rag-ai-prd.md》的 3 阶段路线（可用版 -> 提效版 -> 智能版），目标是构建一个可持续演进的 RAG + AI 知识平台。

设计原则：
- 分层解耦：数据处理、检索、生成、应用、治理分层清晰
- 渐进增强：MVP 可快速上线，架构不推倒重来
- 可替换性：模型、向量库、重排器、工作流引擎可插拔
- 高可观测：全链路日志、指标、追踪、评测闭环
- 安全优先：鉴权前置、最小权限、可审计

---

## 2. 分阶段演进架构

### 阶段 1（1-2 个月）可用版
目标：具备“可用的企业知识检索问答”。

能力范围：
- 文档/Wiki 接入、增量同步
- 基础清洗、切片、向量化、混合检索
- RAG 问答 + 来源引用
- 基础 RBAC 与审计

技术实现建议：
- 单体模块化（Modular Monolith）优先，减少早期分布式复杂度
- 对外提供统一 API Gateway
- 数据处理采用异步任务队列

### 阶段 2（3-4 个月）提效版
目标：把“问答”升级为“业务提效工具”。

能力范围：
- 查询改写、检索路由、重排
- SOP 引导、工单草稿、专题知识包
- 反馈闭环与离线评测
- 过期知识治理自动化

技术实现建议：
- 将高负载模块服务化拆分：Indexing Service / Retrieval Service / Generation Service
- 引入 Workflow Engine 承载 AI 流程编排
- 增加缓存层（Query Cache + Context Cache）

### 阶段 3（5-6 个月）智能版
目标：形成“知识驱动执行”的 AI Agent 平台。

能力范围：
- 跨系统 Agent 工具调用
- 知识图谱增强检索
- 任务执行回写知识库
- 业务线 Copilot 定制

技术实现建议：
- 引入 Agent Runtime（工具注册、策略、沙箱）
- 图谱检索与向量检索协同（GraphRAG）
- 统一策略中心（模型路由、权限策略、风控策略）

---

## 3. 总体技术架构

## 3.1 逻辑分层
- 接入层（API/BFF）：Web、管理后台、开放 API、Webhook
- 应用层：问答、SOP、工单助手、培训助手、运营后台
- AI 编排层：Prompt Orchestrator、工具路由、模型网关
- 检索层：Query 理解、多路召回、重排、上下文构建
- 数据处理层：采集、清洗、切片、向量化、索引构建
- 数据存储层：关系库、对象存储、搜索引擎、向量库、缓存
- 治理层：权限、审计、评测、监控、成本控制

## 3.2 核心服务拆分（目标态）
- `gateway-service`：鉴权、限流、路由、租户隔离
- `kb-ingestion-service`：连接器管理、同步调度、解析清洗
- `kb-index-service`：切片、embedding、索引更新
- `kb-retrieval-service`：查询理解、召回、重排、过滤
- `kb-generation-service`：Prompt 编排、LLM 调用、答案组装
- `kb-workflow-service`：SOP/工单等 AI 流程执行
- `kb-governance-service`：质量评测、反馈处理、知识治理
- `kb-agent-service`（阶段 3）：工具注册、任务执行、回写

---

## 4. 技术栈选型

## 4.1 服务端
- 语言：`TypeScript` + `Python`
- API 服务框架：`NestJS`（业务 API、治理后台）
- AI/检索服务：`FastAPI`（向量化、检索、生成编排）
- 原因：
  - TypeScript 适合工程化与团队协作
  - Python 生态适合 RAG、模型调用、评测链路

## 4.2 存储与中间件
- 关系数据库：`PostgreSQL`（业务数据、配置、审计）
- 向量能力：`pgvector`（阶段 1/2） -> 可平滑迁移 Milvus/Weaviate（阶段 3 高规模）
- 全文检索：`OpenSearch`（BM25、过滤、聚合）
- 对象存储：`MinIO` 或云对象存储（原文、切片快照）
- 缓存：`Redis`（查询缓存、会话上下文、幂等键）
- 消息队列：`RabbitMQ`（异步任务）

## 4.3 AI 相关
- 编排框架：`LangGraph`（多步骤流程、状态可追踪）
- 模型网关：自建 `LLM Gateway`（统一供应商、限流、回退）
- Embedding 模型：可配置（中文优先模型 + 通用多语模型）
- 重排模型：Cross-Encoder（阶段 2 引入）
- 观测：`OpenTelemetry` + `Prometheus` + `Grafana`

## 4.4 前端
- 管理端/应用端：`Next.js` + `TypeScript`
- 组件：`Ant Design`（管理后台）+ 业务自定义组件
- 状态管理：`TanStack Query` + 轻量 store

---

## 5. 关键数据模型（简化）

核心实体：
- `knowledge_source`：数据源配置（类型、连接信息、同步策略）
- `knowledge_document`：文档元数据（版本、权限、状态、责任人）
- `knowledge_chunk`：切片内容（chunk_id、内容、token 数、embedding_ref）
- `knowledge_index_job`：索引任务（状态、错误、耗时）
- `qa_session` / `qa_message`：问答会话与多轮上下文
- `qa_citation`：答案引用（doc_id、chunk_id、置信度）
- `feedback_record`：用户反馈（有用性、纠错、补充）
- `evaluation_run`：离线评测记录（指标、样本、版本）
- `agent_task`（阶段 3）：任务执行记录与工具调用日志

模型设计要点：
- 文档与切片双版本号（`doc_version` / `index_version`）
- 权限字段下沉到 chunk 级（支持段落级过滤）
- 所有答案必须绑定 citation 记录（支持追溯）

---

## 6. 核心流程设计

## 6.1 数据入库流程
连接器拉取 -> 原文存储 -> 清洗解析 -> 切片 -> embedding -> 索引写入（向量+全文）-> 版本发布。

## 6.2 查询回答流程（RAG）
用户问题 -> 查询理解（改写/分类）-> 混合召回 -> 重排 -> 上下文裁剪 -> 生成答案 -> 引用绑定 -> 返回。

## 6.3 反馈闭环流程
用户反馈 -> 归因（检索问题/生成问题/知识缺失）-> 自动创建优化任务 -> 策略迭代 -> 回归评测。

## 6.4 AI 工作流流程（SOP）
任务触发 -> 识别场景 -> 生成步骤指导 -> 用户确认 -> 执行回执 -> 结果回写知识库。

---

## 7. 安全与合规设计

- 身份认证：OIDC/SAML 单点登录
- 鉴权：RBAC + ABAC（租户、部门、角色、数据密级）
- 权限执行点：检索前过滤、生成前校验、导出前校验
- 数据安全：TLS + 存储加密 + 密钥托管
- 隐私保护：PII 检测与脱敏、日志脱敏
- 审计：查询行为、引用来源、导出行为、Agent 调用记录

---

## 8. 可观测性与质量保障

- 指标：
  - 技术指标：QPS、P95、错误率、任务积压
  - RAG 指标：Recall@K、MRR、引用覆盖率、幻觉率
  - 业务指标：FRT、工单一次解决率、复用率
- 日志：
  - 请求日志、检索日志、模型调用日志、引用日志
- 追踪：
  - 每次回答具备 TraceId，可串联检索与生成链路
- 评测：
  - 离线评测集 + 线上抽样对比 + A/B 实验

---

## 9. 部署与环境规划

环境划分：`dev` / `staging` / `prod`

部署建议：
- 容器化：Docker
- 编排：Kubernetes
- 网关：Nginx Ingress / API Gateway
- CI/CD：GitHub Actions 或 GitLab CI
- 基础设施即代码：Terraform（可选）

弹性策略：
- 检索与生成服务独立扩缩容
- 异步任务 Worker 按队列积压自动扩容
- 模型调用支持多供应商熔断与回退

---

## 10. 里程碑交付物映射（对应 PRD）

阶段 1 交付：
- 混合检索问答闭环
- 文档引用可追溯
- 基础权限与审计

阶段 2 交付：
- 查询路由 + 重排
- SOP/工单 AI 流程
- 反馈闭环 + 评测平台

阶段 3 交付：
- Agent 工具调用
- GraphRAG 能力
- 业务线 Copilot 定制能力

---

## 11. 关键技术决策（ADR 建议）

建议在 `docs/architecture/adr/` 持续新增 ADR 文档，优先记录：
- 选择 pgvector + OpenSearch 作为初期方案的依据
- 为什么阶段 1 采用模块化单体而非微服务
- 何时触发向量库独立化（规模阈值）
- 模型供应商路由与降级策略

以上决策应包含：背景、备选方案、决策结果、影响范围、回滚策略。
