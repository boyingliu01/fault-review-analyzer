"""可视化图表生成器 - 根因分布图、违规类型图、改进措施追踪图"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import plotly.graph_objects as go
from loguru import logger

if TYPE_CHECKING:
    from src.analysis.improvement_recommender import ImprovementMeasure


class RootCauseChart:
    """根因分布图生成器"""

    def create_bar_chart(
        self,
        root_causes: dict[str, int],
        title: str = "根因分布统计",
        output_path: str | Path | None = None,
    ) -> bool:
        """创建根因分布柱状图

        Args:
            root_causes: 根因名称到数量的映射
            title: 图表标题
            output_path: 输出文件路径

        Returns:
            是否成功创建图表
        """
        try:
            if not root_causes:
                logger.warning("根因数据为空")
                return False

            # 按数量降序排序
            sorted_causes = sorted(
                root_causes.items(),
                key=lambda x: x[1],
                reverse=True,
            )

            causes = [item[0] for item in sorted_causes]
            counts = [item[1] for item in sorted_causes]
            total = sum(counts)
            percentages = [c / total * 100 for c in counts]

            fig = go.Figure()

            fig.add_trace(
                go.Bar(
                    x=causes,
                    y=counts,
                    text=[f"{c}<br>({p:.1f}%)" for c, p in zip(counts, percentages)],
                    textposition="auto",
                    marker_color="#3498db",
                )
            )

            fig.update_layout(
                title=dict(text=title, x=0.5, font=dict(size=18)),
                xaxis_title="根因类型",
                yaxis_title="故障数量",
                xaxis_tickangle=-45,
                template="plotly_white",
                showlegend=False,
                width=1000,
                height=600,
            )

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                fig.write_html(str(output_path))
                logger.info(f"根因分布图已保存: {output_path}")

            return True

        except Exception as e:
            logger.error(f"创建根因分布图失败: {e}")
            return False


class ViolationChart:
    """违规类型分布图生成器"""

    def create_pie_chart(
        self,
        violations: dict[str, int],
        title: str = "违规类型分布",
        output_path: str | Path | None = None,
    ) -> bool:
        """创建违规类型饼图

        Args:
            violations: 违规类型到数量的映射
            title: 图表标题
            output_path: 输出文件路径

        Returns:
            是否成功创建图表
        """
        try:
            if not violations:
                logger.warning("违规数据为空")
                return False

            labels = list(violations.keys())
            values = list(violations.values())
            total = sum(values)

            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=labels,
                        values=values,
                        hole=0.4,
                        textinfo="label+percent",
                        textposition="outside",
                        hovertemplate="<b>%{label}</b><br>"
                        "数量: %{value}<br>"
                        "占比: %{percent}<br>"
                        "<extra></extra>",
                    )
                ]
            )

            fig.update_layout(
                title=dict(
                    text=f"{title}<br><sub>总计: {total}个违规</sub>",
                    x=0.5,
                    font=dict(size=18),
                ),
                template="plotly_white",
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.3,
                    xanchor="center",
                    x=0.5,
                ),
                width=800,
                height=600,
            )

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                fig.write_html(str(output_path))
                logger.info(f"违规类型分布图已保存: {output_path}")

            return True

        except Exception as e:
            logger.error(f"创建违规类型分布图失败: {e}")
            return False


class ImprovementTrackingChart:
    """改进措施追踪图生成器"""

    def create_priority_chart(
        self,
        measures: list[ImprovementMeasure],
        title: str = "改进措施优先级分布",
        output_path: str | Path | None = None,
    ) -> bool:
        """创建改进措施优先级分布图

        Args:
            measures: 改进措施列表
            title: 图表标题
            output_path: 输出文件路径

        Returns:
            是否成功创建图表
        """
        try:
            if not measures:
                logger.warning("改进措施数据为空")
                return False

            # 按优先级分组统计
            priority_counts: dict[str, list[str]] = {
                "high": [],
                "medium": [],
                "low": [],
            }

            for measure in measures:
                priority = measure.priority
                if priority in priority_counts:
                    priority_counts[priority].append(measure.root_cause)

            priority_names = {
                "high": "高优先级",
                "medium": "中优先级",
                "low": "低优先级",
            }

            priority_colors = {
                "high": "#e74c3c",
                "medium": "#f39c12",
                "low": "#3498db",
            }

            fig = go.Figure()

            for priority in ["high", "medium", "low"]:
                count = len(priority_counts[priority])
                if count > 0:
                    fig.add_trace(
                        go.Bar(
                            name=priority_names[priority],
                            x=[priority_names[priority]],
                            y=[count],
                            text=[f"{count}项"],
                            textposition="auto",
                            marker_color=priority_colors[priority],
                            hovertemplate="<b>%{x}</b><br>措施数量: %{y}<br><extra></extra>",
                        )
                    )

            fig.update_layout(
                title=dict(text=title, x=0.5, font=dict(size=18)),
                xaxis_title="优先级",
                yaxis_title="措施数量",
                template="plotly_white",
                showlegend=False,
                width=800,
                height=500,
            )

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                fig.write_html(str(output_path))
                logger.info(f"改进措施追踪图已保存: {output_path}")

            return True

        except Exception as e:
            logger.error(f"创建改进措施追踪图失败: {e}")
            return False

    def create_detail_chart(
        self,
        measures: list[ImprovementMeasure],
        title: str = "改进措施详情",
        output_path: str | Path | None = None,
    ) -> bool:
        """创建改进措施详情图（横向柱状图）

        Args:
            measures: 改进措施列表
            title: 图表标题
            output_path: 输出文件路径

        Returns:
            是否成功创建图表
        """
        try:
            if not measures:
                logger.warning("改进措施数据为空")
                return False

            # 限制显示前15个措施
            display_measures = measures[:15]

            root_causes = [
                m.root_cause[:30] + "..." if len(m.root_cause) > 30 else m.root_cause
                for m in display_measures
            ]
            impacts = [
                10 if m.priority == "high" else 5 if m.priority == "medium" else 3
                for m in display_measures
            ]
            colors = [
                "#e74c3c"
                if m.priority == "high"
                else "#f39c12"
                if m.priority == "medium"
                else "#3498db"
                for m in display_measures
            ]

            fig = go.Figure()

            fig.add_trace(
                go.Bar(
                    y=root_causes,
                    x=impacts,
                    orientation="h",
                    marker_color=colors,
                    text=[
                        m.measure[:40] + "..." if len(m.measure) > 40 else m.measure
                        for m in display_measures
                    ],
                    textposition="auto",
                    hovertemplate="<b>%{y}</b><br>"
                    "预期影响: %{x}<br>"
                    "措施: %{text}<br>"
                    "<extra></extra>",
                )
            )

            fig.update_layout(
                title=dict(text=title, x=0.5, font=dict(size=18)),
                xaxis_title="预期影响程度",
                yaxis_title="根因",
                template="plotly_white",
                showlegend=False,
                width=1000,
                height=max(400, len(display_measures) * 40),
                yaxis=dict(autorange="reversed"),
            )

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                fig.write_html(str(output_path))
                logger.info(f"改进措施详情图已保存: {output_path}")

            return True

        except Exception as e:
            logger.error(f"创建改进措施详情图失败: {e}")
            return False


class DashboardGenerator:
    """仪表板生成器 - 整合所有图表"""

    def __init__(self) -> None:
        self.root_cause_chart = RootCauseChart()
        self.violation_chart = ViolationChart()
        self.improvement_chart = ImprovementTrackingChart()

    def generate_full_dashboard(
        self,
        root_causes: dict[str, int],
        violations: dict[str, int],
        measures: list[ImprovementMeasure],
        output_dir: str | Path = "./output/visualization",
    ) -> dict[str, str]:
        """生成完整的数据分析仪表板

        Args:
            root_causes: 根因分布数据
            violations: 违规类型分布数据
            measures: 改进措施列表
            output_dir: 输出目录

        Returns:
            生成的文件路径字典
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        # 生成根因分布图
        root_cause_path = output_dir / "root_cause_distribution.html"
        if self.root_cause_chart.create_bar_chart(
            root_causes,
            output_path=root_cause_path,
        ):
            results["root_cause"] = str(root_cause_path)

        # 生成违规类型分布图
        violation_path = output_dir / "violation_distribution.html"
        if self.violation_chart.create_pie_chart(
            violations,
            output_path=violation_path,
        ):
            results["violation"] = str(violation_path)

        # 生成改进措施追踪图
        improvement_priority_path = output_dir / "improvement_priority.html"
        if self.improvement_chart.create_priority_chart(
            measures,
            output_path=improvement_priority_path,
        ):
            results["improvement_priority"] = str(improvement_priority_path)

        improvement_detail_path = output_dir / "improvement_detail.html"
        if self.improvement_chart.create_detail_chart(
            measures,
            output_path=improvement_detail_path,
        ):
            results["improvement_detail"] = str(improvement_detail_path)

        logger.info(f"仪表板生成完成，共{len(results)}个图表")
        return results
