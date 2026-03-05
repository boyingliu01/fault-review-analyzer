# -*- coding: utf-8 -*-
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from src.config.manager import ConfigManager
from src.embedding.generator import EmbeddingGenerator
from src.clustering.analyzer import ClusterAnalyzer
from src.rules.engine import RulesEngine


async def analyze_faults():
    print("=" * 80)
    print("故障聚类分析 - 详细报告")
    print("=" * 80)

    # 1. 读取Excel数据
    print("\n[1/5] 读取Excel数据...")
    df = pd.read_excel('SQL缺陷分析结果.xlsx')
    tasks = df.head(10)
    
    task_ids = tasks['泄露缺陷单号'].tolist()
    print(f"    共读取 {len(task_ids)} 个故障单: {task_ids}")

    # 2. 加载配置
    print("\n[2/5] 加载配置...")
    config_manager = ConfigManager()
    config = config_manager.get_config()
    print(f"    Embedding Provider: {config.embedding.provider}")
    print(f"    Embedding Model: {config.embedding.model}")
    print(f"    Clustering Algorithm: {config.clustering.algorithm}")

    # 3. 初始化组件
    print("\n[3/5] 初始化组件...")
    embedding_gen = EmbeddingGenerator(
        provider=config.embedding.provider,
        model=config.embedding.model,
        api_key=config.embedding.api_key,
        base_url=config.embedding.base_url,
    )
    cluster_analyzer = ClusterAnalyzer(
        algorithm=config.clustering.algorithm,
        min_cluster_size=config.clustering.min_cluster_size,
        min_samples=config.clustering.min_samples,
        metric=config.clustering.metric,
    )
    rules_engine = RulesEngine()

    # 4. 处理每个故障
    print("\n[4/5] 处理故障数据...")
    processed_tasks = []
    
    for idx, row in tasks.iterrows():
        task_id = int(row['泄露缺陷单号'])
        title = str(row['标题']) if pd.notna(row['标题']) else ""
        reason = str(row['引入原因']) if pd.notna(row['引入原因']) else ""
        stage = str(row['引入环节']) if pd.notna(row['引入环节']) else ""
        problem_type = str(row['问题类型']) if pd.notna(row['问题类型']) else ""
        sql_related = str(row['是否SQL相关']) if pd.notna(row['是否SQL相关']) else "N"
        
        # 构建分析文本
        analysis_text = f"""
        标题: {title}
        引入原因: {reason}
        引入环节: {stage}
        问题类型: {problem_type}
        SQL相关: {sql_related}
        """.strip()
        
        # 生成embedding
        try:
            embedding = await embedding_gen.embed_text(analysis_text)
            print(f"    [Embedding] Task {task_id} - 维度: {len(embedding)}")
        except Exception as e:
            print(f"    [Embedding错误] Task {task_id}: {e}")
            embedding = None
        
        # 规则检查 - 需要传入dict格式
        try:
            task_dict = {
                'title': title,
                'reason': reason,
                'stage': stage,
                'problem_type': problem_type,
            }
            violation_list = rules_engine.check(task_dict)
            violations = violation_list if violation_list else []
        except Exception as e:
            print(f"    [规则检查错误] Task {task_id}: {e}")
            violations = []
        
        processed_tasks.append({
            'task_id': task_id,
            'title': title,
            'reason': reason,
            'stage': stage,
            'problem_type': problem_type,
            'sql_related': sql_related,
            'analysis_text': analysis_text,
            'embedding': embedding,
            'violations': violations,
        })

    # 5. 聚类分析
    print("\n[5/5] 执行聚类分析...")
    embeddings = [t['embedding'] for t in processed_tasks if t['embedding'] is not None]
    valid_tasks = [t for t in processed_tasks if t['embedding'] is not None]
    
    embeddings_array = np.array(embeddings)
    
    cluster_result = cluster_analyzer.fit_predict(embeddings_array)
    
    # 为每个任务分配聚类标签
    for i, task in enumerate(valid_tasks):
        label = cluster_result.labels[i]
        task['cluster'] = int(label)
    
    print(f"    聚类结果: {len(set(cluster_result.labels))} 个簇")
    
    # 6. 生成详细报告
    print("\n[6/6] 生成报告...")
    
    report = []
    report.append("# 故障聚类分析详细报告")
    report.append("")
    report.append("## 一、分析概览")
    report.append("")
    report.append(f"- 总故障数: {len(processed_tasks)}")
    report.append(f"- 有效分析数: {len(valid_tasks)}")
    report.append(f"- 聚类数量: {len(set(cluster_result.labels))}")
    report.append(f"- Embedding模型: {config.embedding.model} ({config.embedding.provider})")
    report.append(f"- 聚类算法: {config.clustering.algorithm}")
    report.append("")
    
    report.append("## 二、每个故障的详细分析")
    report.append("")
    
    # 按聚类分组
    clusters = {}
    for task in valid_tasks:
        cluster_id = task['cluster']
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append(task)
    
    for cluster_id, cluster_tasks in sorted(clusters.items()):
        report.append(f"### 聚类 {cluster_id} ({len(cluster_tasks)} 个故障)")
        report.append("")
        
        for task in cluster_tasks:
            report.append(f"#### 故障单 #{task['task_id']}")
            report.append("")
            report.append(f"**标题**: {task['title'][:200]}...")
            report.append("")
            report.append(f"**引入原因**: {task['reason']}")
            report.append("")
            report.append(f"| 字段 | 值 |")
            report.append(f"|------|-----|")
            report.append(f"| 引入环节 | {task['stage']} |")
            report.append(f"| 问题类型 | {task['problem_type']} |")
            report.append(f"| SQL相关 | {task['sql_related']} |")
            report.append(f"| 所属聚类 | {task['cluster']} |")
            report.append("")
            
            # 规则检查
            if task['violations']:
                report.append("**规则违规**: 是")
                for v in task['violations']:
                    report.append(f"  - {v.rule_name}: {v.description}")
            else:
                report.append("**规则违规**: 否")
            report.append("")
            report.append("---")
            report.append("")
    
    report.append("## 三、聚类结果汇总")
    report.append("")
    report.append("| 聚类ID | 故障数量 | 引入环节 | 问题类型 |")
    report.append("|--------|----------|----------|----------|")
    
    for cluster_id, cluster_tasks in sorted(clusters.items()):
        stages = set(t['stage'] for t in cluster_tasks if t['stage'])
        types = set(t['problem_type'] for t in cluster_tasks if t['problem_type'])
        report.append(f"| {cluster_id} | {len(cluster_tasks)} | {', '.join(stages) if stages else '-'} | {', '.join(types) if types else '-'} |")
    
    report.append("")
    report.append("## 四、规则匹配统计")
    report.append("")
    total_violations = sum(len(t['violations']) for t in valid_tasks)
    report.append(f"- 总违规数: {total_violations}")
    
    # 按引入环节统计
    stage_stats = {}
    for task in valid_tasks:
        stage = task['stage'] or '未知'
        if stage not in stage_stats:
            stage_stats[stage] = {'total': 0, 'violations': 0}
        stage_stats[stage]['total'] += 1
        stage_stats[stage]['violations'] += len(task['violations'])
    
    report.append("")
    report.append("| 引入环节 | 故障数 | 违规数 |")
    report.append("|----------|--------|--------|")
    for stage, stats in sorted(stage_stats.items()):
        report.append(f"| {stage} | {stats['total']} | {stats['violations']} |")
    
    report_text = "\n".join(report)
    
    # 保存报告
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / "fault_clustering_report.md"
    report_path.write_text(report_text, encoding='utf-8')
    
    print(f"\n报告已保存到: {report_path}")
    print("\n" + "=" * 80)
    print(report_text)
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(analyze_faults())
