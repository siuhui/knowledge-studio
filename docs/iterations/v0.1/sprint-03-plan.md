# v0.1 Sprint 03 Plan（权限、评测与发布准备）

## 1. Sprint 目标
完成上线前治理能力，建立冲刺 v1.0 的质量闸门。

## 2. 工作拆分（WBS）

### A. 权限与鉴权
- A1: RBAC 角色定义（admin/editor/viewer）
- A2: 检索前权限过滤（文档/chunk）
- A3: 越权访问测试用例

### B. 审计与反馈
- B1: 查询与回答审计日志
- B2: `POST /api/v1/feedback` 接口
- B3: feedback 归因分类（检索/生成/知识缺失）

### C. 评测体系
- C1: 构建 100~300 条评测集
- C2: 指标计算脚本（Recall@10、MRR、幻觉率）
- C3: 基线对比报告（当前 vs 上一稳定）

### D. 发布准备
- D1: 灰度发布流程（10%->30%->100%）
- D2: 回滚脚本与演练
- D3: 发布 checklist

## 3. 接口与数据变更
- API: `POST /api/v1/feedback`
- 表: `feedback_record`, `audit_log`

## 4. 验收标准（DoD）
- 越权检索拦截率 100%
- 评测结果达到 v1.0 门槛
- 灰度与回滚演练通过

## 5. 风险与依赖
- 风险：评测集覆盖不足导致上线风险
- 依赖：真实业务问题样本供给

## 6. 输出物
- 评测报告
- 灰度发布记录
- 回写到 `kb-rag-quality-gate/prd.md` 与 `td.md`
