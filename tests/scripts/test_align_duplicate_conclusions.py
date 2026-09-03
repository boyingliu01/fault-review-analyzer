"""align_duplicate_conclusions.py 存量一致性校正不变量锁定（R9）。

- issue 层配对：同 Issue No 组内主单已复盘 -> 从单整体复用主单结论与
  复审状态，reused_from 审计入案，备份目录生成
- 幂等跳过：从单已含 conclusion_review.reused_from -> 跳过不重写
- 字段保护：从单 violations/improvements/image_evidence 等自身字段零污染
- 主单保障：master 记录无 root_causes -> 该对 skipped，不写回
- borderline 清单：未达强一致的对出清单文件，原文件不被改动
- dry-run：只统计不写回不备份不出清单文件
"""

import json
from pathlib import Path
from typing import Any

from scripts.align_duplicate_conclusions import align

MASTER_REC: dict[str, Any] = {
    "urId": 200,
    "title": "订单导出超时",
    "root_causes": [{"cause_type": "设计缺陷", "description": "查询未做分页导致超时"}],
    "conclusion_review": {
        "reviewed_at": "2026-09-03T12:00:00",
        "method": "delphi_multi_expert_consensus",
        "items": [],
    },
    "deep_root_causes": {"deep_root_causes": ["深度结论A"]},
    "violations": [{"rule_id": "master-rule"}],
    "image_evidence": "主单截图",
}

SLAVE_REC: dict[str, Any] = {
    "urId": 100,
    "title": "订单导出超时",
    "root_causes": [{"cause_type": "旧结论", "description": "独立复盘的旧内容"}],
    "violations": [{"rule_id": "slave-rule"}],
    "improvements": [{"action": "从单改进"}],
    "image_evidence": "从单截图",
}


def _task(tid: int) -> dict[str, Any]:
    return {
        "task_id": tid,
        "title": "订单导出超时",
        "description": "导出接口超时",
        "create_time": "2026-01-04 15:30:00",
        "development": None,
    }


def _loader(task_id: int) -> dict[str, Any] | None:
    return _task(task_id)


def _write(out_dir: Path, urid: int, rec: dict[str, Any]) -> Path:
    fp = out_dir / f"progress_{urid}.json"
    fp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return fp


