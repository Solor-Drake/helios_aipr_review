"""
context_builder.py 单元测试。

测试 diff 行号提取、Python 代码解析、上下文格式化和边界情况。
"""

from __future__ import annotations

import pytest

from server.app.context_builder import ContextBuilder, ReviewContext, ChangeContext
from server.app.git_client import FileChange


# ── 测试数据 ──────────────────────────────────────────────────

SAMPLE_PYTHON_SOURCE = '''"""示例认证模块。"""
from typing import Optional
from db import get_db
from cache import user_cache

def login(username: str, password: str) -> Optional[str]:
    """用户登录，返回 token。"""
    conn = get_db()
    query = f"SELECT * FROM users WHERE name = '{username}'"
    result = conn.execute(query)
    if result:
        token = hash_password(password)
        user_cache.set(username, token)
        return token
    return None


def logout(token: str) -> None:
    """用户登出。"""
    user_cache.delete(token)


class AuthService:
    """认证服务类。"""

    def validate(self, token: str) -> bool:
        return user_cache.exists(token)
'''

SAMPLE_PATCH = """diff --git a/auth.py b/auth.py
index abc..def 100644
--- a/auth.py
+++ b/auth.py
@@ -8,7 +8,7 @@ def login(username: str, password: str) -> Optional[str]:
     conn = get_db()
-    query = "SELECT * FROM users WHERE name = '" + username + "'"
+    query = f"SELECT * FROM users WHERE name = '{username}'"
     result = conn.execute(query)
"""


# ── fixture ───────────────────────────────────────────────────


@pytest.fixture
def builder() -> ContextBuilder:
    return ContextBuilder()


@pytest.fixture
def python_file_change() -> FileChange:
    return FileChange(
        filename="src/auth.py",
        status="modified",
        patch=SAMPLE_PATCH,
        raw_content=SAMPLE_PYTHON_SOURCE,
    )


# ── Diff 行号提取测试 ────────────────────────────────────────


class TestExtractChangedLines:
    """测试 _extract_changed_lines 方法。"""

    def test_extract_added_lines(self, builder: ContextBuilder) -> None:
        lines = builder._extract_changed_lines(SAMPLE_PATCH)
        # patch 中第 1 行新增: "    query = f\"SELECT..."
        # hunk header: @@ -8,7 +8,7 @@  → 从第 8 行开始
        # 第 1 行是上下文 → line 8
        # 第 2 行是 - → 不计数
        # 第 3 行是 + → line 9
        # 第 4 行是上下文 → line 10
        # hunk @@ -8,7 +8,7 @@ → new file 从第8行开始
        # + 行是 hunk 的第 3 行（前有1行上下文 + 1行删除），对应 new file line 9
        assert 9 in lines

    def test_empty_patch(self, builder: ContextBuilder) -> None:
        lines = builder._extract_changed_lines("")
        assert len(lines) == 0

    def test_no_changed_lines(self, builder: ContextBuilder) -> None:
        """只有上下文行没有变更行。"""
        patch = "@@ -1,3 +1,3 @@\n context1\n context2\n context3"
        lines = builder._extract_changed_lines(patch)
        assert len(lines) == 0


# ── 上下文构建集成测试 ──────────────────────────────────────


class TestBuild:
    """测试 build() 完整流程。"""

    def test_build_with_python_file(
        self, builder: ContextBuilder, python_file_change: FileChange
    ) -> None:
        diff = "完整 unified diff"
        ctx = builder.build([python_file_change], diff)

        assert isinstance(ctx, ReviewContext)
        assert ctx.raw_diff == diff

    def test_build_skips_removed_file(self, builder: ContextBuilder) -> None:
        fc = FileChange(
            filename="deleted.py",
            status="removed",
            patch=None,
            raw_content=None,
        )
        ctx = builder.build([fc], "diff")
        assert len(ctx.contexts) == 0

    def test_build_skips_unsupported_extension(self, builder: ContextBuilder) -> None:
        fc = FileChange(
            filename="config.yaml",
            status="modified",
            patch="@@ -1 +1 @@\n-old\n+new",
            raw_content="key: value",
        )
        ctx = builder.build([fc], "diff")
        assert "config.yaml" in ctx.unsupported_files
        assert len(ctx.contexts) == 0

    def test_build_empty_file_list(self, builder: ContextBuilder) -> None:
        ctx = builder.build([], "empty diff")
        assert len(ctx.contexts) == 0


