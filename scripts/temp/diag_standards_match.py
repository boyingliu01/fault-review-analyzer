"""诊断规范匹配召回环节：embedding是否可用、J00007601排名"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv

load_dotenv(override=True)

from src.analysis.standards_matcher import StandardsMatcher
from src.config.manager import ConfigManager
from src.embedding.generator import EmbeddingGenerator
from src.knowledge.manager import StandardsManager


async def main() -> None:
    config = ConfigManager()
    cfg = config.load()
    print(f"embedding provider: {cfg.embedding.provider}, model: {cfg.embedding.model}")
    print(f"embedding api_key 前10位: {cfg.embedding.api_key[:10] if cfg.embedding.api_key else '(空)'}")

    sm = StandardsManager()
    rules = [r for c in sm.get_all_categories() for r in c.rules]
    print(f"规范总数: {len(rules)}")

    # 1. 测试embedding连通性
    eg = EmbeddingGenerator(
        provider=cfg.embedding.provider,
        model=cfg.embedding.model,
        api_key=cfg.embedding.api_key,
        base_url=cfg.embedding.base_url,
        batch_size=cfg.embedding.batch_size,
    )
    try:
        vec = await eg.embed_text("RestTemplate 单例复用 线程池耗尽")
        print(f"embedding测试: OK, 维度={len(vec)}")
    except Exception as e:
        print(f"embedding测试: 失败 - {type(e).__name__}: {e}")
        return

    # 2. 用故障结论文本做召回，看J00007601排名
    query = (
        "新电现场 发生故障，由于代码不断的创建restTemplete ，导致线程池耗尽\n"
        "编码环节 根因是代码中每次调用createRestTemplate都创建新的HttpClient实例和IdleConnectionEvictor线程，未使用单例模式复用，导致线程资源泄漏直至OOM\n"
        "资源泄漏 HttpClient和IdleConnectionEvictor线程在每次HTTP调用时被重复创建且未被正确释放\n"
        "单例模式缺失 RestTemplate/HttpClient作为重量级资源对象，应当采用单例模式复用\n"
        "设计缺陷 未将 RestTemplate/HttpClient 设计为单例或进行池化管理"
    )
    matcher = StandardsMatcher(standards_manager=sm, embedding_generator=eg, llm_provider=None)
    candidates = await matcher._retrieve_candidates(query)

    print("\n召回Top8:")
    for i, c in enumerate(candidates, 1):
        print(f"  {i}. {c.rule_id} sim={c.similarity:.4f} {c.rule_title[:40]}")

    # 3. 检查J00007601在所有规则中的排名
    import numpy as np
    texts = [matcher._rule_to_document(r) for r in rules]
    embs = await matcher._get_rule_embeddings(rules, texts)
    qv = np.array(await eg.embed_text(query))
    sims = []
    for r, e in zip(rules, embs):
        sims.append((r.id, matcher._cosine_similarity(qv, np.array(e))))
    sims.sort(key=lambda x: -x[1])
    rank = next(i for i, (rid, _) in enumerate(sims, 1) if rid == "J00007601")
    target_sim = dict(sims)["J00007601"]
    print(f"\nJ00007601 全库排名: {rank}/{len(sims)}, 相似度: {target_sim:.4f}")
    print("全库Top5:", [(rid, f"{s:.3f}") for rid, s in sims[:5]])


if __name__ == "__main__":
    asyncio.run(main())
