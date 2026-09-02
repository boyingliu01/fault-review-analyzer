# Phase 2/6 DESIGN Summary

## Sprint: sprint-20260826-62

## 完成内容
1. **需求澄清**：通过 question 工具向用户确认 4 个关键设计决策
   - 批次划分：按分析运行时间分批
   - urid 链接格式：https://dev.iwhalecloud.com/portal/zcm-devspace/spa/task/pc/{urId}
   - 批注持久化：JSON 文件（batches.json + annotations.json）
   - 帕累托 TopN：全部展示，按原因降序 + 累计占比线

2. **设计文档**：review/ui-iteration-design.md
   - 覆盖 6 项需求（批次隔离、帕累托图、规范条款、明细联动、urid链接、详情联动）
   - 后端存储设计（批次推断优先级、原子写、孤儿处理、批注清理）
   - 前端 UI 设计（sidebar 左导览 + 右明细、Plotly 帕累托、联动、筛选）
   - 测试策略（数据层 + UI 层 + AppTest）

3. **R2 delphi-review**：delphi-reviewer-technical
   - 首轮 REQUEST_CHANGES（9 项 P0/P1：selection_mode single-row、LinkColumn URL字符串、all_analysis时间戳分批、孤儿处理、curve_number过滤等）
   - 已全部修正设计文档
   - 复审 APPROVED（consensus 1.0）

4. **规范产物**：
   - specification.yaml（6 REQ + 后端存储 + 技术选型 + 测试）
   - slices-manifest.json（3 slices）
   - requirements-reviewed.json（R1 + R2 均 approved）
   - delphi-reviewed.json（verdict: APPROVED）

## 设计产物
- review/ui-iteration-design.md
- .sprint-state/specification.yaml
- .sprint-state/slices-manifest.json
- .sprint-state/requirements-reviewed.json
- .sprint-state/delphi-reviewed.json

## 决策
- 标准流程（6 阶段）
- 采用 Plotly 6.6 帕累托图 + Streamlit 1.55 联动
- 后端批次 JSON 存储，不迁移现有数据

## next_phase_context
- BUILD 阶段 3 个 slice：review_data.py 数据层 / streamlit_app.py UI 层 / run_all_parallel.py 批次写入
- 技术依赖已确认：plotly 6.6、streamlit 1.55、pandas 2.3
- venv 复用主目录 E:\Study\LLM\Bug聚类分析\.venv
