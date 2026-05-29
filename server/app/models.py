"""
Pydantic 数据模型定义。

包含 API 请求/响应模型、Agent 输出模型、评审报告模型。
所有模型使用 Pydantic v2 风格 (model_validate / model_dump)。
"""

from __future__ import annotations

import uuid
from enum import Enum
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# 通用枚举
# =============================================================================


class AgentType(str, Enum):
    """Agent 类型标识。"""

    SECURITY = "security"
    PERFORMANCE = "performance"
    LOGIC = "logic"
    STYLE = "style"
    ARBITRATOR = "arbitrator"


class Severity(str, Enum):
    """发现项严重程度。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskLevel(str, Enum):
    """风险等级，用于前端着色。"""

    RED = "red"      # 高危，必须修复
    YELLOW = "yellow"  # 中危，建议修复
    GREEN = "green"    # 低危 / 建议


class RepairStatus(str, Enum):
    """修复验证状态。"""

    FIXED = "fixed"         # 已修复
    NEW = "new"             # 新引入
    UNRESOLVED = "unresolved"  # 未处理


class FeedbackType(str, Enum):
    """用户反馈类型。"""

    UPVOTE = "up"
    DOWNVOTE = "down"


# =============================================================================
# 请求模型
# =============================================================================


class ReviewRequest(BaseModel):
    """评审任务提交请求。

    Example:
        {"pr_url": "https://github.com/owner/repo/pull/42"}
    """

    pr_url: str = Field(
        ...,
        min_length=1,
        description="GitHub 或 GitLab PR 的完整 URL",
        examples=["https://github.com/owner/repo/pull/42"],
    )

    @field_validator("pr_url")
    @classmethod
    def validate_pr_url(cls, v: str) -> str:
        """校验 PR URL 格式。"""
        if "github.com" not in v and "gitlab" not in v:
            raise ValueError("PR URL 必须是 GitHub 或 GitLab 链接")
        if "/pull/" not in v and "/merge_requests/" not in v:
            raise ValueError("URL 中未检测到 pull request 路径")
        return v


class FeedbackRequest(BaseModel):
    """用户反馈请求。"""

    finding_index: int = Field(..., ge=0, description="发现项的索引")
    feedback: FeedbackType = Field(..., description="反馈类型: up 或 down")


# =============================================================================
# Agent 输出模型
# =============================================================================


class AgentFinding(BaseModel):
    """单个 Agent 的单个发现项。

    由各 Agent 调用 LLM 后返回的 JSON 解析而来。
    """

    file: str = Field(..., description="文件路径")
    line: int = Field(..., ge=1, description="行号")
    severity: Severity = Field(..., description="严重程度")
    category: str = Field(..., description="问题分类", examples=["sql-injection", "n+1-query"])
    title: str = Field(..., description="问题标题")
    description: str = Field(..., description="问题详细描述")
    suggestion: str = Field(..., description="修复建议")


class AgentReport(BaseModel):
    """单个 Agent 的完整评审报告。

    orchestrator 汇总四个 Agent 返回的此结构后进行冲突检测。
    """

    agent: AgentType = Field(..., description="Agent 类型")
    findings: list[AgentFinding] = Field(
        default_factory=list, description="发现项列表"
    )


# =============================================================================
# 最终报告模型
# =============================================================================


class ReviewFinding(BaseModel):
    """最终报告中的单条发现（经过仲裁和风险标注）。"""

    agent: AgentType
    severity: Severity
    risk_level: RiskLevel
    arbitrated: bool = False
    repair_status: RepairStatus = RepairStatus.NEW
    file: str
    line: int
    title: str
    description: str
    suggestion: str
    category: str = ""


class ComparisonSummary(BaseModel):
    """修复验证对比摘要。"""

    fixed_count: int = 0
    new_count: int = 0
    unresolved_count: int = 0


class TaskStatus(str, Enum):
    """评审任务状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewResponse(BaseModel):
    """评审任务提交后的即时响应。"""

    task_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="任务唯一标识",
    )
    status: TaskStatus = TaskStatus.PENDING


class ReviewResult(BaseModel):
    """评审任务完成后的完整结果。"""

    task_id: str
    pr_url: str
    status: TaskStatus
    summary: str = ""
    findings: list[ReviewFinding] = Field(default_factory=list)
    comparison: ComparisonSummary = Field(default_factory=ComparisonSummary)
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
    )


# =============================================================================
# 历史记录模型
# =============================================================================


class HistoryRecord(BaseModel):
    """历史评审记录（用于修复验证对比）。"""

    task_id: str
    pr_url: str
    created_at: str
    findings_count: int
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0


class HistoryComparison(BaseModel):
    """修复验证对比结果。"""

    current_task_id: str
    previous_task_id: str | None = None
    comparison: ComparisonSummary = Field(default_factory=ComparisonSummary)
    fixed_items: list[ReviewFinding] = Field(default_factory=list)
    new_items: list[ReviewFinding] = Field(default_factory=list)
    unresolved_items: list[ReviewFinding] = Field(default_factory=list)


# =============================================================================
# 健康检查模型
# =============================================================================


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: Literal["ok"] = "ok"
    version: str = "0.1.0"
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
    )
