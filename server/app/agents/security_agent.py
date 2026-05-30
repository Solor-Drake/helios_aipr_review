"""
安全评审 Agent。

专精于代码安全审计：注入攻击、XSS/CSRF、认证授权、敏感数据泄露、加密弱点。
"""

from __future__ import annotations

from pathlib import Path

from server.app.agents.base_agent import BaseAgent
from server.app.models import AgentType


class SecurityAgent(BaseAgent):
    """安全评审 Agent，检测代码中的安全漏洞。"""

    @property
    def agent_type(self) -> AgentType:
        return AgentType.SECURITY

    def _load_system_prompt(self) -> str:
        prompt_path = (
            Path(__file__).resolve().parent.parent.parent
            / "prompts"
            / "security_prompt.txt"
        )
        return prompt_path.read_text(encoding="utf-8")
