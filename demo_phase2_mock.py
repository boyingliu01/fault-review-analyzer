#!/usr/bin/env python
"""演示：批量故障单聚类分析（mock数据模式）"""

import json
import random
from pathlib import Path
from datetime import datetime
import numpy as np

# 扩展mock数据到15个故障单
MOCK_TASKS_BATCH = [
    # 数据库类（3个）
    {
        "task_id": 11748712,
        "title": "创建唯一索引和主键约束导致的数据库异常",
        "category": "数据库",
        "root_cause": "历史数据兼容性",
        "keywords": ["数据库", "索引", "约束"],
    },
    {
        "task_id": 11745664,
        "title": "数据库连接池耗尽导致服务不可用",
        "category": "数据库",
        "root_cause": "连接未关闭",
        "keywords": ["数据库", "连接池", "资源"],
    },
    {
        "task_id": 11743724,
        "title": "SQL查询慢导致页面响应超时",
        "category": "数据库",
        "root_cause": "缺少索引",
        "keywords": ["数据库", "SQL", "性能"],
    },
    # 并发类（3个）
    {
        "task_id": 11751534,
        "title": "并发场景下订单状态不一致",
        "category": "并发",
        "root_cause": "并发控制缺失",
        "keywords": ["并发", "状态", "锁"],
    },
    {
        "task_id": 11742292,
        "title": "多线程环境下数据竞争问题",
        "category": "并发",
        "root_cause": "线程不安全",
        "keywords": ["并发", "线程", "安全"],
    },
    {
        "task_id": 11740454,
        "title": "分布式锁失效导致重复处理",
        "category": "并发",
        "root_cause": "锁超时",
        "keywords": ["并发", "分布式", "锁"],
    },
    # 安全类（3个）
    {
        "task_id": 11751363,
        "title": "SQL注入漏洞导致的安全风险",
        "category": "安全",
        "root_cause": "字符串拼接SQL",
        "keywords": ["安全", "SQL注入", "注入"],
    },
    {
        "task_id": 11740449,
        "title": "未授权访问敏感数据接口",
        "category": "安全",
        "root_cause": "权限校验缺失",
        "keywords": ["安全", "权限", "未授权"],
    },
    {
        "task_id": 11739485,
        "title": "XSS漏洞导致的安全风险",
        "category": "安全",
        "root_cause": "输入未转义",
        "keywords": ["安全", "XSS", "输入校验"],
    },
    # 空指针/NPE类（3个）
    {
        "task_id": 11750733,
        "title": "空指针异常导致服务崩溃",
        "category": "代码缺陷",
        "root_cause": "空值校验缺失",
        "keywords": ["空指针", "NullPointer", "空值"],
    },
    {
        "task_id": 11739484,
        "title": "方法返回null未做处理",
        "category": "代码缺陷",
        "root_cause": "返回值未校验",
        "keywords": ["空指针", "null", "返回值"],
    },
    {
        "task_id": 11739476,
        "title": "Optional使用不当导致空指针",
        "category": "代码缺陷",
        "root_cause": "Optional误用",
        "keywords": ["空指针", "Optional", "误用"],
    },
    # 配置/运维类（3个）
    {
        "task_id": 11738437,
        "title": "配置项错误导致服务启动失败",
        "category": "配置",
        "root_cause": "配置校验缺失",
        "keywords": ["配置", "启动", "配置项"],
    },
    {
        "task_id": 11738436,
        "title": "环境变量未设置导致功能异常",
        "category": "配置",
        "root_cause": "环境配置缺失",
        "keywords": ["配置", "环境变量", "部署"],
    },
    {
        "task_id": 11738435,
        "title": "缓存配置不当导致内存溢出",
        "category": "配置",
        "root_cause": "缓存策略问题",
        "keywords": ["配置", "缓存", "内存"],
    },
]


def generate_mock_embeddings(tasks: list, dim: int = 128) -> np.ndarray:
    """生成mock embedding向量（模拟真实embedding）"""
    n = len(tasks)

    # 按类别分组，同一类别的向量应该更相似
    categories = list(set(t["category"] for t in tasks))
    category_centers = {}

    # 为每个类别生成一个中心向量
    for cat in categories:
        center = np.random.randn(dim)
        center = center / np.linalg.norm(center)  # 归一化
        category_centers[cat] = center

    embeddings = []
    for task in tasks:
        # 基于类别中心 + 随机噪声
        center = category_centers[task["category"]]
        noise = np.random.randn(dim) * 0.3  # 30%噪声
        vec = center + noise
        vec = vec / np.linalg.norm(vec)  # 归一化
        embeddings.append(vec)

    return np.array(embeddings)


