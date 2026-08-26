# Streamlit UI 迭代优化 — 设计文档

**Sprint**: sprint-20260826-62
**日期**: 2026-08-26
**状态**: 待用户审批

## 1. 需求概述

在 MVP（v0.1.0）基础上，对 Streamlit 复盘分析界面做 6 项展示与易用性优化：

| # | 需求 | 核心诉求 |
|---|------|---------|
| 1 | 批次隔离 + 左右分栏 | 多批次复盘互不干扰；左导览（批次列表+批注），右明细 |
| 2 | 帕累托图 | 根因按频率**降序**排列 + 累计占比线（用户自行关注 Top3/Top5） |
| 3 | 规范条款内容 | 违规分布补充 `rule_name` 条款内容 |
| 4 | 明细联动 + 筛选 | 明细与帕累托图/违规分布联动，支持按根因/条款筛选 |
| 5 | urid 链接 | urId 可点击跳转研发云查看明细 |
| 6 | 单起详情联动 | 明细选中某行 → 下方详情同步更新 |

## 2. 设计决策（用户已确认）

| 决策点 | 用户选择 |
|--------|---------|
| 批次划分 | **按分析运行时间分批**（每次 run_all_parallel.py = 一批） |
| urid 链接格式 | `{API_BASE_URL}/portal/zcm-devspace/spa/task/pc/{urId}`（用户提供样例） |
| 批注持久化 | **JSON 文件**（batches.json + annotations.json） |
| 帕累托 TopN | **全部展示**，按原因降序排列 + 累计占比线（用户自行看 Top3/Top5） |

## 3. 后端存储设计

### 3.1 批次数据模型（新增）

**`output/batches.json`** — 批次索引
```json
{
  "batches": [
    {
      "batch_id": "batch-20260826-152545",
      "name": "新电Singtel 2026.08 复盘",
      "created_at": "2026-08-26 15:25:45",
      "source": "all_analysis_20260826_152545.json",
      "urids": [11757372, 11757373, ...],
      "count": 181
    }
  ]
}
```

**`output/annotations.json`** — 批次批注
```json
{
  "annotations": {
    "batch-20260826-152545": [
      {"id": "a1", "text": "重点确认 security-001 违规", "created_at": "2026-08-26 16:00:00"}
    ]
  }
}
```

### 3.2 批次推断逻辑（`review_data.py` 新增）

**批次推断优先级**（明确）：
1. **`output/batches.json`**（显式批次，最高优先）
2. **`all_analysis_*.json` 文件名时间戳**（一次 `datetime.now()` 调用对应一次 `run_all_parallel.py` 完成，是最可靠的批次边界）
3. **孤儿 progress 归并**（见下）

**不使用 `progress_*.json` mtime 作为批次聚类依据**：progress 文件是每个 urId 完成时增量写入（mtime=单子完成时刻），非批次边界。实测 181 个 progress mtime 跨 43 分钟却只对应 2 个真实批次，且批次间 progress mtime 有重叠（如 `progress_11757373.json` mtime=15:25:39 属于批次2，但落在批次1 的 15:25:36-45 窗口内），纯 mtime 聚类会错误合并/拆分批次。

**孤儿 progress 处理**：若某 urid 在 `progress_*.json` 中存在但不在任何 `all_analysis_*.json` 中，归入"⚠️ 未归档"批次（UI 中单独显示并标注），不强行并入邻近批次。

**写入批次（`run_all_parallel.py`）**：
- 原子写：先写 `batches.json.tmp`，再 `os.replace` 重命名（Windows 原子操作）
- 读取时 try/except `json.JSONDecodeError`，损坏则回退到自动推断
- 写入前按 `batch_id` 去重（防同一分钟内多次运行产生重复 ID），或追加 UUID 后缀
- 批次记录含：batch_id、name、created_at、source 文件名、urids 清单、count

**批注清理**：加载 `annotations.json` 时过滤掉 batches.json 中不存在的 batch_id，避免孤儿批注。

### 3.3 研发云链接配置

