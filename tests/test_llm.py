# ruff: noqa: E402
"""测试LLM API - 在外网终端执行"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.analyzer.llm_provider import OpenAILLMProvider
from src.config.manager import ConfigManager


async def test_llm():
    print("=" * 60)
    print("测试LLM API (智谱)")
    print("=" * 60)

    # 加载配置
    config_manager = ConfigManager()
    config = config_manager.get_config()

    print("\n配置信息:")
    print(f"  Provider: {config.llm.provider}")
    print(f"  Model: {config.llm.model}")
    print(f"  API Key: {config.llm.api_key[:10]}...")

    # 初始化LLM Provider
    llm_provider = OpenAILLMProvider(
        api_key=config.llm.api_key,
        model=config.llm.model,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_tokens,
    )

    # 测试Prompt
    system_prompt = "你是一个专业的故障分析专家，擅长分析软件缺陷的根本原因。"
    user_prompt = "请分析以下故障的根本原因：\n故障描述：企业账户operator属性自动带出VA值，新增operator属性记录后无法自动展示VA。\n请给出详细的根因分析。"

    print("\n" + "=" * 60)
    print("开始测试LLM...")
    print("=" * 60)

    try:
        print(f"\n输入:\n{user_prompt[:100]}...")
        result = await llm_provider.generate(system_prompt, user_prompt)
        print(f"\n输出:\n{result}")
    except Exception as e:
        print(f"错误: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_llm())
