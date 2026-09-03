"""Diff 文本处理工具。

规范违规检测只应针对"本次新增的代码"：unified diff 中的删除行（- 行）
是本次被移除的代码、上下文行（空格开头）是未变更的历史代码，混入检测
范围会把历史代码/已删除代码误判为本次引入的违规（如 11964851 的
"若加密"误报，词边界修复只解决了一半，另一半就是删除行混入）。
"""

from __future__ import annotations

import re

# unified diff 元数据行前缀（不参与内容检测）
_DIFF_META_PREFIXES: tuple[str, ...] = (
    "diff --git",
    "index ",
    "old mode ",
    "new mode ",
    "similarity index ",
    "dissimilarity index ",
    "rename from ",
    "rename to ",
    "copy from ",
    "copy to ",
    "Binary files ",
    "GIT binary patch",
    "deleted file mode ",
    "new file mode ",
)

# hunk 头：@@ -l,c +l,c @@（行尾可带函数上下文）
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")

# 测试/mock 文件特征：目录段（__tests__/test/tests/mocks/fixtures/spec/e2e）
# 或 jest 风格后缀（.test.js / .spec.ts 等）。其中的 mock 凭证、示例值
# 不部署到生产，不构成"敏感信息硬编码"等生产环境违规。
_TEST_FILE_PATTERN = re.compile(
    r"(?:^|/)(?:__tests?__|tests?|mocks?|fixtures?|spec|e2e)(?:/|$)"
    r"|\.(?:test|spec)\.[^.]+$",
    re.IGNORECASE,
)


def is_test_file(file_path: str) -> bool:
    """判断文件是否为测试/mock 文件（如 __tests__/DeepLink.test.js）。"""
    if not file_path:
        return False
    return bool(_TEST_FILE_PATTERN.search(file_path.replace("\\", "/")))


def _parse_diff_new_path(line: str) -> str:
    """解析 ``+++ b/path/to/file`` 行中的文件路径。"""
    path = line[len("+++ ") :].strip().strip('"')
    if path.startswith("b/"):
        path = path[2:]
    if path == "/dev/null":
        return ""
    return path


def iter_added_lines_by_file(diff_text: str) -> list[tuple[str, str]]:
    """按文件段拆分 unified diff，返回 ``(文件路径, 该文件新增行)`` 列表。

    用于需要文件上下文的检测（如跳过测试/mock 文件）。非 unified diff
    文本返回 ``[("", 原文)]``——此类文本没有文件语义，调用方不应按
    路径跳过。新增行为空的文件段不返回。
    """
    if not diff_text:
        return []
    if not _looks_like_unified_diff(diff_text):
        return [("", diff_text)]

    segments: list[tuple[str, str]] = []
    current_path = ""
    current_buf: list[str] = []

    def _flush() -> None:
        if current_buf:
            added = extract_added_lines("\n".join(current_buf))
            if added:
                segments.append((current_path, added))
            current_buf.clear()

    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            _flush()
            current_path = _parse_diff_new_path(line)
            continue
        if line.startswith("--- "):
            # --- 行属于即将开始的新文件段，不进缓冲
            continue
        current_buf.append(line)
    _flush()
    return segments


def _looks_like_unified_diff(text: str) -> bool:
    """判断文本是否为 unified diff 格式（而非裸代码片段/普通文本）。"""
    for line in text.splitlines():
        if line.startswith("diff --git ") or _HUNK_HEADER.match(line):
            return True
    return False


def extract_added_lines(diff_text: str) -> str:
    """从 unified diff 中提取新增行（+ 行）。

    处理规则：
    - 跳过 diff 元数据行（diff --git/index/---/+++/@@ 等）
    - 跳过删除行（- 行）与上下文行（空格开头）
    - 保留新增行并去掉行首的 ``+`` 前缀

    若文本不是 unified diff（如裸代码片段、commit message），则原样
    返回——调用方传入的此类文本本身没有 diff 语义，不应被过滤。
    """
    if not diff_text:
        return ""
    if not _looks_like_unified_diff(diff_text):
        return diff_text

    added: list[str] = []
    for line in diff_text.splitlines():
        if not line:
            continue
        if line.startswith(("--- ", "+++ ")) or _HUNK_HEADER.match(line):
            continue
        if line.startswith(_DIFF_META_PREFIXES):
            continue
        if line.startswith("\\"):
            # "\ No newline at end of file"
            continue
        if line.startswith("+"):
            added.append(line[1:])
        # 其余（- 删除行、空格开头的上下文行）不参与检测
    return "\n".join(added)


def extract_removed_lines(diff_text: str) -> str:
    """从 unified diff 中提取删除行（- 行，即修复前代码）。

    处理规则与 extract_added_lines 对称：
    - 跳过 diff 元数据行（diff --git/index/---/+++/@@ 等）
    - 跳过新增行（+ 行）与上下文行（空格开头）
    - 保留删除行并去掉行首的 ``-`` 前缀

    若文本不是 unified diff（如裸代码片段、commit message），则原样
    返回——调用方传入的此类文本本身没有 diff 语义，不应被过滤。
    """
    if not diff_text:
        return ""
    if not _looks_like_unified_diff(diff_text):
        return diff_text

    removed: list[str] = []
    for line in diff_text.splitlines():
        if not line:
            continue
        # "--- " 是文件元数据行，虽以 - 开头但不是删除行（须先于 - 行判断）
        if line.startswith(("--- ", "+++ ")) or _HUNK_HEADER.match(line):
            continue
        if line.startswith(_DIFF_META_PREFIXES):
            continue
        if line.startswith("\\"):
            # "\ No newline at end of file"
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        # 其余（+ 新增行、空格开头的上下文行）不进修复前代码
    return "\n".join(removed)
