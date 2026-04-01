# v0.1 Sprint 02 Plan（检索与问答）

## 1. Sprint 目标
完成混合检索与带引用 RAG 问答，形成可用用户体验。

## 2. 工作拆分（WBS）

### A. 查询理解
- A1: query 规范化（空白、标点、同义词）
- A2: 问题类型分类（事实/流程/对比）
- A3: filter 合并（部门、时间、权限）

### B. 混合检索
- B1: BM25 检索通道
- B2: 向量检索通道
- B3: 融合打分与 topK 合并
- B4: 最小重排（规则或轻量模型）

### C. 上下文构建与生成
- C1: 上下文窗口裁剪（token budget）
- C2: 回答模板（摘要/步骤/风险）
- C3: citation 绑定（doc_id/chunk_id/score）
- C4: 低置信兜底（澄清建议）

### D. API 与会话
- D1: `POST /api/v1/qa/ask`
- D2: `POST /api/v1/retrieval/query`
- D3: session/message 持久化

### E. 性能优化
- E1: 查询缓存（hot query）
- E2: P95 延迟压测与瓶颈定位

## 3. 接口与数据变更
- API: QA/Search 两个核心接口
- 表: `qa_session`, `qa_message`, `qa_citation`

## 4. 验收标准（DoD）
- 回答必须包含 citations
- 引用覆盖率 >= 95%（样本集）
- QA 首字延迟 P95 < 3s（目标环境）

## 5. 风险与依赖
- 风险：重排性能影响时延
- 依赖：模型网关稳定性、缓存可用性

## 6. 输出物
- QA 接口联调文档
- 压测报告
- 回写到 `kb-rag-foundation/prd.md` 与 `td.md`

## 7. 当前状态（2026-04-01）
- 已完成最小可用闭环（MVP）：
  - `POST /api/v1/retrieval/query`：按 `kb_id` 范围检索分片并返回 `citation`。
  - `POST /api/v1/qa/ask`：检索增强回答（模板式）并返回引用。
  - 读权限校验：无权限统一返回 `PERMISSION_DENIED`。
- 当前实现边界：
  - 检索为词项匹配打分（未接入 BM25/向量/重排）。
  - 生成为模板回答（未接入 LLM 网关）。
- 测试覆盖：
  - 检索命中
  - 问答带引用
  - 无权限拒绝
