# Phase 1/6 PREP Summary

## Sprint
- ID: sprint-20260826-62
- Branch: sprint/2026-08-26-01
- Worktree: .worktrees/sprint/sprint-2026-08-26-01

## 需求
Streamlit UI 迭代优化（6 项）：
1. 批次隔离 + 左右分栏（左导览/批注，右明细）
2. 帕累托图展示根因（Top3/Top5）
3. 规范违规分布补充条款内容
4. 缺陷明细与帕累托/违规联动 + 筛选
5. urid 增加研发云跳转链接
6. 单起缺陷详情与缺陷明细联动

## AUTO-ESTIMATE
- 变更类型: 修改已存在代码（UI 迭代）
- 影响文件: src/ui/streamlit_app.py (163行), src/ui/review_data.py (96行), tests/ui/test_streamlit_app.py
- 跨模块: src/ui/ 为主，涉及 review_data 后端加载逻辑扩展
- 循环依赖: 无
- Public API: load_review_records/build_summary_df/build_detail_df/build_violation_df/get_detail_by_urid
- 测试: tests/ui/test_streamlit_app.py (4 tests)
- 评分: 5 分 → **标准流程**

## 环境说明
- worktree 中无 output/ 数据目录（gitignore）
- UI 测试用 mock 数据（tests/ui 4 passed 基线通过）
- Streamlit 实际预览在主目录跑（有真实 181 起数据）
- venv 复用主目录: E:\Study\LLM\Bug聚类分析\.venv

## 决策
- 采用标准流程（6 阶段）
- 数据策略：代码在 worktree 开发，测试 mock 验证，真实预览在主目录
