"""Streamlit 复盘分析界面 - 展示 AI 自主分析结果，支持批次隔离、帕累托图、明细联动。

数据来源: output/progress_*.json（每起缺陷的分析结果）+ output/batches.json（批次索引）
功能:
- 左侧批次导览（批次列表 + 批注 + 统计）
- 右侧帕累托图（根因降序 + 累计占比线）
- 规范违规分布（含条款内容）
- 缺陷明细（研发云链接 + 筛选 + 联动）
- 单起缺陷详情（随明细选中联动）
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
from loguru import logger
from plotly import graph_objects as go

from src.ui.review_data import (
    add_annotation,
    build_detail_df,
    build_detail_url,
    build_summary_df,
    build_violation_df,
    get_detail_by_urid,
    load_annotations,
    load_batches,
    load_review_records,
)

# 配置页面
st.set_page_config(
    page_title="故障复盘分析系统",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


class FaultAnalysisUI:
    """复盘分析 UI 主类"""

    def run(self) -> None:
        """运行应用"""
        self._render_review()

    # ------------------------------------------------------------------
    # 左侧导览
    # ------------------------------------------------------------------
    def _render_sidebar(self, batches: list[dict], annotations: dict) -> str | None:
        """渲染左侧批次导览，返回选中的 batch_id（None 表示全部缺陷）。"""
        st.sidebar.header("📚 批次导览")

        if not batches:
            st.sidebar.info("暂无批次")
            return None

        # 顶部提供全量聚合视图
        # 按 urid 去重后的真实总数（跨批次可能有重叠）
        all_urids = {u for b in batches for u in (b.get("urids") or [])}
        real_total = len(all_urids)

        batch_options = {f"⭐ 全部缺陷（{real_total}起）": ""}
        batch_options.update({f"{b['name']}（{b['count']}起）": b["batch_id"] for b in batches})
        selected_label = st.sidebar.selectbox(
            "选择范围",
            options=list(batch_options.keys()),
            index=0,
            key="batch_selector",
        )
        selected_batch_id = str(batch_options[selected_label]) or None

        # 当前批次批注
        st.sidebar.markdown("---")
        st.sidebar.subheader("✏️ 批注")
        if selected_batch_id is None:
            st.sidebar.caption("选择具体批次后可添加批注")
        else:
            batch_anns = annotations.get(selected_batch_id, [])
            if batch_anns:
                for ann in batch_anns:
                    st.sidebar.markdown(f"- {ann.get('text', '')}")
                    st.sidebar.caption(ann.get("created_at", ""))
            else:
                st.sidebar.caption("暂无批注")

            new_ann = st.sidebar.text_input("添加批注", key="new_annotation")
            if st.sidebar.button("保存批注", key="save_annotation") and new_ann.strip():
                add_annotation(selected_batch_id, new_ann.strip())
                st.sidebar.success("批注已保存")
                st.rerun()

        # 批次统计
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 批次统计")
        if selected_batch_id is None:
            st.sidebar.metric("缺陷数", real_total)
        else:
            st.sidebar.metric("缺陷数", self._batch_count(batches, selected_batch_id))

        return selected_batch_id

    @staticmethod
    def _batch_count(batches: list[dict], batch_id: str) -> int:
        """获取指定批次的缺陷数。"""
        for b in batches:
            if b["batch_id"] == batch_id:
                return int(b.get("count") or len(b.get("urids") or []))
        return 0

    # ------------------------------------------------------------------
    # 右侧明细
    # ------------------------------------------------------------------
    def _render_review(self) -> None:
        """渲染复盘结果页面（左侧批次导览 + 右侧明细）。"""
        st.title("📋 故障复盘结果")

        try:
            recs = load_review_records()
            if not recs:
                st.warning("⚠️ 暂无复盘分析结果，请先运行分析（output/progress_*.json）")
                return

            batches = load_batches()
            annotations = load_annotations()

            # 左侧批次导览
            selected_batch_id = self._render_sidebar(batches, annotations)

            # 当前批次的记录
            batch_recs = self._filter_records_by_batch(recs, batches, selected_batch_id)
            if not batch_recs:
                st.info("该批次暂无缺陷记录")
                return

            scope_label = (
                f"⭐ 全部缺陷（{len(batch_recs)} 起，跨批次聚合）"
                if selected_batch_id is None
                else f"当前批次: {self._batch_name(batches, selected_batch_id)} · 共 {len(batch_recs)} 起"
            )
            st.caption(scope_label)

            # 顶层统计
            summary_df = build_summary_df(batch_recs)
            violation_df = build_violation_df(batch_recs)
            detail_df = build_detail_df(batch_recs)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("缺陷总数", len(batch_recs))
            with col2:
                st.metric("根因类型数", len(summary_df))
            with col3:
                st.metric(
                    "规范违规总数",
                    int(violation_df["违规次数"].sum()) if not violation_df.empty else 0,
                )
            with col4:
                with_code = sum(1 for r in batch_recs.values() if r.get("has_code_change"))
                st.metric("有代码变更", with_code)

            # 帕累托图
            st.markdown("---")
            st.subheader("📊 根因帕累托图")
            pareto_event = self._render_pareto_chart(summary_df)

            # 规范违规分布
            st.markdown("---")
            st.subheader("🚨 规范违规分布")
            violation_event = self._render_violation_table(violation_df)

            # 缺陷明细（可筛选 + 联动）
            st.markdown("---")
            st.subheader("📑 缺陷明细")
            filtered, selection = self._render_detail_table(
                detail_df, pareto_event, violation_event, violation_df
            )

            # 单起详情（联动）
            st.markdown("---")
            st.subheader("🔍 单起缺陷详情")
            self._render_single_detail(batch_recs, filtered, selection)

        except Exception as e:
            st.error(f"加载复盘结果失败: {e}")
            logger.error(f"复盘结果加载失败: {e}")

    # ------------------------------------------------------------------
    # 批次过滤
    # ------------------------------------------------------------------
    @staticmethod
    def _batch_name(batches: list[dict], batch_id: str | None) -> str:
        """获取批次名称。"""
        if not batch_id:
            return "全部"
        for b in batches:
            if b["batch_id"] == batch_id:
                return str(b.get("name") or batch_id)
        return batch_id

    @staticmethod
    def _filter_records_by_batch(
        recs: dict[int, dict], batches: list[dict], batch_id: str | None
    ) -> dict[int, dict]:
        """按批次过滤记录。batch_id 为 None 时返回全部。"""
        if not batch_id:
            return recs
        batch_urids = set()
        for b in batches:
            if b["batch_id"] == batch_id:
                batch_urids = set(b.get("urids", []))
                break
        if not batch_urids:
            return recs
        return {u: r for u, r in recs.items() if u in batch_urids}

    # ------------------------------------------------------------------
    # 帕累托图
    # ------------------------------------------------------------------
    @staticmethod
    def _render_pareto_chart(summary_df: pd.DataFrame) -> object:
        """渲染帕累托图（根因降序柱状 + 累计占比线），返回选择事件。"""
        if summary_df.empty:
            st.info("暂无根因数据")
            return None

        fig = go.Figure()
        # 柱状图（降序）
        fig.add_trace(
            go.Bar(
                x=summary_df["根因类型"],
                y=summary_df["缺陷数"],
                name="缺陷数",
                marker_color="#4C78A8",
            )
        )
        # 累计占比线（副 y 轴）
        fig.add_trace(
            go.Scatter(
                x=summary_df["根因类型"],
                y=summary_df["累计占比(%)"],
                name="累计占比(%)",
                yaxis="y2",
                mode="lines+markers",
                line={"color": "#E45756", "width": 2},
            )
        )
        fig.update_layout(
            yaxis={"title": "缺陷数"},
            yaxis2={"title": "累计占比(%)", "overlaying": "y", "side": "right", "range": [0, 100]},
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
            height=400,
        )
        return st.plotly_chart(
            fig,
            width="stretch",
            on_select="rerun",
            selection_mode=("points",),
            key="pareto_chart",
        )

    # ------------------------------------------------------------------
    # 规范违规分布
    # ------------------------------------------------------------------
    @staticmethod
    def _render_violation_table(violation_df: pd.DataFrame) -> object:
        """渲染规范违规分布（含条款内容），返回选择事件（用于联动过滤明细）。"""
        if violation_df.empty:
            st.info("无规范违规记录")
            return None

        return st.dataframe(
            violation_df,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="violation_table",
        )

    # ------------------------------------------------------------------
    # 缺陷明细（联动 + 筛选）
    # ------------------------------------------------------------------
    def _render_detail_table(
        self,
        detail_df: pd.DataFrame,
        pareto_event: object,
        violation_event: object = None,
        violation_df: pd.DataFrame | None = None,
    ) -> tuple[pd.DataFrame, object]:
        """渲染缺陷明细表（含筛选 + 联动 + 研发云链接），返回过滤后表和选择事件。

        联动来源：帕累托图选中根因 → 根因筛选；规范违规分布选中条款 →
        规范条款筛选（再次点击违规分布同一行取消选择即恢复"全部"）。
        """
        # 从帕累托图联动获取选中根因
        selected_cause = self._pareto_selected_cause(pareto_event)
        # 从规范违规分布联动获取选中条款
        selected_rule = self._violation_selected_rule(violation_event, violation_df)
        if selected_rule:
            st.caption(
                f"已联动规范违规分布选中条款: **{selected_rule}**（点击该行取消选择可恢复全部）"
            )

        # 筛选控件
        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
        with filter_col1:
            cause_options = ["全部"] + sorted(detail_df["首要根因"].unique().tolist())
            default_cause = selected_cause if selected_cause in cause_options else "全部"
            cause_sel = st.selectbox(
                "按根因筛选",
                cause_options,
                index=cause_options.index(default_cause),
                key="cause_filter",
            )
        with filter_col2:
            rule_options = ["全部"] + sorted(
                detail_df["规范违规"].str.split("; ").explode().unique().tolist()
                if not detail_df.empty
                else []
            )
            default_rule = selected_rule if selected_rule in rule_options else "全部"
            rule_sel = st.selectbox(
                "按规范条款筛选",
                rule_options,
                index=rule_options.index(default_rule),
                key="rule_filter",
            )
        with filter_col3:
            code_options = ["全部", "是", "否"]
            code_sel = st.selectbox("按代码变更筛选", code_options, key="code_filter")
        with filter_col4:
            only_violation = st.checkbox("仅看有违规的", key="only_violation")
            hide_no_cause = st.checkbox("隐藏无根因", key="hide_no_cause")

        # 应用筛选
        mask = pd.Series(True, index=detail_df.index)
        if cause_sel != "全部":
            mask &= detail_df["首要根因"] == cause_sel
        if rule_sel != "全部":
            mask &= detail_df["规范违规"].str.contains(rule_sel, na=False)
        if code_sel != "全部":
            mask &= detail_df["有代码变更"] == code_sel
        if only_violation:
            mask &= detail_df["违规数"] > 0
        if hide_no_cause:
            mask &= detail_df["首要根因"] != "无根因"
        filtered: pd.DataFrame = detail_df.loc[mask]

        st.caption(f"筛选结果: {len(filtered)} 起")

        if filtered.empty:
            st.info("无匹配记录")
            return filtered, None

        # 明细表：研发云链接用 LinkColumn，单行选择用于联动详情
        column_config = {
            "urId": st.column_config.NumberColumn("urId", width="small"),
            "研发云链接": st.column_config.LinkColumn(
                "研发云链接", display_text="查看", width="small"
            ),
        }
        selection = st.dataframe(
            filtered,
            width="stretch",
            height=400,
            hide_index=True,
            column_config=column_config,
            on_select="rerun",
            selection_mode="single-row",
            key="detail_table",
        )
        return filtered, selection

    @staticmethod
    def _pareto_selected_cause(pareto_event: Any) -> str | None:
        """从帕累托图选择事件提取选中的根因类型（curve_number==0 过滤）。"""
        if not pareto_event or not pareto_event.selection:
            return None
        selection = pareto_event.selection
        points = selection.get("points", []) if hasattr(selection, "get") else []
        bar_points = [p for p in points if p.get("curve_number", 0) == 0]
        if bar_points:
            return str(bar_points[0].get("x"))
        return None

    @staticmethod
    def _violation_selected_rule(
        violation_event: Any, violation_df: pd.DataFrame | None
    ) -> str | None:
        """从规范违规分布表选择事件提取选中的条款 ID（规范条款列）。"""
        if violation_event is None or violation_df is None:
            return None
        if not getattr(violation_event, "selection", None):
            return None
        sel = violation_event.selection
        rows = sel.get("rows", []) if hasattr(sel, "get") else []
        if not rows:
            return None
        try:
            return str(violation_df.iloc[rows[0]]["规范条款"])
        except (IndexError, KeyError, ValueError):
            return None

    # ------------------------------------------------------------------
    # 单起详情（联动）
    # ------------------------------------------------------------------
    def _render_single_detail(
        self, recs: dict[int, dict], filtered: pd.DataFrame, selection: object
    ) -> None:
        """渲染单起缺陷详情，随明细选中联动。"""
        selected_urid = self._get_selected_urid(filtered, selection)

        if selected_urid is None:
            st.info("请在上方缺陷明细表中选择一行查看详情")
            return

        if selected_urid not in recs:
            st.info("已选缺陷不在当前筛选结果中，请清除筛选查看")
            return

        detail = get_detail_by_urid(recs, selected_urid)
        st.markdown(f"### {detail.get('title', '')}")
        st.markdown(f"**urId**: [{selected_urid}]({build_detail_url(selected_urid)})")

        # 根因
        st.markdown("#### 根因分析")
        for rc in detail.get("root_causes", []):
            st.markdown(f"- **[{rc.get('cause_type', '')}]** {rc.get('description', '')}")
            if rc.get("evidence"):
                st.caption("证据: " + "; ".join(str(e)[:100] for e in rc["evidence"][:3]))

        # 规范违规
        st.markdown("#### 规范违规")
        if detail.get("violations"):
            for v in detail["violations"]:
                st.markdown(
                    f"- **{v.get('rule_id', '')}**: {v.get('rule_name', '')} "
                    f"(严重度: {v.get('severity', '')})"
                )
                if v.get("justification"):
                    st.caption(f"认定说明: {v['justification']}")
        else:
            st.info("无规范违规")

        # 违规认定复核记录（人工/程序复核的审计线索，有记录时展示）
        review = detail.get("violation_review") or {}
        if isinstance(review, dict) and review:
            with st.expander("🧾 违规认定复核记录", expanded=False):
                st.caption(
                    f"复核时间: {review.get('reviewed_at', '')} ｜ 复核方: {review.get('reviewer', '')}"
                )
                if review.get("scope"):
                    st.caption(f"核查范围: {review['scope']}")
                if review.get("method"):
                    st.caption(f"复核方法: {review['method']}")
                if review.get("conclusion"):
                    st.markdown(f"**结论**: {review['conclusion']}")
                for item in review.get("items", []) or []:
                    st.markdown(
                        f"- **[{item.get('rule_id', '')}] {item.get('rule_name', '')}**"
                        f" — 处置: {item.get('disposition', '')}"
                    )
                    orig_ev = item.get("original_evidence") or []
                    if orig_ev:
                        st.caption("原证据: " + " ｜ ".join(str(e)[:120] for e in orig_ev[:3]))
                    if item.get("reason"):
                        st.caption(f"认定说明: {item['reason']}")

        # Delphi 复审记录（多专家匿名共识裁决，固化于复盘引擎）
        delphi = detail.get("delphi_review") or {}
        if isinstance(delphi, dict) and delphi.get("items"):
            with st.expander("⚖️ 违规 Delphi 复审（多专家共识）", expanded=False):
                st.caption(
                    f"复审时间: {delphi.get('reviewed_at', '')} ｜ 方法: "
                    f"{delphi.get('method', '')} ｜ 专家: "
                    f"{', '.join(delphi.get('reviewers', []))}（独立匿名会话）"
                )
                VERDICT_CN = {
                    "violation": "违规成立",
                    "false_positive": "误报（撤销）",
                    "insufficient_evidence": "证据不足（撤销）",
                    "diverged": "专家分歧（待人工裁决）",
                }
                for item in delphi.get("items", []) or []:
                    verdict = item.get("final_verdict", "")
                    st.markdown(
                        f"- **[{item.get('rule_id', '')}]** → "
                        f"**{VERDICT_CN.get(verdict, verdict)}**"
                        f"（共识: {'是' if item.get('consensus') else '否'}，"
                        f"{item.get('rounds', '')}轮）"
                    )
                    if item.get("reason"):
                        st.caption(f"裁决理由: {item['reason']}")
                    for op in item.get("opinions", []) or []:
                        st.caption(
                            f"　· 专家[{op.get('reviewer', '')}] R{op.get('round', '')}: "
                            f"{VERDICT_CN.get(op.get('verdict', ''), op.get('verdict', ''))}"
                            f" — {str(op.get('reason', ''))[:120]}"
                        )
                manual = delphi.get("manual_review") or {}
                if manual:
                    st.caption(f"人工核查: {manual.get('reviewer', '')}")
                    for m in manual.get("items", []) or []:
                        st.caption(f"　· [{m.get('rule_id', '')}] {m.get('reason', '')}")

        # 改进建议
        st.markdown("#### 改进建议")
        for imp in detail.get("improvements", []):
            st.markdown(
                f"- **[{'🔴高' if imp.get('priority') == 'high' else '🟡中' if imp.get('priority') == 'medium' else '🟢低'}] "
                f"{imp.get('measure', '')}**"
            )
            if imp.get("acceptance_criteria"):
                st.caption(f"验收标准: {imp['acceptance_criteria']}")
            if imp.get("rule_ids"):
                st.caption(f"关联规范: {', '.join(imp['rule_ids'])}")

        # 深度根因分析（5 层追问）
        deep = detail.get("deep_root_causes") or {}
        if deep:
            st.markdown("#### 深度根因分析（5层追问）")
            meta_bits = []
            if deep.get("problem_category"):
                meta_bits.append(f"问题分类: **{deep['problem_category']}**")
            if deep.get("initial_cause"):
                meta_bits.append(f"初步归因: {deep['initial_cause']}")
            if meta_bits:
                st.markdown(" · ".join(meta_bits))
            for rc in deep.get("deep_root_causes", []):
                title_head = str(rc.get("root_cause", ""))[:60]
                with st.expander(f"[{rc.get('layer', '')}] {title_head}"):
                    st.markdown(f"**为什么**: {rc.get('why_reason', '')}")
                    st.caption(f"证据: {rc.get('evidence', '')}")
            acts = deep.get("actionable_improvements") or []
            if acts:
                st.markdown("**可落地改进行动:**")
                for a in acts:
                    st.markdown(
                        f"- [{a.get('priority', '')}] ({a.get('type', '')} → 责任方: {a.get('owner', '')}) "
                        f"{a.get('action', '')}"
                    )
            checks = deep.get("checklist_recommendations") or []
            if checks:
                st.caption("Checklist 建议: " + " ｜ ".join(str(c) for c in checks[:6]))

            # 需求-测试传导链例行检查结论（旧数据无此字段时隐藏）
            req_check = deep.get("requirement_check") or {}
            if isinstance(req_check, dict) and req_check:
                st.markdown("**需求-测试传导链例行检查:**")
                st.markdown(
                    f"- 需求源头规则定义: **{req_check.get('rule_defined_in_requirement', '证据不足')}**"
                    f" ｜ 测试覆盖: **{req_check.get('test_covered', '证据不足')}**"
                )
                conclusion = str(req_check.get("conclusion", "")).strip()
                if conclusion:
                    st.caption(conclusion)

        # 图片证据（截图提取内容）
        img_ev = detail.get("image_evidence")
        if img_ev:
            with st.expander("📷 图片证据（截图提取内容）", expanded=False):
                st.text(str(img_ev)[:4000])

    @staticmethod
    def _get_selected_urid(filtered: pd.DataFrame, selection: Any) -> int | None:
        """从明细表选择事件提取选中的 urId。"""
        if selection is None or not getattr(selection, "selection", None):
            return None
        sel = selection.selection
        rows = sel.get("rows", []) if hasattr(sel, "get") else []
        if not rows:
            return None
        try:
            return int(filtered.iloc[rows[0]]["urId"])
        except (IndexError, KeyError, ValueError):
            return None


def main() -> None:
    """主入口"""
    ui = FaultAnalysisUI()
    ui.run()


if __name__ == "__main__":
    main()
