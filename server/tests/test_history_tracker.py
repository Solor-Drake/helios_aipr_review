"""
history_tracker.py 单元测试。

测试 SQLite 存储、历史查询和修复验证对比。
使用内存 SQLite（:memory:）隔离测试。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from server.app.history_tracker import HistoryTracker
from server.app.models import (
    ReviewFinding,
    AgentType,
    Severity,
    RiskLevel,
    RepairStatus,
)


def _finding(
    file: str = "a.py",
    line: int = 1,
    title: str = "test",
) -> ReviewFinding:
    """创建测试用 ReviewFinding。"""
    return ReviewFinding(
        agent=AgentType.SECURITY,
        severity=Severity.MEDIUM,
        risk_level=RiskLevel.YELLOW,
        repair_status=RepairStatus.NEW,
        file=file,
        line=line,
        title=title,
        description="desc",
        suggestion="fix",
        category="test",
    )


# ── fixture ───────────────────────────────────────────────────


@pytest.fixture
def tracker() -> HistoryTracker:
    """创建使用临时文件的 HistoryTracker。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tracker = HistoryTracker.__new__(HistoryTracker)
        tracker._db_path = str(Path(tmpdir) / "test.db")
        tracker._init_db()
        yield tracker


# ── 存储和查询测试 ──────────────────────────────────────────


class TestSaveAndGet:
    """测试 save() 和 get_history()。"""

    @pytest.mark.asyncio
    async def test_save_and_query(self, tracker: HistoryTracker) -> None:
        findings = [_finding(title="SQL注入")]
        await tracker.save(
            "task-001",
            "https://github.com/o/r/pull/1",
            findings,
            "共发现 1 个问题",
        )

        records = await tracker.get_history("https://github.com/o/r/pull/1")
        assert len(records) == 1
        assert records[0]["task_id"] == "task-001"
        assert "SQL注入" in records[0]["findings_json"]

    @pytest.mark.asyncio
    async def test_get_history_empty(self, tracker: HistoryTracker) -> None:
        records = await tracker.get_history("https://github.com/o/r/pull/999")
        assert len(records) == 0


# ── 修复验证对比测试 ────────────────────────────────────────


class TestCompare:
    """测试 compare() 修复验证。"""

    @pytest.mark.asyncio
    async def test_compare_no_history(self, tracker: HistoryTracker) -> None:
        """无历史记录时，所有发现标记为 new。"""
        current = [_finding()]
        result = await tracker.compare("https://github.com/o/r/pull/1", current)
        assert result.comparison.new_count == 1
        assert result.comparison.fixed_count == 0
        assert result.comparison.unresolved_count == 0
        assert len(result.new_items) == 1

    @pytest.mark.asyncio
    async def test_compare_fixed_and_new(self, tracker: HistoryTracker) -> None:
        """上次有 bug-A，本次只有 bug-B：bug-A 已修复，bug-B 新引入。"""
        # 保存第一次评审
        old_findings = [_finding(file="a.py", line=10, title="bug-A")]
        await tracker.save(
            "task-001", "https://github.com/o/r/pull/1",
            old_findings, "1 个问题",
        )

        # 第二次评审发现不同的问题
        new_findings = [_finding(file="b.py", line=20, title="bug-B")]
        result = await tracker.compare(
            "https://github.com/o/r/pull/1", new_findings,
        )

        assert result.comparison.fixed_count == 1
        assert result.comparison.new_count == 1
        assert result.comparison.unresolved_count == 0
        assert result.fixed_items[0].title == "bug-A"
        assert result.new_items[0].title == "bug-B"

    @pytest.mark.asyncio
    async def test_compare_unresolved(self, tracker: HistoryTracker) -> None:
        """同一位置的问题仍然存在 → unresolved。"""
        old_findings = [_finding(file="a.py", line=42, title="n+1查询")]
        await tracker.save(
            "task-001", "https://github.com/o/r/pull/1",
            old_findings, "1 个问题",
        )

        # 第二次评审同一位置仍有问题
        current = [_finding(file="a.py", line=42, title="n+1查询")]
        result = await tracker.compare(
            "https://github.com/o/r/pull/1", current,
        )

        assert result.comparison.unresolved_count == 1
        assert result.comparison.new_count == 0
        assert result.comparison.fixed_count == 0
        assert result.unresolved_items[0].repair_status == RepairStatus.UNRESOLVED

    @pytest.mark.asyncio
    async def test_compare_mixed(self, tracker: HistoryTracker) -> None:
        """混合场景：修复一个、新增一个、遗留一个。"""
        old = [
            _finding(file="a.py", line=1, title="bug-A"),  # 将消失→fixed
            _finding(file="b.py", line=2, title="bug-B"),  # 保留→unresolved
        ]
        await tracker.save("task-001", "https://github.com/o/r/pull/1", old, "2 个问题")

        current = [
            _finding(file="b.py", line=2, title="bug-B"),  # 仍在
            _finding(file="c.py", line=3, title="bug-C"),  # 新增
        ]
        result = await tracker.compare("https://github.com/o/r/pull/1", current)

        assert result.comparison.fixed_count == 1
        assert result.comparison.unresolved_count == 1
        assert result.comparison.new_count == 1
