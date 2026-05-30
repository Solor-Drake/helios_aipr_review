"""
逻辑评审 Agent。

专精于代码正确性验证：边界条件、异常处理、状态管理、并发竞态、API 契约。
"""

from __future__ import annotations

from pathlib import Path

from server.app.agents.base_agent import BaseAgent
from server.app.models import AgentType


class LogicAgent(BaseAgent):
    """逻辑评审 Agent，检测代码中的业务逻辑缺陷和边界错误。"""

    @property
    def agent_type(self) -> AgentType:
        return AgentType.LOGIC

    def _load_system_prompt(self) -> str:
        prompt_path = (
            Path(__file__).resolve().parent.parent.parent
            / "prompts"
            / "logic_prompt.txt"
        )
        return prompt_path.read_text(encoding="utf-8")
