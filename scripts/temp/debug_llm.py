"""调试 LLM provider 创建"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.analyzer.llm_provider import create_llm_provider
from src.config.manager import ConfigManager


async def main() -> None:
    cm = ConfigManager()
    cm.load()
    cfg = cm.get_config()

    print("LLM Config:")
    print(f"  provider: {cfg.llm.provider}")
    print(f"  model:    {cfg.llm.model}")
    print(f"  api_key:  {cfg.llm.api_key[:20]}..." if cfg.llm.api_key else "  api_key:  (empty)")
    print(f"  base_url: {cfg.llm.base_url}")

    provider = create_llm_provider(cfg.llm)
    print(f"\nLLM Provider: {provider}")

    if provider:
        print("\n测试 LLM 调用...")
        try:
            result = await provider.generate(
                system="你是助手",
                user="用一句话回答：你好"
            )
            print(f"  结果: {result[:100]}...")
        except Exception as e:
            print(f"  错误: {e}")


asyncio.run(main())
