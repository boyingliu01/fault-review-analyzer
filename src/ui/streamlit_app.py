"""Streamlit 复盘分析界面 - 展示 AI 自主分析结果。

数据来源: output/progress_*.json（每起缺陷的分析结果）。
仅保留复盘结果展示，已移除 ChromaDB 向量存储链路。
"""

from __future__ import annotations

import streamlit as st
from loguru import logger

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

    def _render_review(self) -> None:
        """渲染复盘结果页面（展示分析结果，支持筛选与逐条验证）。"""
        st.title("📋 故障复盘结果")

        # 加载分析结果
        try:
            from src.ui.review_data import (
                build_detail_df,
                build_summary_df,
                build_violation_df,
                get_detail_by_urid,
                load_review_records,
            )

            recs = load_review_records()
            if not recs:
                st.warning("⚠️ 暂无复盘分析结果，请先运行分析（output/progress_*.json）")
                return

            st.caption(f"共加载 {len(recs)} 起缺陷分析结果")

            # 顶层统计
            summary_df = build_summary_df(recs)
            violation_df = build_violation_df(recs)
            detail_df = build_detail_df(recs)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("缺陷总数", len(recs))
            with col2:
                st.metric("根因类型数", len(summary_df))
            with col3:
                st.metric("规范违规总数", int(violation_df["违规次数"].sum()))
            with col4:
                with_code = sum(1 for r in recs.values() if r.get("has_code_change"))
                st.metric("有代码变更", with_code)

            # 根因分布
            st.markdown("---")
            st.subheader("📊 根因分布")
            st.bar_chart(summary_df.set_index("根因类型")["缺陷数"])

            # 规范违规分布
            st.markdown("---")
            st.subheader("🚨 规范违规分布")
            if not violation_df.empty:
                st.dataframe(violation_df, use_container_width=True)
            else:
                st.info("无规范违规记录")

            # 缺陷明细（可筛选）
            st.markdown("---")
            st.subheader("📑 缺陷明细")

            # 筛选控件
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            with filter_col1:
                cause_options = ["全部"] + sorted(detail_df["首要根因"].unique().tolist())
                selected_cause = st.selectbox("按根因类型筛选", cause_options)
            with filter_col2:
                code_options = ["全部", "是", "否"]
                selected_code = st.selectbox("按代码变更筛选", code_options)
            with filter_col3:
                violation_filter = st.checkbox("仅看有规范违规的")

            # 应用筛选
            filtered = detail_df
            if selected_cause != "全部":
                filtered = filtered[filtered["首要根因"] == selected_cause]
            if selected_code != "全部":
                filtered = filtered[filtered["有代码变更"] == selected_code]
            if violation_filter:
                filtered = filtered[filtered["违规数"] > 0]

            st.caption(f"筛选结果: {len(filtered)} 起")
            st.dataframe(filtered, use_container_width=True, height=400)

            # 单起详情
            st.markdown("---")
            st.subheader("🔍 单起缺陷详情")
            urid_input = st.selectbox(
                "选择缺陷单号查看详情",
                options=sorted(recs.keys()),
                format_func=lambda u: f"{u}: {recs[u].get('title', '')[:50]}",
            )
            if urid_input:
                detail = get_detail_by_urid(recs, urid_input)
                st.markdown(f"### {detail.get('title', '')}")
                st.markdown(f"**urId**: {urid_input}")

                # 根因
                st.markdown("#### 根因分析")
                for rc in detail.get("root_causes", []):
                    st.markdown(
                        f"- **[{rc.get('cause_type','')}]** (置信度 {rc.get('confidence',0):.2f}): "
                        f"{rc.get('description','')}"
                    )
                    if rc.get("evidence"):
                        st.caption("证据: " + "; ".join(str(e)[:100] for e in rc["evidence"][:3]))

                # 规范违规
                st.markdown("#### 规范违规")
                if detail.get("violations"):
                    for v in detail["violations"]:
                        st.markdown(
                            f"- **{v.get('rule_id','')}**: {v.get('rule_name','')} "
                            f"(严重度: {v.get('severity','')})"
                        )
                else:
                    st.info("无规范违规")

                # 改进建议
                st.markdown("#### 改进建议")
                for imp in detail.get("improvements", []):
                    st.markdown(
                        f"- **[{'🔴高' if imp.get('priority')=='high' else '🟡中' if imp.get('priority')=='medium' else '🟢低'}] "
                        f"{imp.get('measure','')}**"
                    )
                    if imp.get("acceptance_criteria"):
                        st.caption(f"验收标准: {imp['acceptance_criteria']}")
                    if imp.get("rule_ids"):
                        st.caption(f"关联规范: {', '.join(imp['rule_ids'])}")

        except Exception as e:
            st.error(f"加载复盘结果失败: {e}")
            logger.error(f"复盘结果加载失败: {e}")


def main() -> None:
    """主入口"""
    ui = FaultAnalysisUI()
    ui.run()


if __name__ == "__main__":
    main()
