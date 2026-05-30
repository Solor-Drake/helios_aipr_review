"""
risk_labeler.py 单元测试。

验证风险等级标注规则：high/medium/low → red/yellow/green。
"""

from __future__ import annotations

import pytest

from server.app.risk_labeler import label_risk
from server.app.models import AgentFinding, AgentType, Severity, RiskLevel


def _make_finding(
    agent: AgentType,
    severity: Severity,
    line: int = 1,
) -> AgentFinding:
    """创建测试用 AgentFinding。"""
    return AgentFinding(
        file="test.py",
        line=line,
        severity=severity,
        category="test",
        title="test",
        description="test",
        suggestion="test",
        agent=agent,
    )


# ── 安全 Agent 风险标注 ──────────────────────────────────────


class TestSecurityLabeling:
    def test_high_is_red(self) -> None:
        f = _make_finding(AgentType.SECURITY, Severity.HIGH)
        assert label_risk(f) == RiskLevel.RED

    def test_medium_is_yellow(self) -> None:
        f = _make_finding(AgentType.SECURITY, Severity.MEDIUM)
        assert label_risk(f) == RiskLevel.YELLOW

    def test_low_is_green(self) -> None:
        f = _make_finding(AgentType.SECURITY, Severity.LOW)
        assert label_risk(f) == RiskLevel.GREEN


# ── 性能 Agent 风险标注 ──────────────────────────────────────


class TestPerformanceLabeling:
    def test_high_is_yellow(self) -> None:
        """性能 high 不会标红，只标黄（因为安全优先）。"""
        f = _make_finding(AgentType.PERFORMANCE, Severity.HIGH)
        assert label_risk(f) == RiskLevel.YELLOW

    def test_medium_is_yellow(self) -> None:
        f = _make_finding(AgentType.PERFORMANCE, Severity.MEDIUM)
        assert label_risk(f) == RiskLevel.YELLOW

    def test_low_is_green(self) -> None:
        f = _make_finding(AgentType.PERFORMANCE, Severity.LOW)
        assert label_risk(f) == RiskLevel.GREEN


# ── 风格 Agent 风险标注 ──────────────────────────────────────


class TestStyleLabeling:
    def test_high_is_yellow(self) -> None:
        f = _make_finding(AgentType.STYLE, Severity.HIGH)
        assert label_risk(f) == RiskLevel.YELLOW

    def test_medium_is_green(self) -> None:
        """风格 medium 权重低，标绿。"""
        f = _make_finding(AgentType.STYLE, Severity.MEDIUM)
        assert label_risk(f) == RiskLevel.GREEN

    def test_low_is_green(self) -> None:
        f = _make_finding(AgentType.STYLE, Severity.LOW)
        assert label_risk(f) == RiskLevel.GREEN


# ── 仲裁 Agent 风险标注 ──────────────────────────────────────


class TestArbitratorLabeling:
    def test_high_is_red(self) -> None:
        f = _make_finding(AgentType.ARBITRATOR, Severity.HIGH)
        assert label_risk(f) == RiskLevel.RED