- 在 `.env` 新增：`RDEV_DETAIL_URL_TEMPLATE=https://dev.iwhalecloud.com/portal/zcm-devspace/spa/task/pc/{urId}`
- 默认值兜底：`https://dev.iwhalecloud.com/portal/zcm-devspace/spa/task/pc/{urId}`
- `review_data.py` 提供 `build_detail_url(urid)` 生成链接（`{urId}` 占位符替换）
- 该模板独立于 `API_BASE_URL`（二者用途不同：API_BASE_URL 用于 API 调用，RDEV_DETAIL_URL_TEMPLATE 用于前端页面跳转），避免双源真相

## 4. 前端 UI 设计（streamlit_app.py 重构）

### 4.1 布局（需求1）

```
┌─────────────┬──────────────────────────────────────┐
│  左侧导览     │  右侧明细                              │
│             │                                      │
│ 📚 批次列表   │  ┌────────────────────────────────┐  │
│   ▸ batch-A  │  │ 📊 根因帕累托图（降序+累计线）      │  │
│   ▸ batch-B  │  └────────────────────────────────┘  │
│             │  ┌────────────────────────────────┐  │
│ ✏️ 批注       │  │ 🚨 规范违规分布（含条款内容）      │  │
│   + 添加批注  │  └────────────────────────────────┘  │
│             │  ┌────────────────────────────────┐  │
│ 📊 批次统计   │  │ 📑 缺陷明细（可筛选+联动）        │  │
│   缺陷数/根因  │  │    urId🔗 | 根因 | 条款 | ...   │  │
│             │  └────────────────────────────────┘  │
│             │  ┌────────────────────────────────┐  │
│             │  │ 🔍 单起缺陷详情（随明细联动）       │  │
│             │  └────────────────────────────────┘  │
└─────────────┴──────────────────────────────────────┘
```

- 用 `st.sidebar` 作为左侧导览
- 主区域 `st.columns` 或直接主区展示右侧内容

### 4.2 帕累托图（需求2）

- 用 Plotly 绘制组合图：柱状图（根因类型 × 缺陷数，**降序**）+ 折线（累计占比 %，副 y 轴 0-100%）
- **全部根因展示**（不截断 TopN），用户自行关注 Top3/Top5
- **数据准备顺序**（保证柱/线对齐）：
  ```python
  sorted_causes = summary_df.sort_values("缺陷数", ascending=False)
  x = sorted_causes["根因类型"].tolist()
  y_bars = sorted_causes["缺陷数"].tolist()
  y_cum = (sorted_causes["缺陷数"].cumsum() / sorted_causes["缺陷数"].sum() * 100).tolist()
  ```
- **点击柱状图某根因 → 联动过滤下方明细**（需求4）
- **点击事件处理**（`st.plotly_chart(fig, on_select="rerun", selection_mode=("points",))`）：
  ```python
  event = st.plotly_chart(fig, on_select="rerun", selection_mode=("points",), key="pareto")
  if event.selection.points:
      bar_trace_idx = 0  # bar 是第0个trace，scatter累计线是第1个
      bar_points = [p for p in event.selection.points if p["curve_number"] == bar_trace_idx]
      if bar_points:
          selected_cause = bar_points[0]["x"]  # 根因类型
  ```
- **累计线 trace 误点击过滤**：必须按 `curve_number == 0`（bar trace）过滤，忽略累计线选择
- **取消选择**：空选择（`points == []`）= 清空筛选 = 显示全部

### 4.3 规范违规分布（需求3）

- `build_violation_df` 增加 `条款内容`（rule_name）列
- 展示：`规范条款 | 条款内容 | 违规次数`
- **聚合规则**：按 `rule_id` 聚合，`rule_name` 取首次出现值，违规次数按 violation 实例计数（不去重）
- 规范条款点击 → 过滤明细为含该条款的缺陷

### 4.4 明细联动 + 筛选（需求4）

- **帕累托图点击联动**：选中某根因 → 明细过滤为该根因
- **违规分布点击联动**：选中某条款 → 明细过滤为含该条款的缺陷
- **手动筛选**：根因下拉、条款下拉、代码变更、仅看违规 checkbox、"隐藏无根因" checkbox
- 使用 `st.session_state` 保存选中状态（选中根因/条款/urId）
- **空选择 = 显示全部**

### 4.5 urid 链接（需求5）

