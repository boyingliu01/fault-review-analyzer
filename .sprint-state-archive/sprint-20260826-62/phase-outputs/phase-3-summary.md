# Phase 3/6 BUILD Summary

## Sprint: sprint-20260826-62

## 完成内容（TDD: RED → GREEN）

### Slice 1: review_data.py 数据层（16 tests）
- 新增批次加载/推断：load_batches/save_batches
  - 优先级：batches.json > all_analysis_*.json 时间戳 > 孤儿归入"未归档"
  - 原子写（tmp + os.replace）+ batch_id 去重 + 损坏回退
- build_summary_df：根因降序 + 累计占比(%)（帕累托）
- build_violation_df：新增条款内容(rule_name)列，按 rule_id 聚合
- build_detail_url：研发云链接（RDEV_DETAIL_URL_TEMPLATE 环境变量可覆盖）
- build_detail_df：新增研发云链接列
- add_annotation/load_annotations：批次批注 + 孤儿清理

### Slice 2: streamlit_app.py UI 层（9 AppTest tests）
- 左侧 sidebar 批次导览：批次选择 + 批注添加 + 批次统计
- 右侧：帕累托图(Plotly 降序柱+累计线, curve_number==0 过滤)、规范违规分布(含条款)、缺陷明细(LinkColumn 链接 + 筛选 + single-row 联动)、单起详情(联动)
- 修复 use_container_width → width=stretch（Streamlit 1.55 弃用）

### Slice 3: run_all_parallel.py + .env.example
- _append_batch_index：分析完成后原子追加批次到 batches.json
- .env.example：新增 RDEV_DETAIL_URL_TEMPLATE

## 验证
- 全量测试：1298 passed, 85 deselected(e2e), 0 failures
- ruff: src/ui + tests/ui 全通过（scripts/run_all_parallel.py 8 个预先存在错误，未新增）
- LSP diagnostics: 干净
- AppTest 真实渲染：0 异常，帕累托图/2表格/3批次选择器正常
- 真实数据：181 起 → 3 批次（5 + 162 + 14未归档）= 181 ✓

## 决策
- violation 表点击联动未实现（帕累托图已覆盖根因联动），保留条款手动筛选
- scripts/ 预先存在的 ruff 错误不修（非本次引入，不在 CI 严格范围）

## next_phase_context
- VERIFY：已通过全量测试+ruff+AppTest，需 browser 可视化验证
- 数据环境：worktree 用 junction 链接 output + 复制 swagger.txt
