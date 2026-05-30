"""
orchestrator.py 单元测试。

测试冲突检测、合并策略和风险标注流程。
"""

from __future__ import annotations

import pytest

from server.app.orchestrator import Orchestrator
from server.app.models import AgentFinding, AgentReport, AgentType, Severity


def _finding(
    agent: AgentType,
    severity: Severity,
    file: str = "a.py",
    line: int = 1,
    title: str = "test",
) -> AgentFinding:
    return AgentFinding(
        file=file,
        line=line,
        severity=severity,
        category="test",
        title=title,
        description="desc",
        suggestion="fix",
        agent=agent,
    )


# ── 冲突检测 ──────────────────────────────────────────────────


class TestDetectConflicts:
    """测试 _detect_conflicts 方法。"""

    def test_no_conflict_single_agent(self) -> None:
        orch = Orchestrator()
        reports = [
            AgentReport(
                agent=AgentType.SECURITY,
                findings=[_finding(AgentType.SECURITY, Severity.HIGH)],
            ),
        ]
        conflicts = orch._detect_conflicts(reports)
        assert len(conflicts) == 0

    def test_no_conflict_different_lines(self) -> None:
        orch = Orchestrator()
        reports = [
            AgentReport(
                agent=AgentType.SECURITY,
                findings=[_finding(AgentType.SECURITY, Severity.HIGH, line=1)],
            ),
            AgentReport(
                agent=AgentType.STYLE,
                findings=[_finding(AgentType.STYLE, Severity.LOW, line=2)],
            ),
        ]
        conflicts = orch._detect_conflicts(reports)
        assert len(conflicts) == 0

    def test_no_conflict_same_severity(self) -> None:
        """同一位置相同 severity 不构成冲突。"""
        orch = Orchestrator()
        reports = [
            AgentReport(
                agent=AgentType.SECURITY,
                findings=[_finding(AgentType.SECURITY, Severity.MEDIUM, line=1)],
            ),
            AgentReport(
                agent=AgentType.LOGIC,
                findings=[_finding(AgentType.LOGIC, Severity.MEDIUM, line=1)],
            ),
        ]
        conflicts = orch._detect_conflicts(reports)
        assert len(conflicts) == 0

    def test_conflict_high_vs_low(self) -> None:
        """同一位置 high vs low 构成冲突。"""
        orch = Orchestrator()
        reports = [
            AgentReport(
                agent=AgentType.SECURITY,
                findings=[_finding(AgentType.SECURITY, Severity.HIGH, line=1)],
            ),
            AgentReport(
                agent=AgentType.STYLE,
                findings=[_finding(AgentType.STYLE, Severity.LOW, line=1)],
            ),
        ]
        conflicts = orch._detect_conflicts(reports)
        assert len(conflicts) == 1

    def test_no_conflict_low_only(self) -> None:
        """同一位置多个 low 不构成冲突（low vs low 无差距）。"""
        orch = Orchestrator()
        reports = [
            AgentReport(
                agent=AgentType.SECURITY,
                findings=[_finding(AgentType.SECURITY, Severity.LOW, line=1)],
            ),
            AgentReport(
                agent=AgentType.STYLE,
                findings=[_finding(AgentType.STYLE, Severity.LOW, line=1)],
            ),
        ]
        conflicts = orch._detect_conflicts(reports)
        assert len(conflicts) == 0


# ── 合并策略 ──────────────────────────────────────────────────


class TestMerge:
    """测试 _merge_with/without_arbitration。"""

    def test_merge_without_arbitration(self) -> None:
        orch = Orchestrator()
        reports = [
            AgentReport(
                agent=AgentType.SECURITY,
                findings=[
                    _finding(AgentType.SECURITY, Severity.HIGH, title="sec"),
                ],
            ),
            AgentReport(
                agent=AgentType.PERFORMANCE,
                findings=[
                    _finding(AgentType.PERFORMANCE, Severity.MEDIUM, title="perf"),
                ],
            ),
        ]
        merged = orch._merge_without_arbitration(reports)
        assert len(merged) == 2

    def test_merge_with_arbitration_replaces_conflicts(self) -> None:
        orch = Orchestrator()
        agent_reports = [
            AgentReport(
                agent=AgentType.SECURITY,
                findings=[
                    _finding(AgentType.SECURITY, Severity.HIGH, line=1, title="sec-high"),
                    _finding(AgentType.SECURITY, Severity.LOW, line=2, title="sec-low"),
                ],
            ),
            AgentReport(
                agent=AgentType.STYLE,
                findings=[
                    _finding(AgentType.STYLE, Severity.LOW, line=1, title="style-low"),
                ],
            ),
        ]
        arbiter_report = AgentReport(
            agent=AgentType.ARBITRATOR,
            findings=[
                _finding(AgentType.ARBITRATOR, Severity.HIGH, line=1, title="arbitrated"),
            ],
        )
        merged = orch._merge_with_arbitration(agent_reports, arbiter_report)
        # 第 1 行的 sec-high 和 style-low 被仲裁结果替换
        # 第 2 行的 sec-low 保留
        assert len(merged) == 2
        titles = {f.title for f in merged}
        assert "arbitrated" in titles
        assert "sec-low" in titles
        assert "sec-high" not in titles
        assert "style-low" not in titles
