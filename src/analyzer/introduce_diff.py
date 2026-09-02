"""引入缺陷任务单代码变更拉取（辅助代码走查）。

引入单（introduceTaskNo，引入此缺陷的任务单）的代码变更是缺陷引入的
直接候选证据；故障单自身的代码变更通常只是修复动作。背景：故障单
11757372 的复盘中修复动作曾被误判为设计缺陷。

无引入单号、非数字单号或 API 拉取失败时降级为空串，不阻断主流程。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

# 引入单 diff 注入 prompt 的长度上限（避免超长 diff 挤占上下文）
MAX_INTRODUCE_DIFF_CHARS = 12000


async def fetch_introduce_task_diff(
    api_client: Any,
    task_data: dict[str, Any],
) -> str:
    """拉取引入缺陷任务单的代码变更 diff，失败时降级为空串。

    Args:
        api_client: API 客户端（需提供 get_commits 方法），可为 None。
        task_data: 任务数据 dict（TaskInfo.model_dump() 结果）。

    Returns:
        引入单 diff 文本（截断至 MAX_INTRODUCE_DIFF_CHARS）；
        无引入单号、API 客户端不可用或拉取失败时为空串。
    """
    raw_no = task_data.get("introduce_task_no") or task_data.get("introduceTaskNo")
    if not raw_no:
        return ""

    if api_client is None:
        logger.warning("API 客户端不可用，跳过引入单 {} 代码变更拉取", raw_no)
        return ""

    # task-branch/{taskNo}/changes/content 接口需要数字单号
    digits = "".join(ch for ch in str(raw_no) if ch.isdigit())
    if not digits:
        logger.warning("引入单号 {} 非数字单号，跳过引入单代码变更拉取", raw_no)
        return ""

    try:
        commits = await api_client.get_commits(int(digits))
    except Exception as e:
        logger.warning("拉取引入单 {} 代码变更失败(降级忽略): {}", raw_no, str(e)[:80])
        return ""

    diff_text = "\n\n".join(c.diff for c in commits if c.diff)
    if not diff_text:
        logger.info("引入单 {} 无代码变更内容", raw_no)
        return ""
    return diff_text[:MAX_INTRODUCE_DIFF_CHARS]
