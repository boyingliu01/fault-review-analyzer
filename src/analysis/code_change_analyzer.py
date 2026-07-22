"""代码变更分析器 - 解析代码变更记录并提取关键信息"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from loguru import logger

from src.core.models import CodeChange

FILE_TYPE_MAP = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".xml": "xml",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sh": "shell",
}

CODE_PATTERNS = {
    "database_connection": [
        r"getConnection\(\)",
        r"Connection\s+\w+\s*=",
        r"Statement\s+\w+\s*=",
    ],
    "exception_handling": [
        r"catch\s*\([^)]+\)\s*\{",
        r"throw\s+new",
        r"throws\s+\w+",
    ],
    "null_check": [
        r"if\s*\(\s*\w+\s*==\s*null\s*\)",
        r"Objects\.requireNonNull",
        r"Optional\.of",
    ],
    "concurrency": [
        r"synchronized\s*\(",
        r"new\s+Thread\(",
        r"ExecutorService",
        r"ConcurrentHashMap",
    ],
    "sql_injection": [
        r"\+\s*[\"'].*\%s",
        r"executeQuery\s*\(\s*[\"'].*\+",
    ],
}


class CodeChangeAnalyzer:
    """代码变更分析器 - 解析commit和diff，提取关键信息"""

    def __init__(self, llm_provider: Any | None = None) -> None:
        self._file_type_map = FILE_TYPE_MAP
        self._llm_provider = llm_provider

    def parse_commits(self, commits: list[dict[str, Any]]) -> list[CodeChange]:
        """解析commit列表

        Args:
            commits: commit信息字典列表

        Returns:
            list[CodeChange]: 代码变更列表
        """
        result = []
        for commit in commits:
            try:
                timestamp_str = commit.get("timestamp", "")
                if isinstance(timestamp_str, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    except ValueError:
                        timestamp = datetime.now()
                elif isinstance(timestamp_str, datetime):
                    timestamp = timestamp_str
                else:
                    timestamp = datetime.now()

                code_change = CodeChange(
                    commit_id=commit.get("commit_id", ""),
                    author=commit.get("author", ""),
                    timestamp=timestamp,
                    message=commit.get("message", ""),
                    diff=commit.get("diff", ""),
                    files_changed=commit.get("files_changed", []),
                    branch=commit.get("branch", ""),
                    repository=commit.get("repository", ""),
                )
                result.append(code_change)
            except Exception as e:
                logger.warning(f"解析commit失败: {e}")
                continue

        return result

    def analyze_diff(self, diff: str) -> dict[str, Any]:
        """分析代码diff

        Args:
            diff: diff文本

        Returns:
            dict: diff分析结果
        """
        if not diff:
            return {
                "added_lines": 0,
                "removed_lines": 0,
                "modified_lines": 0,
                "files_added": 0,
                "files_removed": 0,
                "files_modified": 0,
            }

        added_lines = len(re.findall(r"^\+[^+]", diff, re.MULTILINE))
        removed_lines = len(re.findall(r"^-[^-]", diff, re.MULTILINE))

        # 支持多种 diff 格式:
        # git标准格式: +++ b/path/to/file
        # 研发云格式: +++ path/to/file (latest)
        file_changes = set(
            re.findall(r"^\+\+\+ (?:b/)?(.*?)(?:\s+\(latest\))?$", diff, re.MULTILINE)
        )
        removed_files = set(
            re.findall(r"^--- (?:a/)?(.*?)(?:\s+\(head\))?$", diff, re.MULTILINE)
        )
        # 排除 /dev/null（新增文件的旧端点）
        removed_files.discard("/dev/null")
        file_changes.discard("/dev/null")
        files_added = len(file_changes - removed_files)
        files_removed = len(removed_files - file_changes)
        files_modified = len(file_changes & removed_files)

        # 如果没有通过文件名匹配到，至少统计有变更的文件数
        if files_added + files_removed + files_modified == 0:
            # 通过 @@ hunk 头来估算文件数
            hunk_files = len(set(re.findall(r"^@@ .* @@", diff, re.MULTILINE)))
            if hunk_files > 0:
                files_modified = hunk_files

        return {
            "added_lines": added_lines,
            "removed_lines": removed_lines,
            "modified_lines": added_lines + removed_lines,
            "files_added": files_added,
            "files_removed": files_removed,
            "files_modified": files_modified,
        }

    def detect_file_types(self, files: list[str]) -> dict[str, str]:
        """检测文件类型

        Args:
            files: 文件路径列表

        Returns:
            dict: 文件路径到类型的映射
        """
        result = {}
        for file_path in files:
            ext = ""
            if "." in file_path:
                ext = "." + file_path.rsplit(".", 1)[1]
            result[file_path] = self._file_type_map.get(ext.lower(), "unknown")
        return result

    def identify_changed_modules(self, files: list[str]) -> list[str]:
        """识别变更模块

        Args:
            files: 文件路径列表

        Returns:
            list: 模块路径列表
        """
        modules = set()
        for file_path in files:
            parts = file_path.replace("\\", "/").split("/")
            if len(parts) >= 2 and parts[0] == "src":
                module_path = "/".join(parts[:2])
                modules.add(module_path)
            elif len(parts) >= 1 and parts[0] != "tests":
                modules.add(parts[0])
        return sorted(modules)

    def generate_change_summary(self, code_changes: list[CodeChange]) -> dict[str, Any]:
        """生成变更摘要

        Args:
            code_changes: 代码变更列表

        Returns:
            dict: 变更摘要
        """
        if not code_changes:
            return {
                "total_commits": 0,
                "total_files_changed": 0,
                "authors": [],
                "modules": [],
                "file_types": {},
            }

        all_files = []
        all_authors = set()
        for change in code_changes:
            all_files.extend(change.files_changed)
            if change.author:
                all_authors.add(change.author)

        file_types = self.detect_file_types(all_files)
        type_counts: dict[str, int] = {}
        for ftype in file_types.values():
            type_counts[ftype] = type_counts.get(ftype, 0) + 1

        modules = self.identify_changed_modules(all_files)

        return {
            "total_commits": len(code_changes),
            "total_files_changed": len(set(all_files)),
            "authors": sorted(all_authors),
            "modules": modules,
            "file_types": type_counts,
        }

    def extract_code_patterns(self, diff: str) -> list[dict[str, Any]]:
        """提取代码模式

        Args:
            diff: diff文本

        Returns:
            list: 检测到的代码模式列表
        """
        patterns_found = []

        for pattern_name, pattern_list in CODE_PATTERNS.items():
            for pattern in pattern_list:
                if re.search(pattern, diff, re.IGNORECASE):
                    patterns_found.append(
                        {
                            "type": pattern_name,
                            "pattern": pattern,
                            "matched": True,
                        }
                    )
                    break

        return patterns_found

    def analyze_code_changes(self, commits: list[dict[str, Any]]) -> dict[str, Any]:
        """综合分析代码变更

        Args:
            commits: commit信息列表

        Returns:
            dict: 综合分析结果
        """
        code_changes = self.parse_commits(commits)

        summary = self.generate_change_summary(code_changes)

        all_patterns = []
        all_diffs = []

        for change in code_changes:
            if change.diff:
                diff_analysis = self.analyze_diff(change.diff)
                all_diffs.append(diff_analysis)
                patterns = self.extract_code_patterns(change.diff)
                all_patterns.extend(patterns)

        total_added = sum(d.get("added_lines", 0) for d in all_diffs)
        total_removed = sum(d.get("removed_lines", 0) for d in all_diffs)

        return {
            "code_changes": code_changes,
            "summary": summary,
            "diff_stats": {
                "total_added": total_added,
                "total_removed": total_removed,
            },
            "detected_patterns": all_patterns,
        }

    def generate_analysis_text(self, commits: list[dict[str, Any]]) -> str:
        """生成用于向量化和聚类的代码变更分析文本

        将代码变更的统计信息、模式检测结果等综合为一段文本，
        用于后续的embedding和聚类分析。

        Args:
            commits: commit信息列表

        Returns:
            str: 分析文本
        """
        result = self.analyze_code_changes(commits)
        summary = result["summary"]
        diff_stats = result["diff_stats"]
        patterns = result["detected_patterns"]

        parts = []

        # 基本统计
        if summary["total_commits"] > 0:
            parts.append(f"代码变更: {summary['total_commits']}次提交")
            parts.append(f"涉及{summary['total_files_changed']}个文件")

            if diff_stats["total_added"] > 0 or diff_stats["total_removed"] > 0:
                parts.append(
                    f"新增{diff_stats['total_added']}行，删除{diff_stats['total_removed']}行"
                )

            # 文件类型分布
            if summary["file_types"]:
                type_desc = ", ".join(
                    f"{k}({v})" for k, v in summary["file_types"].items()
                )
                parts.append(f"文件类型: {type_desc}")

            # 变更模块
            if summary["modules"]:
                parts.append(f"变更模块: {', '.join(summary['modules'])}")

            # 检测到的代码模式
            if patterns:
                pattern_types = [p["type"] for p in patterns]
                parts.append(f"涉及代码模式: {', '.join(set(pattern_types))}")

        # 如果有LLM，生成更深层的语义分析
        if self._llm_provider and any(c.get("diff", "") for c in commits):
            try:
                llm_analysis = self._llm_analyze_changes(commits)
                if llm_analysis:
                    parts.append(f"LLM分析: {llm_analysis}")
            except Exception as e:
                logger.debug(f"LLM代码分析失败: {e}")

        return "; ".join(parts) if parts else ""

    def _llm_analyze_changes(self, commits: list[dict[str, Any]]) -> str:
        """使用LLM对代码变更进行语义分析

        Args:
            commits: commit信息列表（含diff）

        Returns:
            str: LLM分析结果摘要
        """
        if not self._llm_provider:
            return ""

        # 构建分析输入
        diffs_summary = []
        for c in commits:
            diff = c.get("diff", "")
            if diff:
                # 截取关键部分
                diff_preview = diff[:1000]
                diffs_summary.append(
                    f"Commit: {c.get('message', '')}\n"
                    f"Files: {', '.join(c.get('files_changed', []))}\n"
                    f"Diff preview:\n{diff_preview}"
                )

        if not diffs_summary:
            return ""

        combined = "\n---\n".join(diffs_summary[:5])  # 限制输入量

        prompt = f"""你是一个代码审查专家。请分析以下代码变更，用简短的中文总结：
1. 这些变更的主要目的和功能
2. 涉及的技术领域（如数据库、API、并发、安全等）
3. 潜在的风险点

代码变更：
{combined}

请用3-5句话总结，重点关注变更的性质和风险。"""

        try:
            import asyncio

            if hasattr(self._llm_provider, "generate"):
                result = self._llm_provider.generate(prompt)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop and loop.is_running():
                        # 已在异步事件循环中，无法同步等待，跳过 LLM 分析
                        logger.warning("LLM分析跳过: 已在异步事件循环中")
                        return ""
                    result = asyncio.run(result)
                return str(result)[:500]
        except Exception as e:
            logger.warning(f"LLM分析失败: {e}")

        return ""
