"""
风险等级标注模块。

根据 LLM 返回的 severity 和 agent 类型，为每条发现分配最终的风险等级（红/黄/绿）。
高风险等级直接影响前端着色和评审者的处理优先级。
"""

from __future__ import annotations

from server.app.models import (
    AgentFinding,
    AgentType,
    RiskLevel,
    Severity,
)


# 风险等级映射规则：基于 severity 和 agent 类型的二维决策
# 安全的 high > 逻辑的 high：因为安全漏洞通常影响更大
_RISK_WEIGHT: dict[AgentType, int] = {
    AgentType.SECURITY: 3,
    AgentType.PERFORMANCE: 2,
    AgentType.LOGIC: 2,
    AgentType.STYLE: 1,
    AgentType.ARBITRATOR: 3,  # 经过仲裁的发现，权重等同安全
}


def label_risk(finding: AgentFinding) -> RiskLevel:
    """为单条发现分配风险等级。

    规则：
    - severity=high 且 agent 为 security/arbitrator → red（高危，必须修复）
    - severity=high 且其他 agent → yellow（中危，建议修复）
    - severity=medium → yellow
    - severity=low → green（低危/建议）

    Args:
        finding: 单个 Agent 的发现项。

    Returns:
        RiskLevel 枚举值，用于前端着色。
    """
    if finding.severity == Severity.LOW:
        return RiskLevel.GREEN

    if finding.severity == Severity.HIGH:
        if finding.agent in (AgentType.SECURITY, AgentType.ARBITRATOR):
            return RiskLevel.RED
        return RiskLevel.YELLOW

    # severity == MEDIUM
    agent_weight = _RISK_WEIGHT.get(finding.agent, 1)
    if agent_weight >= 2:
        return RiskLevel.YELLOW
    return RiskLevel.GREEN
