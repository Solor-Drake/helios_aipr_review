"""
base_agent.py 单元测试。

测试 BaseAgent 的核心逻辑：JSON 解析、Prompt 构建、错误处理。
LLM API 调用通过 mock 隔离，不依赖真实网络。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from server.app.agents.base_agent import BaseAgent
from server.app.models import AgentType, AgentReport, AgentFinding, Severity


# ── 测试用具体 Agent 实现 ────────────────────────────────────


class MockSecurityAgent(BaseAgent):
    """测试用安全 Agent，返回固定 System Prompt。"""

    @property
    def agent_type(self) -> AgentType:
        return AgentType.SECURITY

    def _load_system_prompt(self) -> str:
        return "你是一个安全评审专家。"


# ── JSON 解析测试 ────────────────────────────────────────────


class TestParseResponse:
    """测试 _parse_response 方法。"""

    def test_parse_valid_json(self, valid_agent_json: str) -> None:
        """解析合法的 LLM 返回 JSON。"""
        agent = MockSecurityAgent()
        report = agent._parse_response(valid_agent_json)

        assert isinstance(report, AgentReport)
        assert report.agent == AgentType.SECURITY
        assert len(report.findings) == 1

        finding = report.findings[0]
        assert finding.file == "src/auth.py"
        assert finding.line == 13
        assert finding.severity == Severity.HIGH
        assert finding.category == "sql-injection"

    def test_parse_invalid_json_raises(self) -> None:
        """无效 JSON 抛出 ValueError。"""
        agent = MockSecurityAgent()
        with pytest.raises(ValueError, match="无效 JSON"):
            agent._parse_response("这不是 JSON")

    def test_parse_empty_findings(self) -> None:
        """零发现项的报告也能正常解析。"""
        agent = MockSecurityAgent()
        json_str = '{"agent": "security", "findings": []}'
        report = agent._parse_response(json_str)

        assert isinstance(report, AgentReport)
        assert len(report.findings) == 0

    def test_parse_auto_fill_agent_field(self) -> None:
        """LLM 未返回 agent 字段时自动补充。"""
        agent = MockSecurityAgent()
        json_str = '{"findings": []}'
        report = agent._parse_response(json_str)

        assert report.agent == AgentType.SECURITY


# ── Prompt 构建测试 ──────────────────────────────────────────


class TestBuildUserPrompt:
    """测试 _build_user_prompt 方法。"""

    def test_prompt_contains_context_and_diff(
        self, sample_code_context: str, sample_diff: str
    ) -> None:
        """Prompt 中包含了代码上下文和 diff。"""
        agent = MockSecurityAgent()
        prompt = agent._build_user_prompt(sample_code_context, sample_diff)

        assert "代码上下文" in prompt
        assert "代码变更" in prompt
        assert sample_code_context in prompt
        assert sample_diff in prompt
        assert "output_schema" in prompt


# ── LLM 调用测试 ─────────────────────────────────────────────


class TestCallLLM:
    """测试 _call_llm 方法（mock OpenAI 客户端）。"""

    @pytest.mark.asyncio
    async def test_call_llm_returns_content(self) -> None:
        """API 调用正常返回内容。"""
        agent = MockSecurityAgent()
        mock_message = AsyncMock()
        mock_message.content = '{"findings": []}'

        mock_choice = AsyncMock()
        mock_choice.message = mock_message

        mock_completion = AsyncMock()
        mock_completion.choices = [mock_choice]

        with patch.object(agent.client.chat.completions, "create", return_value=mock_completion):
            result = await agent._call_llm("system", "user")
            assert result == '{"findings": []}'

    @pytest.mark.asyncio
    async def test_call_llm_empty_response_raises(self) -> None:
        """LLM 返回空内容时抛出 RuntimeError。"""
        agent = MockSecurityAgent()
        mock_message = AsyncMock()
        mock_message.content = None

        mock_choice = AsyncMock()
        mock_choice.message = mock_message

        mock_completion = AsyncMock()
        mock_completion.choices = [mock_choice]

        with patch.object(agent.client.chat.completions, "create", return_value=mock_completion):
            with pytest.raises(RuntimeError, match="空响应"):
                await agent._call_llm("system", "user")

    @pytest.mark.asyncio
    async def test_call_llm_api_error_raises(self) -> None:
        """API 调用异常时抛出 RuntimeError。"""
        agent = MockSecurityAgent()
        with patch.object(
            agent.client.chat.completions,
            "create",
            side_effect=Exception("网络超时"),
        ):
            with pytest.raises(RuntimeError, match="API 调用失败"):
                await agent._call_llm("system", "user")


# ── 集成测试（mock LLM）───────────────────────────────────────


class TestReview:
    """测试 review() 完整流程（mock LLM）。"""

    @pytest.mark.asyncio
    async def test_review_returns_agent_report(
        self, sample_code_context: str, sample_diff: str, valid_agent_json: str
    ) -> None:
        """完整的 review 流程返回正确的 AgentReport。"""
        agent = MockSecurityAgent()
        mock_message = AsyncMock()
        mock_message.content = valid_agent_json

        mock_choice = AsyncMock()
        mock_choice.message = mock_message

        mock_completion = AsyncMock()
        mock_completion.choices = [mock_choice]

        with patch.object(agent.client.chat.completions, "create", return_value=mock_completion):
            report = await agent.review(sample_code_context, sample_diff)

        assert report.agent == AgentType.SECURITY
        assert len(report.findings) == 1
        assert report.findings[0].title == "SQL注入风险"
