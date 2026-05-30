"""
四个评审 Agent 和仲裁 Agent 的单元测试。

验证 agent_type、System Prompt 加载、arbitrate 方法。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from server.app.agents.security_agent import SecurityAgent
from server.app.agents.performance_agent import PerformanceAgent
from server.app.agents.logic_agent import LogicAgent
from server.app.agents.style_agent import StyleAgent
from server.app.agents.arbitrator_agent import ArbitratorAgent
from server.app.models import AgentType, AgentReport, AgentFinding, Severity


# ── Agent 类型验证 ────────────────────────────────────────────


@pytest.mark.parametrize(
    "agent_cls, expected_type",
    [
        (SecurityAgent, AgentType.SECURITY),
        (PerformanceAgent, AgentType.PERFORMANCE),
        (LogicAgent, AgentType.LOGIC),
        (StyleAgent, AgentType.STYLE),
        (ArbitratorAgent, AgentType.ARBITRATOR),
    ],
)
def test_agent_type(agent_cls: type, expected_type: AgentType) -> None:
    agent = agent_cls()
    assert agent.agent_type == expected_type


# ── System Prompt 加载验证 ────────────────────────────────────


@pytest.mark.parametrize(
    "agent_cls, keyword",
    [
        (SecurityAgent, "安全"),
        (PerformanceAgent, "性能"),
        (LogicAgent, "逻辑"),
        (StyleAgent, "风格"),
        (ArbitratorAgent, "仲裁"),
    ],
)
def test_load_system_prompt(agent_cls: type, keyword: str) -> None:
    agent = agent_cls()
    prompt = agent._load_system_prompt()
    assert keyword in prompt
    assert len(prompt) > 100  # 确保加载了完整内容而非空文件


# ── 仲裁 Agent arbitrate 方法 ─────────────────────────────────


class TestArbitrator:
    """测试仲裁 Agent 的 arbitrate 方法（mock LLM）。"""

    @pytest.mark.asyncio
    async def test_arbitrate_returns_report(self) -> None:
        agent = ArbitratorAgent()
        reports = [
            AgentReport(
                agent=AgentType.SECURITY,
                findings=[
                    AgentFinding(
                        file="a.py", line=1, severity=Severity.HIGH,
                        category="injection", title="SQL注入",
                        description="...", suggestion="使用参数化查询",
                    ),
                ],
            ),
            AgentReport(
                agent=AgentType.STYLE,
                findings=[
                    AgentFinding(
                        file="a.py", line=1, severity=Severity.LOW,
                        category="naming", title="变量命名不规范",
                        description="...", suggestion="改用 snake_case",
                    ),
                ],
            ),
        ]

        mock_result_json = (
            '{"agent": "arbitrator", "findings": ['
            '{"file": "a.py", "line": 1, "severity": "high", '
            '"category": "injection", "title": "SQL注入（已仲裁）", '
            '"description": "安全Agent标记为高危，采纳安全立场", '
            '"suggestion": "使用参数化查询"}]}'
        )
        mock_create = AsyncMock()
        mock_message = AsyncMock()
        mock_message.content = mock_result_json
        mock_choice = AsyncMock()
        mock_choice.message = mock_message
        mock_completion = AsyncMock()
        mock_completion.choices = [mock_choice]
        mock_create.return_value = mock_completion

        with patch.object(agent.client.chat.completions, "create", mock_create):
            result = await agent.arbitrate(reports, "def foo(): pass")

        assert result.agent == AgentType.ARBITRATOR
        assert len(result.findings) == 1
        assert "仲裁" in result.findings[0].title
