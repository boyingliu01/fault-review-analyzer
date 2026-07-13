"""聚类散点图可视化 - 使用UMAP降维展示聚类结果"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from loguru import logger
from umap import UMAP


class ClusterScatterVisualizer:
    """聚类散点图可视化器 - 使用UMAP将高维向量降维到2D并绘制散点图"""

    def __init__(
        self,
        n_neighbors: int = 15,
        min_dist: float = 0.1,
        random_state: int = 42,
    ) -> None:
        self.n_neighbors = n_neighbors
        self.min_dist = min_dist
        self.random_state = random_state
        self._umap = UMAP(
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            n_components=2,
            random_state=random_state,
        )

    def prepare_data(
        self,
        embeddings: list[list[float]],
        labels: list[int],
        task_ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """准备可视化数据

        Args:
            embeddings: 高维向量列表
            labels: 聚类标签列表
            task_ids: 任务单ID列表
            metadata: 可选的元数据列表

        Returns:
            包含降维后坐标和标签的数据字典
        """
        if not embeddings:
            raise ValueError("向量数据不能为空")

        if len(embeddings) != len(labels) or len(embeddings) != len(task_ids):
            raise ValueError("embeddings、labels和task_ids长度必须一致")

        embeddings_array = np.array(embeddings)

        embeddings_2d = self._umap.fit_transform(embeddings_array)

        return {
            "embeddings_2d": embeddings_2d,
            "labels": labels,
            "task_ids": task_ids,
            "metadata": metadata or [],
        }

    def create_figure(
        self,
        data: dict[str, Any],
        title: str = "故障聚类散点图",
        show_hover: bool = True,
    ) -> go.Figure | None:
        """构建聚类散点图 Figure 对象（供直接渲染，如 Streamlit）

        Args:
            data: prepare_data 返回的数据字典
            title: 图表标题
            show_hover: 是否显示悬停信息

        Returns:
            Plotly Figure 对象，失败时返回 None
        """
        try:
            embeddings_2d = data["embeddings_2d"]
            labels = data["labels"]
            task_ids = data["task_ids"]
            metadata = data.get("metadata", [])

            unique_labels = sorted(set(labels))
            colors = self._generate_colors(len(unique_labels))

            fig = go.Figure()

            for idx, label in enumerate(unique_labels):
                mask = [lb == label for lb in labels]
                x = embeddings_2d[mask, 0]
                y = embeddings_2d[mask, 1]
                ids = [task_ids[i] for i, m in enumerate(mask) if m]

                color = "#808080" if label == -1 else colors[idx]
                name = f"噪声点 ({sum(mask)}个)" if label == -1 else f"聚类 {label} ({sum(mask)}个)"

                hover_text = self._build_hover_text(ids, metadata, mask)

                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y,
                        mode="markers",
                        name=name,
                        marker={
                            "size": 10,
                            "color": color,
                            "opacity": 0.7,
                            "line": {"width": 1, "color": "white"},
                        },
                        text=hover_text if show_hover else None,
                        hovertemplate="<b>%{text}</b><br>X: %{x:.3f}<br>Y: %{y:.3f}"
                        if show_hover
                        else None,
                    )
                )

            fig.update_layout(
                title={
                    "text": title,
                    "x": 0.5,
                    "font": {"size": 20},
                },
                xaxis_title="UMAP Dimension 1",
                yaxis_title="UMAP Dimension 2",
                showlegend=True,
                legend={
                    "yanchor": "top",
                    "y": 0.99,
                    "xanchor": "left",
                    "x": 0.01,
                },
                template="plotly_white",
                width=1000,
                height=800,
            )

            return fig

        except Exception as e:
            logger.error(f"构建散点图失败: {e}")
            return None

    def create_scatter_plot(
        self,
        data: dict[str, Any],
        title: str = "故障聚类散点图",
        output_path: str | Path | None = None,
        show_hover: bool = True,
    ) -> bool:
        """创建聚类散点图并保存到文件

        Args:
            data: prepare_data 返回的数据字典
            title: 图表标题
            output_path: 输出文件路径（None 时不保存）
            show_hover: 是否显示悬停信息

        Returns:
            是否成功创建图表
        """
        fig = self.create_figure(data, title=title, show_hover=show_hover)
        if fig is None:
            return False

        if output_path:
            try:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                fig.write_html(str(output_path))
                logger.info(f"散点图已保存: {output_path}")
            except Exception as e:
                logger.error(f"保存散点图失败: {e}")
                return False

        return True

    def _generate_colors(self, n: int) -> list[str]:
        """生成聚类颜色"""
        plotly_colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ]

        if n <= len(plotly_colors):
            return plotly_colors[:n]

        import plotly.express as px

        return list(px.colors.qualitative.Bold[:n])

    def _build_hover_text(
        self,
        task_ids: list[str],
        metadata: list[dict[str, Any]],
        mask: list[bool],
    ) -> list[str]:
        """构建悬停文本"""
        hover_text = []
        meta_idx = 0

        for i, m in enumerate(mask):
            if not m:
                continue

            text_parts = [f"任务单: {task_ids[meta_idx]}"]

            if metadata and i < len(metadata):
                meta = metadata[i]
                if meta.get("root_cause"):
                    text_parts.append(f"根因: {meta['root_cause'][:50]}...")
                if meta.get("is_violation") is not None:
                    text_parts.append(f"违规: {'是' if meta['is_violation'] else '否'}")

            hover_text.append("<br>".join(text_parts))
            meta_idx += 1

        return hover_text
