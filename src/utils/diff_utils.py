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
