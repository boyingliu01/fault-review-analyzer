"""需求-测试传导链例行检查的证据采集。

背景（案例 11757372）：gomo 号码段校验规则在整条需求链上均无定义，
研发只能按通用逻辑实现、测试无验收依据可覆盖该分支，线上才暴露。
"需求验收标准不明确 → 研发跑偏/遗漏 → 测试未覆盖"是典型故障传导链，
复盘中应例行核查需求源头是否定义了故障涉及的业务规则、测试是否覆盖。

采集策略：
1. 故障单 relationship 找父单/引入单（引入关系在研发云上常未录入，
   relationship 响应中的 parentTask 是最可靠的需求链锚点）；
2. 拉父单详情（title/comments）作为需求描述证据；
3. 拉故障单关联测试用例 ID 列表作为测试覆盖事实（用例内容在测试平台）；
4. 采集不到的部分写入 data_gaps 如实声明，禁止分析时脑补。

任何一步失败都降级为 gap 声明，不阻断主流程。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.analysis.root_cause.models import RequirementContext

# 需求描述注入 prompt 的长度上限（避免超长需求文档挤占上下文）
MAX_REQUIREMENT_DESC_CHARS = 6000


async def fetch_requirement_context(
    api_client: Any,
    task_data: dict[str, Any],
) -> RequirementContext:
    """采集需求-测试传导链检查的证据上下文，失败时降级为 gap 声明。

    Args:
        api_client: API 客户端（需提供 get_task_relationship /
            get_related_test_case_ids 方法），可为 None。
        task_data: 任务数据 dict（TaskInfo.model_dump() 结果，
            task_id 为内部 ID，task_no/taskId 为业务单号）。

    Returns:
        RequirementContext；采集不到的部分记录在 data_gaps 中。
    """
    task_no = str(
        task_data.get("task_no") or task_data.get("taskId") or task_data.get("task_id") or ""
    )
    internal_id = task_data.get("task_id") or task_data.get("taskId")
    ctx = RequirementContext()

    if api_client is None:
        ctx.data_gaps.append("API 客户端不可用，未采集需求单与测试用例关联证据")
        return ctx

    # --- 1. 关联测试用例（故障单自身，测试覆盖事实） ---
    if isinstance(internal_id, int) or (isinstance(internal_id, str) and internal_id.isdigit()):
        try:
            ctx.test_case_ids = await api_client.get_related_test_case_ids(int(internal_id))
        except Exception as e:  # noqa: BLE001
            logger.warning("拉取故障单 {} 关联测试用例失败(降级忽略): {}", task_no, str(e)[:80])
            ctx.data_gaps.append("关联测试用例列表拉取失败")

    # --- 2. 父单/引入单（需求链锚点） ---
    parent = {}
    source = ""
    try:
        rel = await api_client.get_task_relationship(task_no)
        data = rel.get("data") or {}
        candidate = data.get("parentTask") or {}
        if isinstance(candidate, dict) and candidate.get("taskNo"):
            parent = candidate
            source = "parent_task"
    except Exception as e:  # noqa: BLE001
        logger.warning("拉取故障单 {} relationship 失败(降级忽略): {}", task_no, str(e)[:80])
        ctx.data_gaps.append("单据关系（relationship）拉取失败")

    if not parent:
        # 引入单关联常未录入（探查案例 11757372 即如此），如实声明
        raw_intro = task_data.get("introduce_task_no") or task_data.get("introduceTaskNo")
        if raw_intro:
            ctx.source = "introduce_task"
            ctx.requirement_no = str(raw_intro)
            ctx.data_gaps.append(
                "故障单无父需求单，仅按引入单号溯源（引入关系未经验证）"
            )
        else:
            ctx.source = "none"
            ctx.data_gaps.append(
                "研发云未录入引入单/父需求关联（list-introduce-bug 反向查询亦为空），"
                "无法程序化锁定引入需求单"
            )
            return ctx
    else:
        ctx.requirement_no = str(parent.get("taskNo") or "")
        ctx.requirement_title = str(parent.get("taskTitle") or "")
        ctx.source = source

    # --- 3. 需求/任务单详情（需求描述证据） ---
    if ctx.requirement_no:
        try:
            req_task = await api_client.get_task(ctx.requirement_no)
            ctx.requirement_title = ctx.requirement_title or req_task.title
            ctx.requirement_desc = (req_task.description or "").strip()[
                :MAX_REQUIREMENT_DESC_CHARS
            ]
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "拉取需求单 {} 详情失败(降级忽略): {}", ctx.requirement_no, str(e)[:80]
            )
            ctx.data_gaps.append("需求/任务单详情拉取失败，需求描述证据缺失")

    if not ctx.requirement_desc and not any("详情" in g for g in ctx.data_gaps):
        ctx.data_gaps.append("关联需求/任务单无描述内容（需求源头规则缺失的直接证据）")

    return ctx
