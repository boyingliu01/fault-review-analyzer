"""extract_added_lines 单元测试（A1：diff 删除行/上下文行过滤）。

背景：规范违规检测曾把 diff 删除行与上下文行一并当作"存在的代码"检测，
导致历史代码/被删除代码被误判为本次引入的违规（11964851 "若加密"误报
的成因之一）。
"""

from src.utils.diff_utils import (
    extract_added_lines,
    extract_removed_lines,
    is_test_file,
    iter_added_lines_by_file,
)

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
    '+System.out.println("added debug");\n'
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


class TestExtractRemovedLines:
    """结论域复审材料补全：提取删除行（- 行，即修复前代码）。

    219 条撤销理由中 77 条「缺修复前代码」：build_fault_info 此前只喂
    + 行，专家看不到修复前代码，以「未提供修复前代码」为由撤销结论。
    引入单号非必填，引入单信息只是辅助证据；删除行提取让故障单自身
    携带的修复前代码进入材料（用户裁定：缺失辅助信息不构成撤销理由）。
    """

    def test_unified_diff_keeps_removed_only(self):
        """unified diff 只保留删除行（- 行）"""
        result = extract_removed_lines(UNIFIED_DIFF)
        lines = result.splitlines()
        assert "oldPassword = 'Removed123';" in lines

    def test_unified_diff_drops_added_and_context(self):
        """unified diff 过滤新增行、上下文行与元数据行"""
        result = extract_removed_lines(UNIFIED_DIFF)
        assert "newPassword = 'Added999';" not in result
        assert 'System.out.println("added debug");' not in result
        assert "context line stays" not in result
        assert "another context" not in result
        assert "diff --git" not in result
        assert "@@" not in result
        # "--- a/..." 以 - 开头但属文件元数据行，不是删除行
        assert "--- a/src/App.java" not in result
        assert "index 3f2a1b" not in result

    def test_removed_minus_prefix_stripped(self):
        """删除行的 - 前缀应被去除"""
        result = extract_removed_lines(UNIFIED_DIFF)
        assert "-oldPassword" not in result

    def test_multi_deletions_preserved_in_order(self):
        """连续多行删除应全部保留且保序"""
        diff = (
            "diff --git a/src/App.java b/src/App.java\n"
            "--- a/src/App.java\n"
            "+++ b/src/App.java\n"
            "@@ -10,3 +10,3 @@ public class App {\n"
            "-old line one\n"
            "-old line two\n"
            "+new line\n"
            " context stays\n"
        )
        assert extract_removed_lines(diff).splitlines() == ["old line one", "old line two"]

    def test_bare_code_passthrough(self):
        """裸代码片段（非 unified diff）原样返回，不做过滤"""
        code = "password = 'PlainText1';\nkey = 'x';"
        assert extract_removed_lines(code) == code

    def test_commit_message_passthrough(self):
        """commit message 等普通文本原样返回"""
        msg = "fix: resolve null pointer issue"
        assert extract_removed_lines(msg) == msg

    def test_empty_input(self):
        assert extract_removed_lines("") == ""

    def test_no_newline_marker_skipped(self):
        """\\ No newline at end of file 标记行应被跳过"""
        diff = UNIFIED_DIFF + "\\ No newline at end of file\n"
        result = extract_removed_lines(diff)
        assert "No newline" not in result


MULTI_FILE_DIFF = (
    "diff --git a/src/Service.java b/src/Service.java\n"
    "index 111..222 100644\n"
    "--- a/src/Service.java\n"
    "+++ b/src/Service.java\n"
    "@@ -1,2 +1,3 @@\n"
    "+serviceCode();\n"
    "diff --git a/src/pkg/__tests__/Util.test.js b/src/pkg/__tests__/Util.test.js\n"
    "index 333..444 100644\n"
    "--- a/src/pkg/__tests__/Util.test.js\n"
    "+++ b/src/pkg/__tests__/Util.test.js\n"
    "@@ -1 +1,2 @@\n"
    "+const token = 'tok-mock9';\n"
    "diff --git a/README.md b/README.md\n"
    "index 555..666 100644\n"
    "--- a/README.md\n"
    "+++ b/README.md\n"
    "@@ -1 +1,2 @@\n"
    "+readme text\n"
)


class TestIterAddedLinesByFile:
    def test_split_by_file_segments(self):
        """多文件 diff 应按文件段拆分"""
        segments = iter_added_lines_by_file(MULTI_FILE_DIFF)
        paths = [p for p, _ in segments]
        assert paths == ["src/Service.java", "src/pkg/__tests__/Util.test.js", "README.md"]

    def test_added_lines_per_file(self):
        """每个文件段的文本只含该文件的新增行"""
        segments = dict(iter_added_lines_by_file(MULTI_FILE_DIFF))
        assert segments["src/Service.java"] == "serviceCode();"
        assert segments["src/pkg/__tests__/Util.test.js"] == "const token = 'tok-mock9';"
        assert segments["README.md"] == "readme text"

    def test_bare_code_no_file_semantics(self):
        """非 unified diff 文本返回空路径段（调用方不应按路径跳过）"""
        segments = iter_added_lines_by_file("password = 'Plain123';")
        assert segments == [("", "password = 'Plain123';")]

    def test_empty_input(self):
        assert iter_added_lines_by_file("") == []


class TestIsTestFile:
    def test_jest_test_dir(self):
        assert is_test_file("src/deeplink/__tests__/DeepLink.test.js")

    def test_test_suffix(self):
        assert is_test_file("src/service.test.ts")
        assert is_test_file("src/service.spec.ts")

    def test_test_dir_variants(self):
        assert is_test_file("tests/test_service.py")
        assert is_test_file("test/java/com/x/AppTest.java")
        assert is_test_file("mocks/store.js")
        assert is_test_file("e2e/login.spec.js")

    def test_production_files_not_flagged(self):
        assert not is_test_file("src/service/TokenService.java")
        assert not is_test_file("src/utils/test_utils.py")  # 工具文件不是测试目录
        assert not is_test_file("pkg/latest.js")  # latest 含 "test" 子串但非段级匹配

    def test_empty_path(self):
        assert not is_test_file("")
        assert not is_test_file(None)  # type: ignore[arg-type]
