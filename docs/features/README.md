# 功能文档目录

本目录是功能级文档的单一事实源（Single Source of Truth）。

## 结构约定
- `docs/features/<feature-id>/prd.md`
- `docs/features/<feature-id>/td.md`
- `docs/features/<feature-id>/changelog.md`
- 可选：`api-contract.md`、`data-schema-migration.md`、`runbook.md`

## 维护规则
- 每次迭代开发在 `docs/iterations/` 记录执行计划与决策。
- 代码合并前，必须将最终结论回写到对应 feature 文档。
- `docs/releases/` 仅做版本映射，不承载主设计内容。
