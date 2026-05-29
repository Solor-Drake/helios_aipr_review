"""
Agent 基类模块。

封装 LLM API 调用逻辑，提供统一的异步调用接口。
支持阿里云百炼和 DeepSeek 双平台，通过环境变量切换。
子类只需传入 agent_type 和 system_prompt 即可复用全部逻辑。
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from server.app.config import get_settings
from server.app.models import AgentType, AgentReport

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 抽象基类。

    封装了 LLM 客户端初始化、System Prompt 加载、API 调用和响应解析。
    子类必须实现 agent_type 属性和 _load_system_prompt() 方法。
    """

    def __init__(self) -> None:
        """初始化 Agent。

        从全局配置读取 AI 服务参数，创建 AsyncOpenAI 客户端。
        默认使用阿里云百炼，如检测到 DeepSeek 配置则自动切换。
        """
        settings = get_settings()
        ai = settings.ai

        # 根据 default_model 自动选择 base_url 和 api_key
        if "deepseek" in ai.default_model.lower():
            base_url = ai.deepseek_base_url
            api_key = ai.deepseek_api_key
        else:
            base_url = ai.daskscope_base_url
            api_key = ai.daskscope_api_key

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=ai.request_timeout,
        )
        self.model: str = ai.default_model
        self.temperature: float = ai.temperature
        self.max_tokens: int = ai.max_tokens

    # ── 子类必须实现 ──────────────────────────────────────

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """返回当前 Agent 的类型标识。"""
        ...

    @abstractmethod
    def _load_system_prompt(self) -> str:
        """加载 System Prompt 文本。

        子类实现时应从 server/prompts/ 目录读取对应的 .txt 文件。
        """
        ...

    # ── 公共接口 ──────────────────────────────────────────

    async def review(self, code_context: str, diff: str) -> AgentReport:
        """对代码变更执行评审。

        Args:
            code_context: tree-sitter 提取的代码上下文（函数定义、调用关系）。
            diff: PR 的 unified diff 文本。

        Returns:
            结构化评审报告。

        Raises:
            ValueError: LLM 返回的 JSON 无法解析时抛出。
        """
        system_prompt = self._load_system_prompt()
        user_prompt = self._build_user_prompt(code_context, diff)

        raw_json = await self._call_llm(system_prompt, user_prompt)
        report = self._parse_response(raw_json)

        logger.info(
            "Agent %s 评审完成，发现 %d 个问题",
            self.agent_type.value,
            len(report.findings),
        )
        return report

    # ── 内部方法 ──────────────────────────────────────────

    def _build_user_prompt(self, code_context: str, diff: str) -> str:
        """构建发送给 LLM 的 User Prompt。"""
        return (
            "请对以下代码变更进行评审。\n\n"
            "## 代码上下文（变更相关的函数定义和调用关系）\n"
            f"{code_context}\n\n"
            "## 代码变更 (unified diff)\n"
            f"{diff}\n\n"
            "请以 JSON 格式返回评审结果，严格遵守 output_schema。"
        )

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM API 并返回原始文本。

        Args:
            system_prompt: System Prompt（从 txt 文件加载）。
            user_prompt: 拼接了代码上下文和 diff 的 User Prompt。

        Returns:
            LLM 返回的原始 JSON 字符串。

        Raises:
            RuntimeError: API 调用失败时抛出。
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.error(
                "Agent %s LLM 调用失败: %s",
                self.agent_type.value,
                exc,
            )
            raise RuntimeError(
                f"Agent {self.agent_type.value} API 调用失败: {exc}"
            ) from exc

        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError(
                f"Agent {self.agent_type.value} 返回了空响应"
            )
        return content

    def _parse_response(self, raw_json: str) -> AgentReport:
        """将 LLM 返回的 JSON 解析为 AgentReport。

        Args:
            raw_json: LLM 返回的原始 JSON 字符串。

        Returns:
            校验后的结构化报告。

        Raises:
            ValueError: JSON 无法解析或字段校验失败。
        """
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.error("Agent %s 返回的 JSON 解析失败: %s", self.agent_type.value, exc)
            raise ValueError(
                f"Agent {self.agent_type.value} 返回了无效 JSON: {raw_json[:200]}"
            ) from exc

        # 确保 agent 字段与当前 Agent 类型一致
        data.setdefault("agent", self.agent_type.value)

        return AgentReport.model_validate(data)