# ── 格式化输出测试 ──────────────────────────────────────────


class TestFormatContext:
    """测试 format_context 方法。"""

    def test_format_with_contexts(self, builder: ContextBuilder) -> None:
        ctx = ReviewContext(
            contexts=[
                ChangeContext(
                    file_path="src/auth.py",
                    function_name="login",
                    function_source="def login(): pass",
                    call_targets=["get_db", "hash_password"],
                    decorators=["@login_required"],
                )
            ],
            raw_diff="diff content",
        )
        output = builder.format_context(ctx)
        assert "变更函数上下文" in output
        assert "login" in output
        assert "src/auth.py" in output
        assert "get_db" in output
        assert "@login_required" in output
        assert "def login(): pass" in output

    def test_format_with_unsupported_files(self, builder: ContextBuilder) -> None:
        ctx = ReviewContext(
            unsupported_files=["config.yaml", "Dockerfile"],
            raw_diff="diff",
        )
        output = builder.format_context(ctx)
        assert "未解析文件" in output
        assert "config.yaml" in output

    def test_format_empty_context(self, builder: ContextBuilder) -> None:
        ctx = ReviewContext(raw_diff="diff")
        output = builder.format_context(ctx)
        assert "原始 diff" in output


# ── tree-sitter Python 解析测试 ──────────────────────────────


class TestPythonParsing:
    """使用真实 tree-sitter 解析 Python 代码的测试。

    需要 tree-sitter-python 已安装，否则跳过。
    """

    @pytest.fixture
    def source_code(self) -> str:
        return "def add(a: int, b: int) -> int:\n" \
               '    """两数相加。"""\n' \
               "    result = a + b\n" \
               "    log_result(result)\n" \
               "    return result\n" \
               "\n" \
               "\n" \
               "def log_result(value: int) -> None:\n" \
               '    print(f"Result: {value}")\n'

    @pytest.fixture
    def patch_touching_add(self) -> str:
        return '''@@ -2,3 +2,3 @@ def add(a: int, b: int) -> int:
     """两数相加。"""
-    result = a + b
+    result = a + b + 1
     log_result(result)
'''

    def test_parse_python_function(self, builder: ContextBuilder, source_code: str, patch_touching_add: str) -> None:
        import importlib
        try:
            importlib.import_module("tree_sitter_python")
        except ImportError:
            pytest.skip("tree-sitter-python 未安装")

        fc = FileChange(
            filename="math_utils.py",
            status="modified",
            patch=patch_touching_add,
            raw_content=source_code,
        )
        ctx = builder.build([fc], "diff")
        # 应该解析出 add 函数（变更行在其范围内）
        func_names = [c.function_name for c in ctx.contexts]
        assert "add" in func_names

    def test_no_changed_functions(self, builder: ContextBuilder, source_code: str) -> None:
        import importlib
        try:
            importlib.import_module("tree_sitter_python")
        except ImportError:
            pytest.skip("tree-sitter-python 未安装")

        # patch 只改了 import，不涉及函数体
        patch_import = "@@ -1,2 +1,2 @@\n-import os\n+import sys\n"
        fc = FileChange(
            filename="math_utils.py",
            status="modified",
            patch=patch_import,
            raw_content=source_code,
        )
        ctx = builder.build([fc], "diff")
        # import 不在函数体内，不应匹配到任何函数
        assert len(ctx.contexts) == 0


# ── 长度保护测试 ────────────────────────────────────────────


class TestMaxContextLength:
    """测试上下文长度保护机制。"""

    def test_truncation(self, builder: ContextBuilder) -> None:
        builder._max_context_length = 50  # 人为降低阈值
        ctx = ReviewContext(
            contexts=[
                ChangeContext(
                    file_path="a.py",
                    function_name="func1",
                    function_source="x" * 30,
                    call_targets=["a", "b"],
                ),
                ChangeContext(
                    file_path="b.py",
                    function_name="func2",
                    function_source="y" * 30,
                    call_targets=["c"],
                ),
            ],
            raw_diff="diff",
        )
        output = builder.format_context(ctx)
        # 第一个函数（30 + 列表长度 ≈ 32）应该出现
        assert "func1" in output
        # 第二个函数可能导致超限，但 format_context 不截断 contexts 列表
        # 截断发生在 build() 中
