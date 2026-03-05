# -*- coding: utf-8 -*-
"""
故障聚类分析 - 完整流程
从Excel读取故障单号 -> API获取原始信息 -> LLM深度分析 -> Embedding -> 聚类 -> 报告
"""
import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from src.config.manager import ConfigManager
from src.embedding.generator import EmbeddingGenerator
from src.clustering.analyzer import ClusterAnalyzer
from src.api.client import APIClient
from src.analyzer.llm_provider import OpenAILLMProvider


SYSTEM_PROMPT = """你是一个专业的软件故障分析专家，擅长分析软件缺陷的根本原因。
请根据故障的原始信息（需求、设计、代码等）进行深度分析，
不要依赖人工填写的复盘结论，独立给出根因分析。"""

ANALYSIS_PROMPT = """请分析以下故障的根本原因，独立给出分析结论：

故障ID: {task_id}
标题: {title}
需求信息: {requirement}
设计信息: {design}
开发信息: {development}
测试信息: {testing}

请按以下JSON格式输出分析结果：
{{
    "root_cause_category": "根因分类（如：需求遗漏、设计缺陷、代码bug、配置错误等）",
    "root_cause_detail": "详细根因描述",
    "affected_stage": "受影响的阶段（需求/设计/开发/测试/生产）",
    "severity": "严重程度（高/中/低）",
    "suggestion": "改进建议"
}}

请只输出JSON，不要其他内容。"""


class FaultAnalyzer:
    def __init__(self, config: Any):
        self.config = config
        self.embedding_gen = EmbeddingGenerator(
            provider=config.embedding.provider,
            model=config.embedding.model,
            api_key=config.embedding.api_key,
            base_url=config.embedding.base_url,
        )
        self.cluster_analyzer = ClusterAnalyzer(
            algorithm=config.clustering.algorithm,
            min_cluster_size=config.clustering.min_cluster_size,
            min_samples=config.clustering.min_samples,
            metric=config.clustering.metric,
        )
        self.api_client = None
        self.llm_provider = None

    def init_api_client(self, base_url: str, token: str, timeout: int, api_path_prefix: str):
        """初始化API客户端"""
        self.api_client = APIClient(
            base_url=base_url,
            token=token,
            timeout=timeout,
            api_path_prefix=api_path_prefix,
        )

    def init_llm_provider(self) -> bool:
        """初始化LLM Provider"""
        if not self.config.llm.api_key:
            return False
        
        base_url = "https://api.openai.com/v1"
        if self.config.llm.provider == 'zhipu':
            base_url = "https://open.bigmodel.cn/api/paas/v4/"
        elif self.config.llm.provider == 'volcengine':
            base_url = self.config.llm.base_url or "https://ark.cn-beijing.volces.com/api/v3"
        
        self.llm_provider = OpenAILLMProvider(
            api_key=self.config.llm.api_key,
            model=self.config.llm.model,
            base_url=base_url,
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
        )
        return True

    async def fetch_task_from_api(self, task_id: int) -> dict | None:
        """从API获取任务原始信息"""
        if not self.api_client:
            return None
        
        try:
            async with self.api_client:
                task = await self.api_client.get_task(task_id)
                if task:
                    return {
                        'task_id': task.task_id,
                        'title': task.title,
                        'description': task.description,
                        'requirement': task.requirement.content if task.requirement else "",
                        'design': task.design.content if task.design else "",
                        'development': task.development.content if task.development else "",
                        'testing': task.testing.content if task.testing else "",
                        'production': task.production.content if task.production else "",
                    }
        except Exception as e:
            print(f"    [API错误] Task {task_id}: {e}")
        return None

    async def analyze_with_llm(self, task_info: dict) -> dict | None:
        """使用LLM进行深度分析"""
        if not self.llm_provider:
            return None
        
        try:
            user_prompt = ANALYSIS_PROMPT.format(
                task_id=task_info.get('task_id', ''),
                title=task_info.get('title', ''),
                requirement=task_info.get('requirement', ''),
                design=task_info.get('design', ''),
                development=task_info.get('development', ''),
                testing=task_info.get('testing', ''),
            )
            
            result = await self.llm_provider.generate(SYSTEM_PROMPT, user_prompt)
            
            import json
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"    [LLM错误] Task {task_info.get('task_id')}: {e}")
        
        return None

    async def generate_embedding(self, text: str) -> list[float] | None:
        """生成embedding"""
        try:
            return await self.embedding_gen.embed_text(text)
        except Exception as e:
            print(f"    [Embedding错误]: {e}")
            return None

    async def analyze(self, task_ids: list[int]) -> list[dict]:
        """完整分析流程"""
        results = []
        
        print(f"\n[1/4] 初始化组件...")
        self.init_api_client(
            base_url=self.config.api.base_url,
            token=self.config.api.api_key,
            timeout=self.config.api.timeout,
            api_path_prefix=self.config.api.api_path_prefix,
        )
        llm_available = self.init_llm_provider()
        print(f"    API客户端: 已初始化")
        print(f"    LLM服务: {'可用' if llm_available else '不可用'}")
        
        print(f"\n[2/4] 获取故障原始信息...")
        for task_id in task_ids:
            print(f"    处理故障单: {task_id}")
            
            task_info = await self.fetch_task_from_api(task_id)
            
            if not task_info:
                task_info = {'task_id': task_id, 'title': f'故障单 {task_id}', 'error': '无法获取原始信息'}
            
            llm_result = None
            if llm_available:  # 启用LLM分析
                print(f"    -> LLM分析中...")
                llm_result = await self.analyze_with_llm(task_info)
            
            if llm_result:
                task_info['llm_analysis'] = llm_result
                analysis_text = f"{task_info['title']} {llm_result.get('root_cause_category', '')} {llm_result.get('root_cause_detail', '')}"
            else:
                analysis_text = f"{task_info['title']} {task_info.get('requirement', '')} {task_info.get('development', '')}"
            
            embedding = await self.generate_embedding(analysis_text)
            
            task_info['analysis_text'] = analysis_text
            task_info['embedding'] = embedding
            results.append(task_info)
            
            if llm_result:
                print(f"    -> 根因: {llm_result.get('root_cause_category', 'N/A')}")
            print(f"    -> Embedding: {'OK' if embedding else '失败'}")
        
        print(f"\n[3/4] 执行聚类分析...")
        valid_tasks = [t for t in results if t.get('embedding') is not None]
        
        if valid_tasks:
            embeddings = [t['embedding'] for t in valid_tasks]
            embeddings_array = np.array(embeddings)
            cluster_result = self.cluster_analyzer.fit_predict(embeddings_array)
            
            for i, task in enumerate(valid_tasks):
                task['cluster'] = int(cluster_result.labels[i])
        else:
            for task in results:
                task['cluster'] = -1
        
        print(f"    聚类数量: {len(set(t['cluster'] for t in valid_tasks))}")
        
        return results


