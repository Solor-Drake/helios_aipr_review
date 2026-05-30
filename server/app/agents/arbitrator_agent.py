"""
仲裁 Agent。

当四个评审 Agent 对同一段代码产生严重分歧时，由仲裁 Agent 做出最终裁决。
遵循安全优先、事实依据、影响范围评估、误报过滤的仲裁原则。
"""

from __future__ import annotations

import json
from pathlib import Path

from server.app.agents.base_agent import BaseAgent
from server.app.models import AgentType, AgentReport


class ArbitratorAgent(BaseAgent):
    """仲裁 Agent，解决四个评审 Agent 之间的严重分歧。"""

    @property
    def agent_type(self) -> AgentType:
        return AgentType.ARBITRATOR

    def _load_system_prompt(self) -> str:
        prompt_path = (
            Path(__file__).resolve().parent.parent.parent
            / "prompts"
            / "arbitrator_prompt.txt"
        )
        return prompt_path.read_text(encoding="utf-8")

    # ── 覆盖 review 方法，因为仲裁的输入是四个 Agent 的报告 ──

    async def arbitrate(
        self,
        agent_reports: list[AgentReport],
        code_context: str,
    ) -> AgentReport:
        """对四个 Agent 的评审报告进行仲裁。

        Args:
            agent_reports: 安全/性能/逻辑/风格四个 Agent 的原始报告。
            code_context: 相关代码片段（用于事实核查）。

        Returns:
            仲裁后的统一报告，只包含有冲突的发现项。
        """
        system_prompt = self._load_system_prompt()

        # 构建仲裁专用 User Prompt
        reports_json = json.dumps(
            [r.model_dump() for r in agent_reports],
            ensure_ascii=False,
            indent=2,
        )
        user_prompt = (
            "请对以下四个代码评审 Agent 的报告进行仲裁。\n\n"
            "## 四个 Agent 的原始报告\n"
            f"{reports_json}\n\n"
            "## 相关代码上下文\n"
            f"{code_context}\n\n"
            "请输出有冲突需要裁决的发现项。无冲突的项不要输出。"
        )

        raw_json = await self._call_llm(system_prompt, user_prompt)
        report = self._parse_response(raw_json)

        return report