- **方案 A（采用）**：`build_detail_df` 新增 `研发云链接` 列（URL 字符串），用 `column_config.LinkColumn` 渲染；urId 列保留 int 不动
- 或 **方案 B**：urId 列本身放 URL，配 `display_text=r".*pc/(\d+)"` 提取 urId 数字作显示文本
- **明确**：LinkColumn 的 cell 值必须是 URL 字符串，**不是** markdown（Streamlit 不在 dataframe 单元格渲染 markdown）
- `review_data.py` 提供 `build_detail_url(urid)` 生成 URL

### 4.6 单起详情联动（需求6）

- 明细表选中行：`st.dataframe(filtered, on_select="rerun", selection_mode="single-row", ...)`（**注意：是 `"single-row"`，不是 `"single"`**）
- 选中行取 urId：`selected_urid = filtered.iloc[event.selection.rows[0]]["urId"]`（`selection.rows` 是 integer position，用 `.iloc` 取）
- 用 `st.session_state` 保存选中 urId
- **限制**：Streamlit dataframe 选择状态**不可程序化设置**。当筛选变化导致选中 urId 不在新结果中时，详情区显示"已选缺陷不在当前筛选结果中，请清除筛选查看"，不强行高亮
- **空 dataframe**：筛选后无行时，详情区显示"请选择一行查看详情"，不报错

## 5. 技术选型

- **图表库**：优先 Plotly（`plotly`）— 支持交互式点击事件 + 组合图（柱+线），Streamlit 原生支持 `st.plotly_chart`。若项目未装 plotly 则评估替代。
- **状态管理**：`st.session_state`（选中批次/根因/条款/缺陷）
- **数据层**：`review_data.py` 扩展批次加载、链接生成、帕累托数据

## 6. 测试策略（TDD）

新增 `tests/ui/test_review_data.py`（数据层，重点）+ 重写 `tests/ui/test_streamlit_app.py`（匹配新 UI 结构）：

**数据层测试（test_review_data.py）**：

| 测试 | 覆盖 |
|------|------|
| `test_load_batches` | batches.json 加载 + 自动推断（all_analysis 时间戳） |
| `test_orphan_progress` | 孤儿 progress 归入"未归档"批次 |
| `test_build_summary_sorted` | 根因降序 + 累计占比计算 |
| `test_build_violation_with_content` | 违规分布含条款内容列（rule_id 聚合、rule_name 首次值） |
| `test_build_detail_url` | urid → 研发云链接（模板占位符替换） |
| `test_batches_atomic_write` | batches.json 原子写（tmp+rename）+ JSON 损坏回退 |

**UI 层测试（test_streamlit_app.py，重写匹配新结构）**：

| 测试 | 覆盖 |
|------|------|
| `test_render_with_batches` | UI 渲染批次导览（sidebar 批次列表） |
| `test_render_empty` | 无数据时显示提示 |
| `test_selection_mode_single_row` | 明细表用 `selection_mode="single-row"`（捕获 API 误用） |
| `test_linkcolumn_configured` | urId 链接用 LinkColumn（URL 字符串） |
| `test_pareto_curve_filter` | 帕累托点击按 curve_number==0 过滤（忽略累计线） |

**AppTest 真实渲染**：加 1-2 个 `streamlit.testing.v1.AppTest` 做真实渲染测试，能捕获 API 合约误用（如 `selection_mode="single"` 会抛异常）。

> 现有 4 个 UI 测试用 `@patch("st")` 全 mock，无法校验真实 Streamlit API 合约，需重写为新结构断言。

## 7. 兼容性

- 现有 `progress_*.json` 数据**不迁移**，通过批次推断兼容
- **批次推断结果**：当前 181 起 = 2 个真实批次（`all_analysis_20260826_152545` 5 起 + `all_analysis_20260826_154535` 163 起）+ 13 个孤儿归入"⚠️ 未归档"批次
- `output/复盘分析报告.xlsx` 生成逻辑不受影响（独立于 UI）
- Streamlit 启动命令不变（`python -m streamlit run src/ui/streamlit_app.py --server.port 8501`）

## 8. 交付物

- `src/ui/review_data.py`：批次加载、帕累托数据、链接生成、违规条款
- `src/ui/streamlit_app.py`：左右分栏、帕累托图、联动、筛选、详情联动
- `scripts/run_all_parallel.py`：完成后追加 batches.json
- `tests/ui/test_streamlit_app.py` + `tests/ui/test_review_data.py`
- `.env.example`：新增 RDEV_DETAIL_URL_TEMPLATE