def generate_report(results: list[dict], output_path: Path):
    """生成Markdown报告"""
    report = []
    report.append("# 故障聚类分析详细报告")
    report.append("")
    report.append("## 一、分析概览")
    report.append("")
    report.append(f"- 总故障数: {len(results)}")
    
    valid_tasks = [t for t in results if t.get('embedding')]
    report.append(f"- 有效分析数: {len(valid_tasks)}")
    
    if valid_tasks:
        clusters = {}
        for task in valid_tasks:
            cid = task.get('cluster', -1)
            if cid not in clusters:
                clusters[cid] = []
            clusters[cid].append(task)
        report.append(f"- 聚类数量: {len(clusters)}")
    else:
        report.append("- 聚类数量: 0 (embedding失败)")
    
    report.append("")
    report.append("## 二、每个故障的详细分析")
    report.append("")
    
    valid_tasks = sorted(valid_tasks, key=lambda x: x.get('cluster', -1))
    
    for task in valid_tasks:
        report.append(f"### 故障单 #{task.get('task_id')}")
        report.append("")
        report.append(f"**标题**: {task.get('title', 'N/A')[:200]}")
        report.append("")
        
        if task.get('llm_analysis'):
            analysis = task['llm_analysis']
            report.append("**LLM深度分析**: 是")
            report.append("")
            report.append("| 分析维度 | 内容 |")
            report.append("|---------|------|")
            report.append(f"| 根因分类 | {analysis.get('root_cause_category', 'N/A')} |")
            report.append(f"| 根因详情 | {analysis.get('root_cause_detail', 'N/A')} |")
            report.append(f"| 受影响阶段 | {analysis.get('affected_stage', 'N/A')} |")
            report.append(f"| 严重程度 | {analysis.get('severity', 'N/A')} |")
            report.append(f"| 改进建议 | {analysis.get('suggestion', 'N/A')} |")
        else:
            report.append("**LLM深度分析**: 否 (API不可用或失败)")
        
        if task.get('requirement'):
            report.append("")
            report.append(f"**需求信息**: {task.get('requirement', '')[:200]}...")
        
        if task.get('development'):
            report.append("")
            report.append(f"**开发信息**: {task.get('development', '')[:200]}...")
        
        report.append("")
        report.append(f"**所属聚类**: {task.get('cluster', -1)}")
        report.append("")
        report.append("---")
        report.append("")
    
    report.append("## 三、聚类结果汇总")
    report.append("")
    report.append("| 聚类ID | 故障数量 | 根因分类 |")
    report.append("|--------|----------|----------|")
    
    if valid_tasks:
        clusters = {}
        for task in valid_tasks:
            cid = task.get('cluster', -1)
            if cid not in clusters:
                clusters[cid] = []
            clusters[cid].append(task)
        
        for cid in sorted(clusters.keys()):
            tasks = clusters[cid]
            categories = set()
            for t in tasks:
                if t.get('llm_analysis'):
                    categories.add(t['llm_analysis'].get('root_cause_category', 'N/A'))
            report.append(f"| {cid} | {len(tasks)} | {', '.join(categories) if categories else '-'} |")
    
    report_text = "\n".join(report)
    output_path.write_text(report_text, encoding='utf-8')
    return report_text


async def main():
    print("=" * 80)
    print("故障聚类分析 - 完整流程")
    print("=" * 80)

    print("\n[0/4] 读取故障单号...")
    df = pd.read_excel('故障单列表.xlsx')
    task_ids = df['缺陷单号'].head(10).tolist()
    print(f"    共读取 {len(task_ids)} 个故障单")

    print("\n[配置信息]")
    config_manager = ConfigManager()
    config = config_manager.get_config()
    print(f"    API: {config.api.base_url}")
    print(f"    Embedding: {config.embedding.provider} / {config.embedding.model}")
    print(f"    LLM: {config.llm.provider} / {config.llm.model}")

    analyzer = FaultAnalyzer(config)
    results = await analyzer.analyze(task_ids)

    print("\n[4/4] 生成报告...")
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / "fault_clustering_with_llm.md"
    
    report_text = generate_report(results, report_path)
    
    print(f"\n报告已保存到: {report_path}")
    print("\n" + "=" * 80)
    print(report_text)
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
