# v0.1 迭代总览（开发基线）

## 版本定位
- `v0.1`：未上线开发版本（internal/dev only）
- `v1.0`：首个生产发布版本（GA）

## 开发顺序（已调整）
- Sprint 01：用户/团队/知识库访问控制（优先）
- Sprint 02：数据接入与索引
- Sprint 03：检索与问答
- Sprint 04：权限治理、评测与发布准备

## 关联功能（事实源）
- `kb-user-team-access`
- `kb-rag-foundation`
- `kb-rag-quality-gate`

## 文档索引
- `sprint-01-user-team-kb-plan.md`（用户/团队/知识库访问）
- `sprint-02-ingest-index-plan.md`（数据接入与索引）
- `sprint-03-retrieval-qa-plan.md`（检索与问答）
- `sprint-04-governance-release-plan.md`（权限、评测与发布准备）
- `implementation-log.md`（实施进展）

## 里程碑出口条件
- Sprint 01：完成用户、团队、知识库权限基础能力
- Sprint 02：完成 ingest->index 基础链路，支持最小可检索集
- Sprint 03：完成带引用问答，关键链路可压测
- Sprint 04：完成质量门禁与灰度脚本，具备冲刺 v1.0 条件

## 当前执行阶段
- `Sprint 01`（kb-user-team-access）

## 回写要求
每个阶段结束前，需将有效结论回写至 `docs/features/*`。
