"""
pytest 全局配置和共享 fixture。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path 中，测试时可直接 import server.app
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))


@pytest.fixture
def sample_diff() -> str:
    """提供一段示例 unified diff，用于测试 Agent 调用。"""
    return """diff --git a/src/auth.py b/src/auth.py
index abc123..def456 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,7 +10,7 @@ def login(username: str, password: str) -> bool:
     conn = get_db()
-    query = "SELECT * FROM users WHERE name = '" + username + "'"
+    query = f"SELECT * FROM users WHERE name = '{username}'"
     result = conn.execute(query)
     return result is not None"""


@pytest.fixture
def sample_code_context() -> str:
    """提供一段示例代码上下文，模拟 tree-sitter 输出。"""
    return """函数: login(username: str, password: str) -> bool
文件: src/auth.py:10
调用关系:
  login → get_db
  login → conn.execute"""


@pytest.fixture
def valid_agent_json() -> str:
    """返回一个合法的 Agent JSON 响应（模拟 LLM 返回）。"""
    return (
        '{"agent": "security", "findings": ['
        '{"file": "src/auth.py", "line": 13, "severity": "high", '
        '"category": "sql-injection", '
        '"title": "SQL注入风险", '
        '"description": "username 参数直接拼接到 SQL 查询中", '
        '"suggestion": "使用参数化查询替换字符串拼接"}]}'
    )
