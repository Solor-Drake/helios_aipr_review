"""
风格评审 Agent。

专精于代码可维护性：命名规范、函数设计、代码重复、注释质量、类型安全、模块结构。
"""

from __future__ import annotations

from pathlib import Path

from server.app.agents.base_agent import BaseAgent
from server.app.models import AgentType


class StyleAgent(BaseAgent):
    """风格评审 Agent，检测代码中的可读性和可维护性问题。"""

    @property
    def agent_type(self) -> AgentType:
        return AgentType.STYLE

    def _load_system_prompt(self) -> str:
        prompt_path = (
            Path(__file__).resolve().parent.parent.parent
            / "prompts"
            / "style_prompt.txt"
        )
        return prompt_path.read_text(encoding="utf-8")
