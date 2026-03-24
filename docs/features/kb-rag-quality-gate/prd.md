# 功能 PRD：RAG 质量门禁

## 元信息
- feature_id: `kb-rag-quality-gate`
- owner: `TBD`
- status: `active`
- version_introduced: `v0.1`
- version_updated: `v0.1`

## 目标
建立可执行的 RAG 质量门禁，作为版本发布前置条件。

## 范围
- 离线评测集规范
- 核心指标与阈值
- 灰度发布与回滚门禁

## 验收
- 每次模型/检索策略变更均有评测记录
- 未达阈值不得全量发布
- 发布版本可追溯到评测结果

