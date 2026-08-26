"""Streamlit 交互式故障分析界面"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
from loguru import logger

from src.analysis.clustering import ClusteringAnalyzer
from src.analysis.improvement_recommender import ImprovementRecommender
from src.storage.chroma_manager import ChromaManager
from src.visualization.charts import DashboardGenerator
from src.visualization.cluster_scatter import ClusterScatterVisualizer

# 配置页面
st.set_page_config(
    page_title="故障聚类分析系统",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


class FaultAnalysisUI:
    """故障分析 UI 主类"""

    def __init__(self) -> None:
        self.chroma_manager = ChromaManager()
        self.clustering_analyzer = ClusteringAnalyzer()
        self.improvement_recommender = ImprovementRecommender()
        self.dashboard_generator = DashboardGenerator()

    def run(self) -> None:
        """运行应用"""
        self._render_sidebar()
        self._render_main_content()

    def _render_sidebar(self) -> None:
        """渲染侧边栏"""
        with st.sidebar:
            st.title("🔧 故障聚类分析")
            st.markdown("---")

            # 导航菜单
            page = st.radio(
                "功能选择",
                [
                    "📊 数据概览",
                    "📋 复盘结果",
                    "🔍 相似故障查询",
                    "📈 聚类分析",
                    "📉 可视化图表",
                    "💡 改进措施",
                ],
            )

            st.session_state["page"] = page

            st.markdown("---")
            st.markdown("### 系统状态")

            # 显示向量数据库状态
            try:
                collection = self.chroma_manager.get_or_create_collection()
                count = collection.count()
                st.success(f"✅ 向量数据库: {count} 条记录")
            except Exception as e:
                st.error(f"❌ 向量数据库连接失败: {e}")
                logger.error(f"向量数据库连接失败: {e}")

    def _render_main_content(self) -> None:
        """渲染主内容区"""
        page = st.session_state.get("page", "📊 数据概览")

        if page == "📊 数据概览":
            self._render_overview()
        elif page == "📋 复盘结果":
            self._render_review()
        elif page == "🔍 相似故障查询":
            self._render_similarity_search()
        elif page == "📈 聚类分析":
            self._render_clustering()
        elif page == "📉 可视化图表":
            self._render_visualization()
        elif page == "💡 改进措施":
            self._render_improvements()

    def _render_overview(self) -> None:
        """渲染数据概览页面"""
        st.title("📊 数据概览")

        try:
            # 加载所有数据
            embeddings, metadatas = self._load_all_embeddings()

            if embeddings is None or len(embeddings) == 0:
                st.warning("⚠️ 暂无数据，请先运行阶段一数据准备")
                return

            # 统计信息
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("故障单总数", len(embeddings))

            with col2:
                violation_count = sum(1 for m in metadatas if m.get("is_violation", False))
                st.metric("违规故障数", violation_count)

            with col3:
                unique_phases = len({m.get("introduce_phase", "未知") for m in metadatas})
                st.metric("引入阶段数", unique_phases)

            with col4:
                st.metric("向量维度", len(embeddings[0]) if embeddings else 0)

            # 数据表格
            st.markdown("---")
            st.subheader("故障单列表")

            df_data = []
            for i, meta in enumerate(metadatas):
                df_data.append(
                    {
                        "序号": i + 1,
                        "任务单号": meta.get("task_id", "未知"),
                        "引入阶段": meta.get("introduce_phase", "未知"),
                        "是否违规": "是" if meta.get("is_violation", False) else "否",
                        "违规类型": meta.get("violation_type", "无"),
                        "根因": meta.get("root_cause", "")[:50] + "..."
                        if len(meta.get("root_cause", "")) > 50
                        else meta.get("root_cause", ""),
                    }
                )

            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"加载数据失败: {e}")
            logger.error(f"数据概览加载失败: {e}")

    def _render_review(self) -> None:
        """渲染复盘结果页面（展示 181 起分析结果，支持筛选与逐条验证）。"""
        st.title("📋 复盘结果")

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

    def _render_similarity_search(self) -> None:
        """渲染相似故障查询页面"""
        st.title("🔍 相似故障查询")

        # 输入任务单号
        task_id = st.text_input(
            "输入任务单号",
            placeholder="例如: TASK-001",
            help="输入要查询的任务单号，系统将查找相似的故障",
        )

        if not task_id:
            st.info("👆 请输入任务单号开始查询")
            return

        # 相似度阈值
        threshold = st.slider(
            "相似度阈值",
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.05,
            help="只显示相似度高于此阈值的故障",
        )

        # 最大结果数
        top_k = st.slider(
            "最大结果数",
            min_value=1,
            max_value=20,
            value=5,
            help="最多显示多少个相似故障",
        )

        if st.button("🔍 查询相似故障", type="primary"):
            with st.spinner("正在查询..."):
                try:
                    results = self.chroma_manager.query_similar(
                        query_text=task_id,
                        n_results=top_k + 1,  # 包含自身
                    )

                    if not results:
                        st.warning("未找到相似故障")
                        return

                    # 过滤并显示结果
                    st.markdown("---")
                    st.subheader(f"与 {task_id} 相似的故障")

                    for result in results:
                        # 跳过自身（Chroma 返回字段为 "id"）
                        if result.get("id") == task_id:
                            continue

                        # Chroma 返回 "distance"（越小越相似），转换为相似度
                        similarity = 1.0 - result.get("distance", 1.0)
                        if similarity < threshold:
                            continue

                        with st.expander(
                            f"📋 {result.get('id', '未知')} (相似度: {similarity:.2%})"
                        ):
                            meta = result.get("metadata", {})

                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**引入阶段**: {meta.get('introduce_phase', '未知')}")
                                st.markdown(
                                    f"**是否违规**: {'是' if meta.get('is_violation') else '否'}"
                                )
                            with col2:
                                st.markdown(f"**违规类型**: {meta.get('violation_type', '无')}")

                            st.markdown("**根因分析**:")
                            st.text(meta.get("root_cause", "暂无"))

                            st.markdown("**改进措施**:")
                            st.text(meta.get("improvement_measure", "暂无"))

                except Exception as e:
                    st.error(f"查询失败: {e}")
                    logger.error(f"相似故障查询失败: {e}")

    def _render_clustering(self) -> None:
        """渲染聚类分析页面"""
        st.title("📈 聚类分析")

        # 聚类算法选择
        algorithm = st.selectbox(
            "选择聚类算法",
            ["hdbscan", "kmeans", "hierarchical"],
            help="HDBSCAN 适合发现任意形状的簇，K-Means 适合球形簇",
        )

        # 算法参数
        col1, col2 = st.columns(2)

        with col1:
            if algorithm == "hdbscan":
                min_cluster_size = st.number_input(
                    "最小簇大小",
                    min_value=2,
                    max_value=20,
                    value=3,
                )
                min_samples = st.number_input(
                    "最小样本数",
                    min_value=1,
                    max_value=10,
                    value=2,
                )
            elif algorithm == "kmeans":
                n_clusters = st.number_input(
                    "簇数量",
                    min_value=2,
                    max_value=20,
                    value=5,
                )
            else:  # hierarchical
                n_clusters = st.number_input(
                    "簇数量",
                    min_value=2,
                    max_value=20,
                    value=5,
                )

        with col2:
            st.markdown("### 参数说明")
            if algorithm == "hdbscan":
                st.markdown("- **最小簇大小**: 形成一个簇所需的最少样本数")
                st.markdown("- **最小样本数**: 核心点的邻域样本数")
            else:
                st.markdown("- **簇数量**: 期望分成的簇的数量")

        if st.button("🚀 运行聚类分析", type="primary"):
            with st.spinner("正在运行聚类分析..."):
                try:
                    # 加载数据
                    embeddings, metadatas = self._load_all_embeddings()

                    if embeddings is None or len(embeddings) == 0:
                        st.warning("⚠️ 暂无数据，请先运行阶段一数据准备")
                        return

                    # 运行聚类
                    if algorithm == "hdbscan":
                        result = self.clustering_analyzer.cluster_hdbscan(
                            embeddings,
                            min_cluster_size=min_cluster_size,
                            min_samples=min_samples,
                        )
                    elif algorithm == "kmeans":
                        result = self.clustering_analyzer.cluster_kmeans(
                            embeddings,
                            n_clusters=n_clusters,
                        )
                    else:
                        result = self.clustering_analyzer.cluster_hierarchical(
                            embeddings,
                            n_clusters=n_clusters,
                        )

                    # 显示结果
                    st.markdown("---")
                    st.subheader("聚类结果")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("簇数量", result.n_clusters)
                    with col2:
                        st.metric("噪声点", result.n_noise)
                    with col3:
                        coverage = (
                            (len(embeddings) - result.n_noise) / len(embeddings) * 100
                            if embeddings
                            else 0
                        )
                        st.metric("覆盖率", f"{coverage:.1f}%")

                    # 显示每个簇的信息
                    st.markdown("---")
                    st.subheader("簇详情")

                    for cluster_id in sorted(set(result.labels)):
                        if cluster_id == -1:
                            continue  # 跳过噪声

                        # 获取该簇的样本
                        indices = [
                            i for i, label in enumerate(result.labels) if label == cluster_id
                        ]

                        with st.expander(f"🔸 簇 {cluster_id} ({len(indices)} 个样本)"):
                            for idx in indices:
                                meta = metadatas[idx]
                                st.markdown(
                                    f"- **{meta.get('task_id', '未知')}**: {meta.get('root_cause', '暂无根因')[:50]}..."
                                )

                    # 保存结果到 session state
                    st.session_state["clustering_result"] = result
                    st.session_state["clustering_metadatas"] = metadatas

                    st.success("✅ 聚类分析完成！")

                except Exception as e:
                    st.error(f"聚类分析失败: {e}")
                    logger.error(f"聚类分析失败: {e}")

    def _render_visualization(self) -> None:
        """渲染可视化图表页面"""
        st.title("📉 可视化图表")

        # 检查是否有聚类结果
        if "clustering_result" not in st.session_state:
            st.warning("⚠️ 请先运行聚类分析")
            return

        result = st.session_state["clustering_result"]
        metadatas = st.session_state["clustering_metadatas"]

        # 加载嵌入向量
        embeddings, _ = self._load_all_embeddings()

        # 生成可视化
        st.markdown("---")
        st.subheader("聚类散点图")

        try:
            visualizer = ClusterScatterVisualizer()
            prepared_data = visualizer.prepare_data(
                embeddings=embeddings,
                labels=result.labels,
                task_ids=[m.get("task_id", f"TASK-{i}") for i, m in enumerate(metadatas)],
                metadata=metadatas,
            )

            fig = visualizer.create_figure(
                prepared_data,
                title="故障聚类散点图 (UMAP 降维)",
            )

            if fig is None:
                st.error("散点图生成失败，请查看日志")
                return

            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"生成散点图失败: {e}")
            logger.error(f"散点图生成失败: {e}")

        # 生成其他图表
        st.markdown("---")
        st.subheader("统计图表")

        col1, col2 = st.columns(2)

        with col1:
            # 根因分布
            root_causes: dict[str, int] = {}
            for meta in metadatas:
                cause = meta.get("root_cause", "未知")
                # 简化根因名称
                short_cause = cause[:20] + "..." if len(cause) > 20 else cause
                root_causes[short_cause] = root_causes.get(short_cause, 0) + 1

            if root_causes:
                self.dashboard_generator.root_cause_chart.create_bar_chart(
                    dict(sorted(root_causes.items(), key=lambda x: x[1], reverse=True)[:10]),
                    title="Top 10 根因分布",
                )
                st.info("📊 根因分布图已生成")

        with col2:
            # 违规类型分布
            violations: dict[str, int] = {}
            for meta in metadatas:
                if meta.get("is_violation"):
                    vtype = meta.get("violation_type", "未分类")
                    violations[vtype] = violations.get(vtype, 0) + 1

            if violations:
                self.dashboard_generator.violation_chart.create_pie_chart(
                    violations,
                    title="违规类型分布",
                )
                st.info("🥧 违规类型分布图已生成")

    def _render_improvements(self) -> None:
        """渲染改进措施页面"""
        st.title("💡 改进措施")

        # 加载数据
        try:
            embeddings, metadatas = self._load_all_embeddings()

            if not metadatas:
                st.warning("⚠️ 暂无数据")
                return

            # 提取根因
            root_causes = []
            violation_causes = []

            for meta in metadatas:
                cause = meta.get("root_cause", "")
                if cause:
                    root_causes.append(cause)
                    if meta.get("is_violation"):
                        violation_causes.append(cause)

            # 生成改进措施
            measures = self.improvement_recommender.recommend_measures(
                root_causes,
                violation_causes=violation_causes,
                top_n=10,
            )

            if not measures:
                st.warning("暂无改进措施建议")
                return

            # 显示统计
            st.markdown("---")
            col1, col2, col3 = st.columns(3)

            high_count = sum(1 for m in measures if m.priority == "high")
            medium_count = sum(1 for m in measures if m.priority == "medium")
            low_count = sum(1 for m in measures if m.priority == "low")

            with col1:
                st.metric("🔴 高优先级", high_count)
            with col2:
                st.metric("🟡 中优先级", medium_count)
            with col3:
                st.metric("🟢 低优先级", low_count)

            # 显示改进措施列表
            st.markdown("---")
            st.subheader("改进措施列表")

            priority_colors = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢",
            }

            for i, measure in enumerate(measures, 1):
                color = priority_colors.get(measure.priority, "⚪")

                with st.expander(f"{color} {i}. {measure.root_cause}"):
                    st.markdown(f"**改进措施**: {measure.measure}")
                    st.markdown(f"**验收标准**: {measure.acceptance_criteria}")
                    st.markdown(f"**预期影响**: {measure.expected_impact}")
                    if measure.category:
                        st.markdown(f"**类别**: {measure.category}")

            # 导出报告
            st.markdown("---")
            if st.button("📥 导出改进措施报告"):
                report = self.improvement_recommender.generate_report(measures)
                st.download_button(
                    label="下载 Markdown 报告",
                    data=report,
                    file_name="improvement_measures.md",
                    mime="text/markdown",
                )

        except Exception as e:
            st.error(f"加载改进措施失败: {e}")
            logger.error(f"改进措施加载失败: {e}")

    def _load_all_embeddings(self) -> tuple[list[list[float]], list[dict[str, Any]]]:
        """加载所有嵌入向量"""
        try:
            collection = self.chroma_manager.get_or_create_collection()
            results = collection.get(include=["embeddings", "metadatas"])

            ids = results.get("ids") or []
            embeddings_raw = results.get("embeddings")
            embeddings = [] if embeddings_raw is None else list(embeddings_raw)
            metadatas_raw = results.get("metadatas")
            metadatas = [] if metadatas_raw is None else list(metadatas_raw)

            # 把 Chroma document id 注入 metadata，方便后续显示任务单号
            for i, meta in enumerate(metadatas):
                if i < len(ids):
                    meta["task_id"] = ids[i]

            return embeddings, metadatas

        except Exception as e:
            logger.error(f"加载嵌入向量失败: {e}")
            return [], []


def main() -> None:
    """主入口"""
    ui = FaultAnalysisUI()
    ui.run()


if __name__ == "__main__":
    main()