class TestAlign:
    def test_issue_pair_reuses_master(self, tmp_path: Path):
        """同 issue no 且主单已复盘 -> 从单复用，备份与字段保护到位。"""
        _write(tmp_path, 100, json.loads(json.dumps(SLAVE_REC)))
        _write(tmp_path, 200, json.loads(json.dumps(MASTER_REC)))
        stats = align(tmp_path, _loader, {100: "IS1", 200: "IS1"})
        assert stats["reused"] == [(200, 100)]
        out = json.loads((tmp_path / "progress_100.json").read_text(encoding="utf-8"))
        assert out["root_causes"] == MASTER_REC["root_causes"]
        assert out["conclusion_review"]["reused_from"]["master_urId"] == 200
        assert out["conclusion_review"]["reused_from"]["source"] == "issue_no"
        assert out["deep_root_causes"] == {"deep_root_causes": ["深度结论A"]}
        # 字段保护：从单自身字段零污染
        assert out["violations"] == [{"rule_id": "slave-rule"}]
        assert out["improvements"] == [{"action": "从单改进"}]
        assert out["image_evidence"] == "从单截图"
        # 主单文件不动
        assert json.loads((tmp_path / "progress_200.json").read_text(encoding="utf-8")) == (
            MASTER_REC
        )
        # 备份生成
        backups = list(tmp_path.glob("duplicate_align_backup_*/progress_100.json"))
        assert len(backups) == 1
        backup_rec = json.loads(backups[0].read_text(encoding="utf-8"))
        assert backup_rec["root_causes"] == SLAVE_REC["root_causes"]

    def test_idempotent_skip_already_reused(self, tmp_path: Path):
        """从单已含 reused_from -> 跳过且文件不变（重跑安全）。"""
        rec = json.loads(json.dumps(SLAVE_REC))
        rec["conclusion_review"] = {"reused_from": {"master_urId": 200}}
        fp = _write(tmp_path, 100, rec)
        _write(tmp_path, 200, json.loads(json.dumps(MASTER_REC)))
        stats = align(tmp_path, _loader, {100: "IS1", 200: "IS1"})
        assert stats["reused"] == []
        assert stats["skipped"] == [(200, 100)]
        assert json.loads(fp.read_text(encoding="utf-8")) == rec

    def test_role_reversal_pair_not_realigned(self, tmp_path: Path):
        """复用写回后主从裁决反转 -> 已处理对不再二次写回（审计链防环）。

        第一轮 200 为主单、100 复用；写回后 100 继承复审状态，重跑时
        issue 组内两者均已复盘，主从按 createdDate/task_id 重裁反转
        （100 成主单、200 成从单），若不拦截会把 200 的结论替换为 100
        的继承副本，reused_from 审计链成环。
        """
        slave_after = json.loads(json.dumps(SLAVE_REC))
        slave_after["root_causes"] = json.loads(json.dumps(MASTER_REC["root_causes"]))
        slave_after["conclusion_review"] = {
            "reviewed_at": "2026-09-03T12:48:15",
            "method": "delphi_multi_expert_consensus",
            "items": [],
            "reused_from": {
                "master_urId": 200,
                "source": "issue_no",
                "title_sim": 1.0,
                "desc_sim": 1.0,
                "diff_sim": 1.0,
                "reused_at": "2026-09-03T15:47:50",
            },
        }
        master_fp = _write(tmp_path, 200, json.loads(json.dumps(MASTER_REC)))
        slave_fp = _write(tmp_path, 100, slave_after)
        stats = align(tmp_path, _loader, {100: "IS1", 200: "IS1"})
        assert stats["reused"] == []
        assert stats["skipped"] == [(100, 200)]
        assert json.loads(master_fp.read_text(encoding="utf-8")) == MASTER_REC
        assert json.loads(slave_fp.read_text(encoding="utf-8")) == slave_after

    def test_master_without_conclusion_skipped(self, tmp_path: Path):
        """主单无复盘结论（reviewed_at 缺失）-> 组内不配对，无写回。"""
        bare = {"urId": 200, "title": "订单导出超时", "root_causes": []}
        slave_fp = _write(tmp_path, 100, json.loads(json.dumps(SLAVE_REC)))
        _write(tmp_path, 200, bare)
        stats = align(tmp_path, _loader, {100: "IS1", 200: "IS1"})
        assert stats["reused"] == []
        assert json.loads(slave_fp.read_text(encoding="utf-8")) == SLAVE_REC

    def test_content_strong_reuse_without_issue_map(self, tmp_path: Path):
        """无映射表时内容相似度层兜底（title/desc 完全一致 + 主单已复盘）。"""
        _write(tmp_path, 100, json.loads(json.dumps(SLAVE_REC)))
        _write(tmp_path, 200, json.loads(json.dumps(MASTER_REC)))
        stats = align(tmp_path, _loader, None)
        assert stats["reused"] == [(200, 100)]
        out = json.loads((tmp_path / "progress_100.json").read_text(encoding="utf-8"))
        assert out["conclusion_review"]["reused_from"]["source"] == "content"

    def test_borderline_not_written_but_listed(self, tmp_path: Path):
        """过候选门槛未达强一致 -> borderline 清单，原文件不改动。"""
        slave = json.loads(json.dumps(SLAVE_REC))
        master = json.loads(json.dumps(MASTER_REC))
        _write(tmp_path, 100, slave)
        _write(tmp_path, 200, master)

        def borderline_loader(task_id: int) -> dict[str, Any] | None:
            # t_sim 0.923（gate 过、候选门槛过），desc 缺失 d_sim 0.0
            title = "abcdef" if task_id == 100 else "abcdefg"
            return {
                "task_id": task_id,
                "title": title,
                "description": "",
                "development": None,
            }

        stats = align(tmp_path, borderline_loader, None)
        assert stats["reused"] == []
        assert len(stats["borderline"]) == 1
        pair = stats["borderline"][0]
        assert pair["slave_id"] == 100 and pair["master_id"] == 200
        assert pair["verdict"] == "borderline"
        assert json.loads((tmp_path / "progress_100.json").read_text(encoding="utf-8")) == slave
        # 清单文件生成
        assert list(tmp_path.glob("duplicate_borderline_*.md"))

    def test_dry_run_no_write(self, tmp_path: Path):
        """dry-run 只统计：不写回、不备份、不出清单文件。"""
        _write(tmp_path, 100, json.loads(json.dumps(SLAVE_REC)))
        _write(tmp_path, 200, json.loads(json.dumps(MASTER_REC)))
        stats = align(tmp_path, _loader, {100: "IS1", 200: "IS1"}, dry_run=True)
        assert stats["reused"] == [(200, 100)]
        assert json.loads((tmp_path / "progress_100.json").read_text(encoding="utf-8")) == (
            SLAVE_REC
        )
        assert not list(tmp_path.glob("duplicate_align_backup_*"))
        assert not list(tmp_path.glob("duplicate_borderline_*"))
