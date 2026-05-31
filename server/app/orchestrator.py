"""
评审编排模块。

负责整个评审流程的编排：拉取 PR 信息 → 构建上下文 → 并行调用四个 Agent →
冲突检测 → 触发仲裁 → 风险标注 → 构建最终报告。
"""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from server.app.config import get_settings
from server.app.models import (
    AgentFinding,
    AgentReport,
    AgentType,
    ReviewFinding,
    ReviewMode,
    HumanReviewStatus,
    ReviewResult,
    ComparisonSummary,
    RepairStatus,
    RiskLevel,
    Severity,
    TaskStatus,
)
from server.app.git_client import create_git_client, parse_pr_url
from server.app.context_builder import ContextBuilder
from server.app.agents.security_agent import SecurityAgent
from server.app.agents.performance_agent import PerformanceAgent
from server.app.agents.logic_agent import LogicAgent
from server.app.agents.style_agent import StyleAgent
from server.app.agents.arbitrator_agent import ArbitratorAgent
from server.app.risk_labeler import label_risk

logger = logging.getLogger(__name__)


class Orchestrator:
    """评审流程编排器。

    协调 git_client、context_builder、四个 Agent、仲裁 Agent 和 risk_labeler，
    完成一次完整的 PR 评审流程。
    """

    def __init__(self) -> None:
        self._context_builder = ContextBuilder()

    # ── 主流程 ──────────────────────────────────────────────

    async def review_pr(self, pr_url: str, review_mode: str = "auto") -> ReviewResult:
        """对指定 PR 执行完整评审流程。

        Args:
            pr_url: GitHub 或 GitLab 的 PR URL。
            review_mode: 评审模式 "auto" / "manual"。

        Returns:
            包含所有发现项、风险标注和对比摘要的完整评审结果。
        """
        task_id = str(uuid4())
        logger.info("开始评审 PR: %s (task_id=%s)", pr_url, task_id)

        # 1. 拉取 PR 数据
        pr_info = parse_pr_url(pr_url)
        git_client = create_git_client(pr_url)

        diff = await git_client.get_pr_diff(pr_info)
        file_changes = await git_client.get_pr_files(pr_info)

        # 2. 构建代码上下文
        review_ctx = self._context_builder.build(file_changes, diff)
        code_context = self._context_builder.format_context(review_ctx)

        # 3. 并行调用四个 Agent
        agent_reports = await self._run_agents(code_context, diff)

        # 4. 冲突检测
        conflicts = self._detect_conflicts(agent_reports)

        # 5. 触发仲裁（有冲突时）
        if conflicts:
            logger.info("检测到 %d 个冲突，触发仲裁", len(conflicts))
            arbitrator = ArbitratorAgent()
            conflict_context = self._build_conflict_context(conflicts, code_context)
            arbiter_report = await arbitrator.arbitrate(
                [r for r in agent_reports if r.findings],
                conflict_context,
            )
            resolved = self._merge_with_arbitration(agent_reports, arbiter_report)
        else:
            logger.info("无冲突，跳过仲裁")
            resolved = self._merge_without_arbitration(agent_reports)

        # 6. 标注风险等级
        review_findings: list[ReviewFinding] = []
        for f in resolved:
            rf = ReviewFinding(
                agent=f.agent,
                severity=f.severity,
                risk_level=label_risk(f),
                arbitrated=(f.agent == AgentType.ARBITRATOR or self._was_arbitrated(f, conflicts)),
                repair_status=RepairStatus.NEW,
                human_status=HumanReviewStatus.PENDING if review_mode == "manual" else HumanReviewStatus.PENDING,
                review_mode=ReviewMode.MANUAL if review_mode == "manual" else ReviewMode.AUTO,
                file=f.file,
                line=f.line,
                title=f.title,
                description=f.description,
                suggestion=f.suggestion,
                category=f.category,
            )
            review_findings.append(rf)

        # 7. 构建摘要
        high_count = sum(1 for f in review_findings if f.severity == Severity.HIGH)
        medium_count = sum(1 for f in review_findings if f.severity == Severity.MEDIUM)
        low_count = sum(1 for f in review_findings if f.severity == Severity.LOW)

        result = ReviewResult(
            task_id=task_id,
            pr_url=pr_url,
            status=TaskStatus.COMPLETED,
            summary=(
                f"本次 PR 共发现 {high_count} 个高危、"
                f"{medium_count} 个中危、{low_count} 个建议"
            ),
            findings=review_findings,
            comparison=ComparisonSummary(
                new_count=len(review_findings),
            ),
        )

        logger.info(
            "评审完成: task_id=%s, 发现 %d 个问题",
            task_id,
            len(review_findings),
        )

        # 清理
        await git_client.close()
        return result

    # ── Agent 并行调用 ──────────────────────────────────────

    async def _run_agents(
        self, code_context: str, diff: str
    ) -> list[AgentReport]:
        """并行调用四个 Agent，收集所有评审报告。

        Args:
            code_context: 格式化的代码上下文。
            diff: 原始 unified diff。

        Returns:
            四个 Agent 的评审报告列表（排除超时/失败的 Agent）。
        """
        agents = [
            SecurityAgent(),
            PerformanceAgent(),
            LogicAgent(),
            StyleAgent(),
        ]

        async def _run_one(agent: Any) -> AgentReport | None:
            try:
                return await agent.review(code_context, diff)
            except Exception as exc:
                logger.error(
                    "Agent %s 评审失败: %s",
                    agent.agent_type.value,
                    exc,
                )
                return None

        results = await asyncio.gather(*[_run_one(a) for a in agents])
        return [r for r in results if r is not None]

    # ── 冲突检测 ────────────────────────────────────────────

    def _detect_conflicts(
        self, reports: list[AgentReport]
    ) -> list[tuple[AgentFinding, AgentFinding]]:
        """检测两个以上 Agent 对同一位置产生分歧的发现项。

        分歧定义：
        - 同一文件 + 同一行 + 不同 Agent
        - severity 差两档（high vs low / low vs high）
        - 或 category 完全不同（如一个说安全，一个说风格）

        Args:
            reports: 各 Agent 的评审报告。

        Returns:
            冲突对列表，每对包含两个冲突的发现项。
        """
        conflicts: list[tuple[AgentFinding, AgentFinding]] = []
        # 按 (file, line) 分组
        position_map: dict[tuple[str, int], list[AgentFinding]] = {}
        for report in reports:
            for f in report.findings:
                key = (f.file, f.line)
                position_map.setdefault(key, []).append(f)

        for (file, line), findings in position_map.items():
            if len(findings) < 2:
                continue
            # 检查 severity 差距
            severities = {f.severity for f in findings}
            if Severity.HIGH in severities and Severity.LOW in severities:
                # 找出一对 high-low 冲突
                high_finding = next(f for f in findings if f.severity == Severity.HIGH)
                low_finding = next(f for f in findings if f.severity == Severity.LOW)
                conflicts.append((high_finding, low_finding))

        return conflicts

    def _was_arbitrated(
        self,
        finding: AgentFinding,
        conflicts: list[tuple[AgentFinding, AgentFinding]],
    ) -> bool:
        """检查某发现项是否经历了仲裁。"""
        for a, b in conflicts:
            if finding is a or finding is b:
                return True
        return False

    # ── 结果合并 ────────────────────────────────────────────

    def _merge_with_arbitration(
        self,
        agent_reports: list[AgentReport],
        arbiter_report: AgentReport,
    ) -> list[AgentFinding]:
        """有仲裁的合并策略。

        仲裁结果替换冲突项，未冲突的项全部保留。
        """
        # 收集所有与仲裁相关的 (file, line)，从原始报告中移除这些位置的发现
        arbiter_positions: set[tuple[str, int]] = set()
        for f in arbiter_report.findings:
            arbiter_positions.add((f.file, f.line))

        merged: list[AgentFinding] = []
        for report in agent_reports:
            for f in report.findings:
                if (f.file, f.line) not in arbiter_positions:
                    merged.append(f)

        # 追加仲裁结果
        merged.extend(arbiter_report.findings)
        return merged

    def _merge_without_arbitration(
        self, agent_reports: list[AgentReport]
    ) -> list[AgentFinding]:
        """无冲突的合并策略：直接合并所有发现项。"""
        merged: list[AgentFinding] = []
        for report in agent_reports:
            merged.extend(report.findings)
        return merged

    # ── 冲突上下文构建 ──────────────────────────────────────

    def _build_conflict_context(
        self,
        conflicts: list[tuple[AgentFinding, AgentFinding]],
        code_context: str,
    ) -> str:
        """为仲裁 Agent 构建冲突上下文。

        Args:
            conflicts: 冲突对列表。
            code_context: 原始代码上下文（可能很长）。

        Returns:
            仲裁用的精简上下文，只包含冲突相关的信息。
        """
        lines: list[str] = ["## 冲突项摘要", ""]
        for i, (a, b) in enumerate(conflicts, 1):
            lines.append(
                f"### 冲突 {i}: {a.file}:{a.line}"
            )
            lines.append(
                f"- Agent {a.agent.value}: severity={a.severity.value}, "
                f"title=\"{a.title}\""
            )
            lines.append(
                f"- Agent {b.agent.value}: severity={b.severity.value}, "
                f"title=\"{b.title}\""
            )
            lines.append("")
        lines.append("")
        lines.append(code_context)
        return "\n".join(lines)
