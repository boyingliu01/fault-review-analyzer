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

    def __init__(self) -> None:
        self._file_type_map = FILE_TYPE_MAP

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

        file_changes = re.findall(r"^\+\+\+ b/(.*)$", diff, re.MULTILINE)
        files_added = len(
            [f for f in file_changes if f not in re.findall(r"^--- a/(.*)$", diff, re.MULTILINE)]
        )

        return {
            "added_lines": added_lines,
            "removed_lines": removed_lines,
            "modified_lines": added_lines + removed_lines,
            "files_added": files_added,
            "files_removed": 0,
            "files_modified": len(set(file_changes)),
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
