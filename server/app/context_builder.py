"""
代码上下文构建模块。

使用 tree-sitter 解析代码 AST，提取变更函数定义和调用关系。
为 LLM 评审提供精简但完整的代码上下文，降低 Token 消耗。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from server.app.git_client import FileChange

logger = logging.getLogger(__name__)

# ── 语言扩展名 → tree-sitter 语言标识 ───────────────────────

# tree-sitter 各语言包的 Python 标识符，按需扩展
_EXTENSION_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
}

# 已成功加载的语言 parser 缓存
_language_cache: dict[str, Any] = {}


def _get_language(lang_name: str) -> Any | None:
    """按名称加载 tree-sitter Language 对象（带缓存）。

    首次调用时尝试 import 对应语言的 Python 包并创建 Language 对象。
    后续调用直接从缓存返回。
    """
    if lang_name in _language_cache:
        return _language_cache[lang_name]

    try:
        # tree-sitter 各语言包的导入规则：tree_sitter_<lang>
        if lang_name == "python":
            from tree_sitter_python import language as py_lang  # type: ignore[import-untyped]
        else:
            return None

        lang = py_lang()
        _language_cache[lang_name] = lang
        return lang
    except ImportError:
        logger.warning("tree-sitter 语言包未安装: %s，跳过结构化解析", lang_name)
        return None
    except Exception as exc:
        logger.warning("tree-sitter 加载 %s 失败: %s", lang_name, exc)
        return None


# ── 上下文数据结构 ────────────────────────────────────────────


@dataclass
class ChangeContext:
    """单个变更函数的上下文信息。"""

    file_path: str
    function_name: str
    function_source: str          # 函数完整源码
    call_targets: list[str] = field(default_factory=list)  # 被调用的函数名列表
    decorators: list[str] = field(default_factory=list)


@dataclass
class ReviewContext:
    """一个 PR 中所有变更文件的聚合上下文。"""

    contexts: list[ChangeContext] = field(default_factory=list)
    unsupported_files: list[str] = field(default_factory=list)  # 无法解析的文件列表
    raw_diff: str = ""


# ── 主入口 ─────────────────────────────────────────────────────


class ContextBuilder:
    """代码上下文构建器。

    接收 FileChange 列表和 diff 文本，使用 tree-sitter 解析变更文件，
    提取变更函数定义和调用关系，返回 LLM 可消费的格式化上下文。
    """

    # diff hunk 头部正则: @@ -old,count +new,count @@
    _HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    def __init__(self) -> None:
        self._max_context_length = 16000  # 上下文总长度上限，保护 Token 用量

    def build(self, file_changes: list[FileChange], diff: str) -> ReviewContext:
        """从 PR 文件变更构建评审上下文。

        Args:
            file_changes: git_client 返回的文件变更列表（含 patch 和 raw_content）。
            diff: 完整的 unified diff 文本。

        Returns:
            ReviewContext，包含结构化上下文和原始 diff。
        """
        ctx = ReviewContext(raw_diff=diff)
        total_length = 0

        for fc in file_changes:
            if fc.status == "removed":
                continue  # 被删除的文件不需要上下文

            file_ext = Path(fc.filename).suffix.lower()
            lang_name = _EXTENSION_LANG_MAP.get(file_ext)

            if lang_name is None:
                ctx.unsupported_files.append(fc.filename)
                logger.debug("不支持的文件类型: %s", fc.filename)
                continue

            lang = _get_language(lang_name)
            if lang is None:
                ctx.unsupported_files.append(fc.filename)
                continue

            source = fc.raw_content or fc.patch or ""
            if not source.strip():
                continue

            changed_lines = self._extract_changed_lines(fc.patch or "")
            contexts = self._parse_file_context(
                lang, lang_name, source, fc.filename, changed_lines
            )

            for c in contexts:
                # 长度保护：上下文过长时截断
                entry_len = len(c.function_source) + len(str(c.call_targets))
                if total_length + entry_len > self._max_context_length:
                    logger.warning("上下文总长度超限 (%d)，截断后续文件", self._max_context_length)
                    break
                ctx.contexts.append(c)
                total_length += entry_len

        logger.info(
            "构建评审上下文: %d 个变更函数, %d 个不支持文件",
            len(ctx.contexts),
            len(ctx.unsupported_files),
        )
        return ctx

    # ── diff hunk 行号解析 ──────────────────────────────────

    def _extract_changed_lines(self, patch: str) -> set[int]:
        """从 patch 文本中提取所有变更的行号（新增行）。

        只提取新增行的行号（+ 开头），因为上下文围绕新增/修改的代码展开。
        删除的代码不需要评审。
        """
        changed: set[int] = set()
        if not patch:
            return changed

        current_line = 0
        for line in patch.split("\n"):
            # 跳过 git diff 头部的 ---/+++ 行，只处理 hunk
            if line.startswith("---") or line.startswith("+++"):
                continue

            m = self._HUNK_HEADER_RE.match(line)
            if m:
                current_line = int(m.group(1))
                continue
            if line.startswith("+"):
                changed.add(current_line)
                current_line += 1
            elif line.startswith("-"):
                continue  # 不追踪删除行的行号
            else:
                current_line += 1
        return changed

    # ── tree-sitter AST 解析 ────────────────────────────────

    def _parse_file_context(
        self,
        lang: Any,
        lang_name: str,
        source_code: str,
        filename: str,
        changed_lines: set[int],
    ) -> list[ChangeContext]:
        """使用 tree-sitter 解析单个文件，提取变更函数的上下文。

        Args:
            lang: tree-sitter Language 对象。
            lang_name: 语言名（用于创建 Parser）。
            source_code: 文件源代码。
            filename: 文件名。
            changed_lines: 变更行号集合。

        Returns:
            ChangeContext 列表，每个对应一个变更函数。
        """
        try:
            from tree_sitter import Parser, Language
        except ImportError:
            logger.warning("tree-sitter 未安装")
            return []

        parser = Parser(Language(lang))
        source_bytes = source_code.encode("utf-8")
        tree = parser.parse(source_bytes)

        # 查找包含变更行的所有函数/方法节点
        changed_functions: set[str] = set()
        contexts: list[ChangeContext] = []

        root = tree.root_node

        # 定位所有函数/方法定义
        func_nodes = self._find_function_nodes(root, lang_name, source_bytes)

        for func_node in func_nodes:
            start_line = func_node.start_point[0] + 1
            end_line = func_node.end_point[0] + 1

            # 检查该函数是否与变更行号有交集
            func_range = set(range(start_line, end_line + 1))
            if not func_range.intersection(changed_lines):
                continue

            func_name = self._extract_func_name(func_node, lang_name, source_bytes)
            if func_name in changed_functions:
                continue  # 重载或重复定义（已在同一文件出现）跳过
            changed_functions.add(func_name)

            func_source = func_node.text.decode("utf-8")
            call_targets = self._extract_call_targets(
                func_node, lang_name, source_bytes
            )
            decorators = self._extract_decorators(func_node, lang_name)

            contexts.append(ChangeContext(
                file_path=filename,
                function_name=func_name,
                function_source=func_source,
                call_targets=call_targets,
                decorators=decorators,
            ))

        return contexts

    def _find_function_nodes(
        self, root: Any, lang_name: str, source: bytes
    ) -> list[Any]:
        """递归查找 AST 中的所有函数/方法定义节点。"""
        func_nodes: list[Any] = []
        node_types = {"function_definition", "function_declaration", "method_definition"}

        def walk(node: Any) -> None:
            if node.type in node_types:
                func_nodes.append(node)
            for child in node.children:
                walk(child)

        walk(root)
        return func_nodes

    def _extract_func_name(
        self, func_node: Any, lang_name: str, source: bytes
    ) -> str:
        """从函数节点提取函数名。"""
        for child in func_node.children:
            if child.type in ("identifier", "name"):
                return child.text.decode("utf-8")
        return func_node.text.decode("utf-8")[:50]  # fallback

    def _extract_call_targets(
        self, func_node: Any, lang_name: str, source: bytes
    ) -> list[str]:
        """从函数体内提取所有被调用的函数名。"""
        calls: set[str] = set()
        call_patterns = {
            "call": "function",
            "method_invocation": "name",
        }

        def walk(node: Any) -> None:
            for pattern_node_type, child_field in call_patterns.items():
                if node.type == pattern_node_type:
                    for child in node.children:
                        if child.type == child_field or child.type == "identifier":
                            calls.add(child.text.decode("utf-8"))
                            break
                        if child.type == "attribute":
                            # obj.method() 格式
                            attr_text = child.text.decode("utf-8")
                            calls.add(attr_text)
                            break
            for child in node.children:
                walk(child)

        walk(func_node)
        # 去重并排序，排除内置函数（减少噪音）
        builtins = {"print", "len", "range", "int", "str", "float", "list",
                     "dict", "set", "tuple", "bool", "type", "isinstance",
                     "hasattr", "getattr", "setattr", "enumerate", "zip",
                     "map", "filter", "sorted", "reversed", "open", "super"}
        return sorted(c for c in calls if c not in builtins)

    def _extract_decorators(
        self, func_node: Any, lang_name: str
    ) -> list[str]:
        """提取函数上的装饰器列表。"""
        decorators: list[str] = []
        prev_siblings = []

        # 收集函数之前的兄弟节点（装饰器通常在函数前面）
        parent = func_node.parent
        if parent is None:
            return decorators

        found_func = False
        for child in reversed(parent.children):
            if child == func_node:
                found_func = True
                continue
            if found_func and child.type == "decorator":
                decorators.insert(0, child.text.decode("utf-8"))
            elif found_func and child.type != "decorator":
                break

        return decorators

    # ── 格式化输出 ──────────────────────────────────────────

    def format_context(self, review_ctx: ReviewContext) -> str:
        """将 ReviewContext 格式化为 LLM 可直接消费的文本。

        Args:
            review_ctx: build() 返回的上下文对象。

        Returns:
            格式化的上下文字符串，可直接嵌入 Agent 的 User Prompt。
        """
        lines: list[str] = []

        if review_ctx.contexts:
            lines.append("## 变更函数上下文")
            lines.append("")
            for i, c in enumerate(review_ctx.contexts, 1):
                lines.append(f"### {i}. {c.function_name} ({c.file_path})")
                if c.decorators:
                    lines.append(f"装饰器: {', '.join(c.decorators)}")
                if c.call_targets:
                    lines.append(f"调用: {', '.join(c.call_targets)}")
                lines.append("")
                lines.append("```python")
                lines.append(c.function_source)
                lines.append("```")
                lines.append("")

        if review_ctx.unsupported_files:
            lines.append("## 未解析文件（tree-sitter 不支持，仅提供 diff）")
            for f in review_ctx.unsupported_files:
                lines.append(f"- {f}")
            lines.append("")

        if not review_ctx.contexts:
            lines.append("## 代码上下文（无结构化上下文，使用原始 diff）")
            lines.append("")

        return "\n".join(lines)
