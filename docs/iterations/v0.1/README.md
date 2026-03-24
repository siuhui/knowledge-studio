# v0.1 迭代总览（开发基线）

## 版本定位
- `v0.1`：未上线开发版本（internal/dev only）
- `v1.0`：首个生产发布版本（GA）

## 迭代目标
在 3 个 sprint 内完成可演示、可联调、可评测的 0->1 核心能力闭环。

## 关联功能（事实源）
- `kb-rag-foundation`
- `kb-rag-quality-gate`

## 文档索引
- `sprint-01-plan.md`（数据接入与索引）
- `sprint-02-plan.md`（检索与问答）
- `sprint-03-plan.md`（权限、评测与发布准备）`n- `implementation-log.md`（实施进展）

## 里程碑出口条件
- Sprint 01：完成 ingest->index 基础链路，支持最小可检索集
- Sprint 02：完成带引用问答，关键链路可压测
- Sprint 03：完成质量门禁与灰度脚本，具备冲刺 v1.0 条件

## 回写要求
每个 sprint 结束前，需将有效结论回写至 `docs/features/*`。

