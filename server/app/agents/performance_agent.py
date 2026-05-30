"""
性能评审 Agent。

专精于性能分析：N+1 查询、内存管理、并发锁、网络 IO、算法复杂度、资源泄露。
"""

from __future__ import annotations

from pathlib import Path

from server.app.agents.base_agent import BaseAgent
from server.app.models import AgentType


class PerformanceAgent(BaseAgent):
    """性能评审 Agent，检测代码中的性能瓶颈和资源浪费。"""

    @property
    def agent_type(self) -> AgentType:
        return AgentType.PERFORMANCE

    def _load_system_prompt(self) -> str:
        prompt_path = (
            Path(__file__).resolve().parent.parent.parent
            / "prompts"
            / "performance_prompt.txt"
        )
        return prompt_path.read_text(encoding="utf-8")
