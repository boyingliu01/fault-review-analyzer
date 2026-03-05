# Consistency Analysis

## Feature
[与 specify.md 中的功能名称保持一致]

## Overview
验证 specify.md（规格）、plan.md（设计）、tasks.md（任务）三者之间的一致性。

## Traceability Matrix

### Requirements Coverage

| 需求 | specify.md 来源 | plan.md 覆盖 | tasks.md 任务 | 状态 |
|------|----------------|-------------|--------------|------|
| 需求 1 | 验收标准 #1 | Phase 2 | Task 2.1 | ✅ |
| 需求 2 | 验收标准 #2 | Phase 2 | Task 2.2 | ✅ |
| 需求 3 | 验收标准 #3 | - | - | ❌ 缺失 |

## Consistency Checks

### specify.md vs plan.md
- [ ] specify.md 的所有需求在 plan.md 中有对应设计
- [ ] 数据模型匹配
- [ ] 错误处理方案一致
- [ ] 业务规则已在设计中体现

**不一致项**：
- [ ] **问题**：[描述]
  - specify.md 中：[说了什么]
  - plan.md 中：[说了什么]
  - **解决方案**：[如何解决]

### plan.md vs tasks.md
- [ ] plan.md 中所有组件在 tasks.md 中有对应任务
- [ ] 测试策略已分解为具体测试任务
- [ ] 风险缓解措施有对应任务

**不一致项**：
- [ ] **问题**：[描述]

### specify.md vs tasks.md
- [ ] 所有验收标准有对应测试任务
- [ ] 边界情况有对应测试

## Gap Analysis

### 缺失需求（specify.md 未在 plan/tasks 中覆盖）
- [ ] **缺失**：[描述]
  - **影响**：[影响]
  - **优先级**：P0/P1/P2/P3
  - **行动**：[需要做什么]

### 缺失测试（场景未被测试任务覆盖）
- [ ] **缺失**：[描述]
  - **类型**：Unit / Integration
  - **风险**：[没有此测试的风险]

## Quality Checks

### SDD 遵从性
- [ ] specify.md 描述 WHAT，不描述 HOW
- [ ] plan.md 将 WHAT 转化为 HOW
- [ ] tasks.md 将实现分解为可执行步骤
- [ ] 三份文档保持一致

### 与项目原则的对齐
- [ ] 设计遵循 Clean Architecture
- [ ] 代码将遵循 SOLID 原则
- [ ] 实现将采用 TDD
- [ ] 质量门禁已定义

## Action Items

### Critical（必须解决）
1. [ ] [问题描述]
   - **Owner**: [Name]
   - **Status**: Open

### High Priority（应当解决）
1. [ ] [问题描述]

## Sign-off

- [ ] specify.md 已审查：[Name] / [Date]
- [ ] plan.md 已审查：[Name] / [Date]
- [ ] tasks.md 已审查：[Name] / [Date]
- [ ] 整体批准：[Name] / [Date]

---

**Summary**: [一致性状态的简要说明]
**Status**: Consistent / Minor Inconsistencies / Major Inconsistencies
**Ready for Implementation**: Yes / No
**Last Updated**: [YYYY-MM-DD]