def mock_cluster_analysis(embeddings: np.ndarray, tasks: list, min_cluster_size: int = 3) -> dict:
    """模拟聚类分析"""
    n = len(tasks)

    # 手动模拟聚类结果（基于类别）
    category_to_cluster = {}
    cluster_id = 0
    labels = []

    for task in tasks:
        cat = task["category"]
        if cat not in category_to_cluster:
            category_to_cluster[cat] = cluster_id
            cluster_id += 1
        labels.append(category_to_cluster[cat])

    # 计算聚类统计
    unique_labels = set(labels)
    cluster_count = len(unique_labels)
    noise_count = 0  # 模拟模式下无噪声

    # 聚类详情
    clusters_detail = {}
    for i, label in enumerate(labels):
        if label not in clusters_detail:
            clusters_detail[label] = {
                "cluster_id": label,
                "task_ids": [],
                "titles": [],
                "category": tasks[i]["category"],
                "root_causes": [],
            }
        clusters_detail[label]["task_ids"].append(tasks[i]["task_id"])
        clusters_detail[label]["titles"].append(tasks[i]["title"])
        clusters_detail[label]["root_causes"].append(tasks[i]["root_cause"])

    # 为每个聚类生成描述
    for cluster_id, detail in clusters_detail.items():
        detail["common_keywords"] = list(
            set(kw for t in tasks if t["category"] == detail["category"] for kw in t["keywords"])
        )
        detail["summary"] = (
            f"该聚类包含{len(detail['task_ids'])}个{detail['category']}类故障单，主要涉及{', '.join(detail['common_keywords'][:3])}等问题"
        )

    return {
        "tasks": [
            {"task_id": t["task_id"], "cluster_id": labels[i], "title": t["title"]}
            for i, t in enumerate(tasks)
        ],
        "cluster_count": cluster_count,
        "noise_count": noise_count,
        "total_tasks": n,
        "clusters": list(clusters_detail.values()),
    }


def generate_cluster_report(clustering_result: dict) -> str:
    """生成聚类分析报告"""
    lines = [
        "# 故障聚类分析报告",
        "",
        "## 聚类概览",
        "",
        f"- **任务总数**: {clustering_result['total_tasks']}",
        f"- **聚类数量**: {clustering_result['cluster_count']}",
        f"- **噪声点**: {clustering_result['noise_count']}",
        "",
        "## 聚类分布",
        "",
        "| 聚类ID | 类别 | 任务数 | 占比 |",
        "|--------|------|--------|------|",
    ]

    for cluster in clustering_result["clusters"]:
        pct = len(cluster["task_ids"]) / clustering_result["total_tasks"] * 100
        lines.append(
            f"| {cluster['cluster_id']} | {cluster['category']} | {len(cluster['task_ids'])} | {pct:.1f}% |"
        )

    lines.extend(["", "## 聚类详情", ""])

    for cluster in clustering_result["clusters"]:
        lines.extend(
            [
                f"### 聚类 {cluster['cluster_id']} - {cluster['category']}",
                "",
                f"**摘要**: {cluster['summary']}",
                "",
                f"**任务数量**: {len(cluster['task_ids'])}",
                "",
                "**共同特征**:",
                f"- 关键词: {', '.join(cluster['common_keywords'])}",
                f"- 典型根因: {', '.join(list(set(cluster['root_causes']))[:2])}",
                "",
                "**任务列表**:",
            ]
        )

        for tid, title in zip(cluster["task_ids"], cluster["titles"]):
            lines.append(f"- {tid}: {title[:40]}...")

        lines.append("")

    lines.extend(
        [
            "---",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "*本报告由故障复盘分析系统自动生成*",
        ]
    )

    return "\n".join(lines)


def main():
    """主函数：执行mock聚类分析"""
    print("=" * 70)
    print("故障复盘分析系统 - 阶段2演示（批量聚类分析）")
    print("=" * 70)
    print()

    output_dir = Path("output/phase2")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"【阶段2】分析 {len(MOCK_TASKS_BATCH)} 个故障单并聚类...")
    print()

    # 步骤1：生成embedding
    print("步骤1/3: 生成故障单向量表示...")
    embeddings = generate_mock_embeddings(MOCK_TASKS_BATCH)
    print(f"  ✓ 已生成 {len(MOCK_TASKS_BATCH)} 个 {embeddings.shape[1]}维向量")
    print()

    # 步骤2：执行聚类
    print("步骤2/3: 执行HDBSCAN聚类...")
    clustering_result = mock_cluster_analysis(embeddings, MOCK_TASKS_BATCH, min_cluster_size=3)
    print(f"  ✓ 聚类完成")
    print(f"  ✓ 发现 {clustering_result['cluster_count']} 个聚类")
    print(f"  ✓ 噪声点: {clustering_result['noise_count']}")
    print()

    # 步骤3：生成报告
    print("步骤3/3: 生成聚类分析报告...")
    report = generate_cluster_report(clustering_result)
    report_path = output_dir / "cluster_analysis_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  ✓ 报告已保存: {report_path}")
    print()

    # 保存聚类数据供阶段3使用
    data_path = output_dir / "clustering_result.json"
    data_path.write_text(
        json.dumps(clustering_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  ✓ 聚类数据已保存: {data_path}")
    print()

    print("=" * 70)
    print("【阶段2完成】")
    print("=" * 70)
    print()

    # 输出聚类摘要
    print("聚类结果摘要:")
    print()
    for cluster in clustering_result["clusters"]:
        print(
            f"  聚类 {cluster['cluster_id']} [{cluster['category']}]: {len(cluster['task_ids'])} 个任务"
        )
        print(
            f"    任务: {', '.join(map(str, cluster['task_ids'][:5]))}{'...' if len(cluster['task_ids']) > 5 else ''}"
        )
        print()

    print("=" * 70)
    print("阶段2验证清单（你需要人工判断这些点）")
    print("=" * 70)
    print()
    print("□ 相似故障是否被分到同一簇？（如所有数据库问题在一个簇）")
    print("□ 不同类别故障是否被正确分开？（如数据库 vs 并发）")
    print("□ 聚类数量是否合理？（期望3-5个主要类别）")
    print("□ 噪声点是否可控？（期望<20%）")
    print("□ 聚类摘要是否准确描述该组故障特征？")
    print()
    print("请查看 output/phase2/cluster_analysis_report.md 进行人工验证")
    print("=" * 70)


if __name__ == "__main__":
    main()
