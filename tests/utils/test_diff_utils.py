"""extract_added_lines 单元测试（A1：diff 删除行/上下文行过滤）。

背景：规范违规检测曾把 diff 删除行与上下文行一并当作"存在的代码"检测，
导致历史代码/被删除代码被误判为本次引入的违规（11964851 "若加密"误报
的成因之一）。
"""

from src.utils.diff_utils import extract_added_lines

UNIFIED_DIFF = (
    "diff --git a/src/App.java b/src/App.java\n"
    "index 3f2a1b..9c8d7e 100644\n"
    "--- a/src/App.java\n"
    "+++ b/src/App.java\n"
    "@@ -10,7 +10,7 @@ public class App {\n"
    " context line stays\n"
    "-oldPassword = 'Removed123';\n"
    "+newPassword = 'Added999';\n"
    " another context\n"
    "+System.out.println(\"added debug\");\n"
)


class TestExtractAddedLines:
    def test_unified_diff_keeps_added_only(self):
        """unified diff 只保留新增行（+ 行）"""
        result = extract_added_lines(UNIFIED_DIFF)
        lines = result.splitlines()
        assert "newPassword = 'Added999';" in lines
        assert 'System.out.println("added debug");' in lines

    def test_unified_diff_drops_deleted_and_context(self):
        """unified diff 过滤删除行、上下文行与元数据行"""
        result = extract_added_lines(UNIFIED_DIFF)
        assert "oldPassword = 'Removed123';" not in result
        assert "context line stays" not in result
        assert "another context" not in result
        assert "diff --git" not in result
        assert "@@" not in result
        assert "--- a/src/App.java" not in result
        assert "index 3f2a1b" not in result

    def test_added_plus_prefix_stripped(self):
        """新增行的 + 前缀应被去除"""
        result = extract_added_lines(UNIFIED_DIFF)
        assert "+newPassword" not in result

    def test_bare_code_passthrough(self):
        """裸代码片段（非 unified diff）原样返回，不做过滤"""
        code = "password = 'PlainText1';\nkey = 'x';"
        assert extract_added_lines(code) == code

    def test_commit_message_passthrough(self):
        """commit message 等普通文本原样返回"""
        msg = "fix: resolve null pointer issue"
        assert extract_added_lines(msg) == msg

    def test_empty_input(self):
        assert extract_added_lines("") == ""

    def test_no_newline_marker_skipped(self):
        """\\ No newline at end of file 标记行应被跳过"""
        diff = UNIFIED_DIFF + "\\ No newline at end of file\n"
        result = extract_added_lines(diff)
        assert "No newline" not in result

    def test_new_file_mode_meta_skipped(self):
        """new file mode 等元数据行应被跳过"""
        diff = (
            "diff --git a/new.py b/new.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/new.py\n"
            "@@ -0,0 +1 @@\n"
            "+value = 1\n"
        )
        result = extract_added_lines(diff)
        assert result == "value = 1"
