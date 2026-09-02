"""Tests for requirement context fetcher (需求-测试传导链证据采集)."""

from unittest.mock import AsyncMock

import pytest

from src.analyzer.requirement_context import fetch_requirement_context


class _FakeTask:
    """get_task 返回的简化 TaskInfo 替身。"""

    def __init__(self, title: str = "", description: str = "") -> None:
        self.title = title
        self.description = description


TASK_DATA = {"task_no": "11757372", "task_id": 1757372}


class TestFetchRequirementContext:
    """Test suite for fetch_requirement_context."""

    @pytest.mark.asyncio
    async def test_api_client_none_yields_gap(self):
        """API 客户端不可用时应产出 gap 声明，不抛异常。"""
        ctx = await fetch_requirement_context(None, TASK_DATA)

        assert ctx.requirement_no == ""
        assert ctx.data_gaps
        assert "API 客户端不可用" in ctx.data_gaps[0]

    @pytest.mark.asyncio
    async def test_collects_parent_task_and_test_cases(self):
        """有父单时应采集单号/标题/描述与关联测试用例，且无 gap。"""
        api = AsyncMock()
        api.get_related_test_case_ids.return_value = [6827877, 6828237]
        api.get_task_relationship.return_value = {
            "data": {
                "parentTask": {
                    "taskNo": "21537689",
                    "taskTitle": "DPC-产品优化提升-Q3",
                },
                "relatedTaskList": None,
            }
        }
        api.get_task.return_value = _FakeTask(
            title="DPC-产品优化提升-Q3", description="本单作为Q3各类产品优化的总单"
        )

        ctx = await fetch_requirement_context(api, TASK_DATA)

        assert ctx.requirement_no == "21537689"
        assert ctx.requirement_title == "DPC-产品优化提升-Q3"
        assert "Q3各类产品优化" in ctx.requirement_desc
        assert ctx.test_case_ids == [6827877, 6828237]
        assert ctx.source == "parent_task"
        assert ctx.data_gaps == []

    @pytest.mark.asyncio
    async def test_no_parent_no_intro_declares_gap(self):
        """无父单且无引入单号时应声明引入关系未录入。"""
        api = AsyncMock()
        api.get_related_test_case_ids.return_value = []
        api.get_task_relationship.return_value = {"data": {"parentTask": None}}

        ctx = await fetch_requirement_context(api, TASK_DATA)

        assert ctx.source == "none"
        assert ctx.requirement_no == ""
        assert any("未录入引入单" in g for g in ctx.data_gaps)

    @pytest.mark.asyncio
    async def test_introduce_task_no_used_when_no_parent(self):
        """无父单但有引入单号时应按引入单溯源并声明未经验证。"""
        api = AsyncMock()
        api.get_related_test_case_ids.return_value = []
        api.get_task_relationship.return_value = {"data": {"parentTask": None}}
        api.get_task.return_value = _FakeTask(title="整改任务", description="接口整改描述")

        ctx = await fetch_requirement_context(
            api, {**TASK_DATA, "introduce_task_no": "11543234"}
        )

        assert ctx.source == "introduce_task"
        assert ctx.requirement_no == "11543234"
        assert "接口整改描述" in ctx.requirement_desc
        assert any("未经验证" in g for g in ctx.data_gaps)

    @pytest.mark.asyncio
    async def test_relationship_failure_degrades(self):
        """relationship 拉取失败时应降级为 gap 声明。"""
        api = AsyncMock()
        api.get_related_test_case_ids.return_value = []
        api.get_task_relationship.side_effect = RuntimeError("boom")

        ctx = await fetch_requirement_context(api, TASK_DATA)

        assert ctx.requirement_no == ""
        assert any("relationship" in g for g in ctx.data_gaps)

    @pytest.mark.asyncio
    async def test_testcase_fetch_failure_degrades(self):
        """测试用例拉取失败时应降级为 gap 声明。"""
        api = AsyncMock()
        api.get_related_test_case_ids.side_effect = RuntimeError("boom")
        api.get_task_relationship.return_value = {"data": {"parentTask": None}}

        ctx = await fetch_requirement_context(api, TASK_DATA)

        assert ctx.test_case_ids == []
        assert any("关联测试用例" in g for g in ctx.data_gaps)

    @pytest.mark.asyncio
    async def test_requirement_detail_failure_degrades(self):
        """需求单详情拉取失败时应保留单号并声明描述缺失。"""
        api = AsyncMock()
        api.get_related_test_case_ids.return_value = []
        api.get_task_relationship.return_value = {
            "data": {"parentTask": {"taskNo": "21537689", "taskTitle": "总单"}}
        }
        api.get_task.side_effect = RuntimeError("boom")

        ctx = await fetch_requirement_context(api, TASK_DATA)

        assert ctx.requirement_no == "21537689"
        assert ctx.requirement_desc == ""
        assert any("详情拉取失败" in g for g in ctx.data_gaps)

    @pytest.mark.asyncio
    async def test_empty_requirement_desc_declares_gap(self):
        """需求单描述为空时应声明需求源头无内容（规则缺失的直接证据）。"""
        api = AsyncMock()
        api.get_related_test_case_ids.return_value = []
        api.get_task_relationship.return_value = {
            "data": {"parentTask": {"taskNo": "21537689", "taskTitle": "总单"}}
        }
        api.get_task.return_value = _FakeTask(title="总单", description="")

        ctx = await fetch_requirement_context(api, TASK_DATA)

        assert any("无描述内容" in g for g in ctx.data_gaps)
