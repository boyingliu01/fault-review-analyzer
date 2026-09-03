"""复盘分析数据层测试 - 批次加载/推断、帕累托降序、研发云链接、违规条款、原子写。

覆盖 REQ-1（批次隔离）、REQ-2（帕累托降序）、REQ-3（规范条款内容）、REQ-5（urid 链接）。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from src.ui import review_data

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def sample_recs() -> dict[int, dict]:
    """构造测试用复盘记录。"""
    return {
        1001: {
            "urId": 1001,
            "title": "故障A",
            "root_causes": [
                {"cause_type": "编码错误", "description": "逻辑错误", "confidence": 0.9}
            ],
            "violations": [
                {"rule_id": "security-001", "rule_name": "敏感信息泄露", "severity": "high"}
            ],
            "improvements": [{"priority": "high", "measure": "加强审查"}],
            "has_code_change": True,
        },
        1002: {
            "urId": 1002,
            "title": "故障B",
            "root_causes": [
                {"cause_type": "设计缺陷", "description": "设计问题", "confidence": 0.8}
            ],
            "violations": [{"rule_id": "J000025", "rule_name": "接口规范", "severity": "medium"}],
            "improvements": [{"priority": "medium", "measure": "重新设计"}],
            "has_code_change": False,
        },
        1003: {
            "urId": 1003,
            "title": "故障C",
            "root_causes": [],
            "violations": [],
            "improvements": [],
            "has_code_change": False,
        },
    }


class TestPendingRebuildPreservation:
    """结论域复审聚合层防静默消失（sprint-20260902-77 SLICE-4）。

    全单撤销 -> pending_rebuild（root_causes 为空），批次推断不得把这类
    单据静默剔除，统计口径须区分"复审撤销待重建"与"本来无结论"。
    """

    def _write_analysis(self, tmp_path: Path, results: list[dict]) -> None:
        (tmp_path / "all_analysis_20260902_000000.json").write_text(
            json.dumps({"results": results}, ensure_ascii=False), encoding="utf-8"
        )

    # @test REQ-6
    def test_batch_inference_keeps_pending_rebuild(self, tmp_path: Path, monkeypatch):
        """批次推断对 pending_rebuild 空结论单显式保留（不丢单）。"""
        self._write_analysis(
            tmp_path,
            [
                {
                    "urId": 2001,
                    "title": "全撤单",
                    "root_causes": [],
                    "conclusion_review": {"conclusion_status": "pending_rebuild", "revoked": [{}]},
                }
            ],
        )
        monkeypatch.setattr(review_data, "_OUT_DIR", tmp_path)
        batches = review_data.load_batches()
        assert [u for b in batches for u in b["urids"]] == [2001]

    # @test REQ-6
    def test_batch_inference_still_drops_plain_empty(self, tmp_path: Path, monkeypatch):
        """普通空结论单（无复审记录）仍不入批次（维持原行为）。"""
        self._write_analysis(tmp_path, [{"urId": 2002, "title": "空单", "root_causes": []}])
        monkeypatch.setattr(review_data, "_OUT_DIR", tmp_path)
        batches = review_data.load_batches()
        assert all(2002 not in b["urids"] for b in batches)

    # @test REQ-6
    def test_primary_cause_pending_rebuild_label(self):
        """pending_rebuild 单首要根因标注复审撤销待重建（区别于无根因）。"""
        rec = {"root_causes": [], "conclusion_review": {"conclusion_status": "pending_rebuild"}}
        assert review_data.primary_cause(rec) == "复审撤销待重建"

    # @test REQ-6
    def test_primary_cause_plain_empty_unchanged(self):
        """无复审记录的空结论单保持原"无根因"口径。"""
        assert review_data.primary_cause({"root_causes": []}) == "无根因"


class TestLoadBatches:
    """批次加载与推断测试。"""

    # @test REQ-1
    def test_load_batches_empty(self, tmp_path: Path, monkeypatch):
        """无 batches.json 且无 all_analysis 文件时返回空列表。"""
        monkeypatch.setattr(review_data, "_OUT_DIR", tmp_path)
        assert review_data.load_batches() == []

    # @test REQ-1
    def test_load_batches_from_json(self, tmp_path: Path, monkeypatch):
        """显式 batches.json 优先加载。"""
        batch_data = {
            "batches": [
                {
                    "batch_id": "batch-20260826-152545",
                    "name": "批次1",
                    "created_at": "2026-08-26 15:25:45",
                    "source": "all_analysis_20260826_152545.json",
                    "urids": [1001, 1002],
                    "count": 2,
                }
            ]
        }
        (tmp_path / "batches.json").write_text(
            json.dumps(batch_data, ensure_ascii=False), encoding="utf-8"
        )
        monkeypatch.setattr(review_data, "_OUT_DIR", tmp_path)
        batches = review_data.load_batches()
        assert len(batches) == 1
        assert batches[0]["batch_id"] == "batch-20260826-152545"
        assert batches[0]["urids"] == [1001, 1002]

    # @test REQ-1
    def test_infer_batches_from_all_analysis(self, tmp_path: Path, monkeypatch):
        """无 batches.json 时从 all_analysis_*.json 时间戳推断批次。"""
        # 模拟两个 all_analysis 文件
        a1 = {
            "results": [
                {"urId": 1001, "root_causes": [{"cause_type": "A"}]},
                {"urId": 1002, "root_causes": [{"cause_type": "A"}]},
            ]
        }
        a2 = {
            "results": [
                {"urId": 1003, "root_causes": [{"cause_type": "B"}]},
            ]
        }
        (tmp_path / "all_analysis_20260826_152545.json").write_text(
            json.dumps(a1, ensure_ascii=False), encoding="utf-8"
        )
        (tmp_path / "all_analysis_20260826_154535.json").write_text(
            json.dumps(a2, ensure_ascii=False), encoding="utf-8"
        )
        monkeypatch.setattr(review_data, "_OUT_DIR", tmp_path)
        batches = review_data.load_batches()
        assert len(batches) == 2
        # 按时间戳排序
        assert batches[0]["urids"] == [1001, 1002]
        assert batches[1]["urids"] == [1003]

    # @test REQ-1
    def test_orphan_progress_goes_to_unfiled(self, tmp_path: Path, monkeypatch):
        """孤儿 progress（不在任何 all_analysis 中）归入未归档批次。"""
        # 一个 all_analysis 含 urid 1001
        a1 = {"results": [{"urId": 1001, "root_causes": [{"cause_type": "A"}]}]}
        (tmp_path / "all_analysis_20260826_152545.json").write_text(
            json.dumps(a1, ensure_ascii=False), encoding="utf-8"
        )
        # 两个 progress：1001（在批次中）+ 1002（孤儿）
        (tmp_path / "progress_1001.json").write_text(
            json.dumps({"urId": 1001, "root_causes": [{"cause_type": "A"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (tmp_path / "progress_1002.json").write_text(
            json.dumps({"urId": 1002, "root_causes": [{"cause_type": "B"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(review_data, "_OUT_DIR", tmp_path)
        batches = review_data.load_batches()
        # 应有未归档批次包含 1002
        unfiled = [b for b in batches if "未归档" in b.get("name", "")]
        assert len(unfiled) == 1
        assert 1002 in unfiled[0]["urids"]

    # @test REQ-1
    def test_batches_json_corrupt_falls_back(self, tmp_path: Path, monkeypatch):
        """batches.json 损坏时回退到自动推断，不抛异常。"""
        (tmp_path / "batches.json").write_text("{broken json", encoding="utf-8")
        a1 = {"results": [{"urId": 1001, "root_causes": [{"cause_type": "A"}]}]}
        (tmp_path / "all_analysis_20260826_152545.json").write_text(
            json.dumps(a1, ensure_ascii=False), encoding="utf-8"
        )
        monkeypatch.setattr(review_data, "_OUT_DIR", tmp_path)
        batches = review_data.load_batches()  # 不应抛异常
        assert len(batches) == 1


class TestSaveBatches:
    """批次原子写测试。"""

    # @test REQ-1
    def test_save_batches_atomic(self, tmp_path: Path, monkeypatch):
        """原子写 batches.json（tmp + replace），且可读回。"""
        monkeypatch.setattr(review_data, "_OUT_DIR", tmp_path)
        batch = {
            "batch_id": "batch-20260826-152545",
            "name": "批次1",
            "created_at": "2026-08-26 15:25:45",
            "source": "all_analysis_20260826_152545.json",
            "urids": [1001, 1002],
            "count": 2,
        }
        review_data.save_batches([batch])
        # 文件存在且内容正确
        assert (tmp_path / "batches.json").exists()
        loaded = json.loads((tmp_path / "batches.json").read_text(encoding="utf-8"))
        assert loaded["batches"][0]["batch_id"] == "batch-20260826-152545"

    # @test REQ-1
    def test_save_batches_dedup(self, tmp_path: Path, monkeypatch):
        """重复 batch_id 写入时去重，不产生重复条目。"""
        monkeypatch.setattr(review_data, "_OUT_DIR", tmp_path)
        batch = {
            "batch_id": "batch-20260826-152545",
            "name": "批次1",
            "created_at": "2026-08-26 15:25:45",
            "urids": [1001],
            "count": 1,
        }
        review_data.save_batches([batch])
        review_data.save_batches([batch])  # 再次写入同 batch_id
        loaded = json.loads((tmp_path / "batches.json").read_text(encoding="utf-8"))
        assert len(loaded["batches"]) == 1


class TestParetoSummary:
    """帕累托降序 + 累计占比测试。"""

    # @test REQ-2
    def test_build_summary_sorted_desc(self, sample_recs):
        """根因按缺陷数降序排列。"""
        df = review_data.build_summary_df(sample_recs)
        counts = df["缺陷数"].tolist()
        assert counts == sorted(counts, reverse=True)

    # @test REQ-2
    def test_build_summary_has_cumulative(self, sample_recs):
        """帕累托需要累计占比列。"""
        df = review_data.build_summary_df(sample_recs)
        assert "累计占比(%)" in df.columns
        # 累计占比单调不减
        cum = df["累计占比(%)"].tolist()
        assert all(cum[i] <= cum[i + 1] for i in range(len(cum) - 1))
        # 最后一项应接近 100
        assert cum[-1] == pytest.approx(100.0, abs=1.0)

    # @test REQ-2
    def test_build_summary_empty(self):
        """空记录时返回空 DataFrame。"""
        df = review_data.build_summary_df({})
        assert df.empty


class TestImprovementSummary:
    """改进措施帕累托统计（单内去重覆盖口径）。"""

    def test_aggregates_by_measure_sorted_desc(self):
        """按措施文本聚合，覆盖缺陷数降序。"""
        recs = {
            1: {"improvements": [{"measure": "加强审查"}]},
            2: {"improvements": [{"measure": "加强审查"}]},
            3: {"improvements": [{"measure": "重新设计"}]},
        }
        df = review_data.build_improvement_summary_df(recs)
        assert df.iloc[0]["改进措施"] == "加强审查"
        assert df.iloc[0]["覆盖缺陷数"] == 2
        counts = df["覆盖缺陷数"].tolist()
        assert counts == sorted(counts, reverse=True)

    def test_dedup_within_single_fault(self):
        """同一单内重复措施只计一次（覆盖缺陷数口径）。"""
        recs = {
            1: {"improvements": [{"measure": "加强审查"}, {"measure": "加强审查"}]},
        }
        df = review_data.build_improvement_summary_df(recs)
        assert df.iloc[0]["覆盖缺陷数"] == 1

    def test_multiple_measures_same_fault_each_counted(self):
        """同一单多条不同措施各计一次覆盖。"""
        recs = {
            1: {"improvements": [{"measure": "加强审查"}, {"measure": "重新设计"}]},
        }
        df = review_data.build_improvement_summary_df(recs)
        assert set(df["覆盖缺陷数"]) == {1}
        assert len(df) == 2

    def test_cumulative_reaches_100(self):
        """累计占比单调不减且终点为 100%（帕累托标准口径）。"""
        recs = {
            1: {"improvements": [{"measure": "加强审查"}]},
            2: {"improvements": [{"measure": "加强审查"}]},
            3: {"improvements": [{"measure": "重新设计"}]},
        }
        df = review_data.build_improvement_summary_df(recs)
        cum = df["累计占比(%)"].tolist()
        assert all(cum[i] <= cum[i + 1] for i in range(len(cum) - 1))
        assert cum[-1] == pytest.approx(100.0, abs=1.0)

    def test_empty_measures_returns_empty_df(self):
        """单据存在但无措施时返回空 DataFrame（列结构完整）。"""
        df = review_data.build_improvement_summary_df({1001: {"improvements": []}})
        assert df.empty
        assert list(df.columns) == ["改进措施", "覆盖缺陷数", "占比(%)", "累计占比(%)"]

    def test_empty_recs_returns_empty_df(self):
        """空记录时返回空 DataFrame。"""
        df = review_data.build_improvement_summary_df({})
        assert df.empty


class TestViolationContent:
    """规范条款内容测试。"""

    # @test REQ-3
    def test_build_violation_with_rule_name(self, sample_recs):
        """违规分布含条款内容（rule_name）列。"""
        df = review_data.build_violation_df(sample_recs)
        assert "条款内容" in df.columns
        # 验证 rule_name 已填充
        sec_row = df[df["规范条款"] == "security-001"]
        assert not sec_row.empty
        assert sec_row.iloc[0]["条款内容"] == "敏感信息泄露"

    # @test REQ-3
    def test_build_violation_rule_name_first(self):
        """同一 rule_id 取首次出现的 rule_name。"""
        recs = {
            1: {
                "urId": 1,
                "root_causes": [{"cause_type": "A"}],
                "violations": [{"rule_id": "R1", "rule_name": "名称甲"}],
            },
            2: {
                "urId": 2,
                "root_causes": [{"cause_type": "A"}],
                "violations": [{"rule_id": "R1", "rule_name": "名称乙"}],
            },
        }
        df = review_data.build_violation_df(recs)
        row = df[df["规范条款"] == "R1"].iloc[0]
        assert row["条款内容"] == "名称甲"
        assert row["违规次数"] == 2  # 按实例计数

    # @test REQ-3
    def test_build_violation_empty(self):
        """无违规时返回空 DataFrame。"""
        recs = {1: {"urId": 1, "root_causes": [], "violations": []}}
        df = review_data.build_violation_df(recs)
        assert df.empty


class TestDetailUrl:
    """研发云链接测试。"""

    # @test REQ-5
    def test_build_detail_url_default(self, monkeypatch):
        """默认模板生成研发云链接。"""
        # 清空环境变量用默认值
        monkeypatch.delenv("RDEV_DETAIL_URL_TEMPLATE", raising=False)
        url = review_data.build_detail_url(52013490)
        assert url == "https://dev.iwhalecloud.com/portal/zcm-devspace/spa/task/pc/52013490"

    # @test REQ-5
    def test_build_detail_url_custom_template(self, monkeypatch):
        """自定义 RDEV_DETAIL_URL_TEMPLATE 生效。"""
        monkeypatch.setenv("RDEV_DETAIL_URL_TEMPLATE", "https://example.com/task/{urId}")
        url = review_data.build_detail_url(12345)
        assert url == "https://example.com/task/12345"

    # @test REQ-5
    def test_build_detail_df_has_url_column(self, sample_recs):
        """明细表包含研发云链接列。"""
        df = review_data.build_detail_df(sample_recs)
        assert "研发云链接" in df.columns
        # 验证 urid 1001 的链接
        row = df[df["urId"] == 1001].iloc[0]
        assert row["研发云链接"] == (
            "https://dev.iwhalecloud.com/portal/zcm-devspace/spa/task/pc/1001"
        )
