"""
FastAPI 应用入口。

定义路由、CORS 中间件、应用生命周期事件。
所有端点接入已实现的 orchestrator、history_tracker 模块。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from server.app.config import get_settings
from server.app.models import (
    ReviewRequest,
    ReviewResponse,
    ReviewResult,
    HistoryComparison,
    FeedbackRequest,
    TaskStatus,
)
from server.app.orchestrator import Orchestrator
from server.app.history_tracker import HistoryTracker
from server.app.error_classifier import classify_error

logger = logging.getLogger(__name__)

# ── 内存任务存储 ──────────────────────────────────────────────

_tasks: dict[str, dict] = {}


# ── 应用生命周期 ──────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    app.state.settings = settings

    # 启动时校验 AI 服务是否可用
    if not settings.ai.is_api_key_configured():
        logger.warning("=" * 60)
        logger.warning("⚠️  未检测到有效的大模型 API Key！")
        logger.warning("   AI 评审功能将不可用，所有评审请求会被拒绝。")
        logger.warning("   请在项目根目录的 .env 文件中配置以下任一变量：")
        logger.warning("     DASHSCOPE_API_KEY=你的阿里云百炼 Key")
        logger.warning("     DEEPSEEK_API_KEY=你的 DeepSeek Key")
        logger.warning("   当前激活的服务商: %s", settings.ai.active_provider_name())
        logger.warning("=" * 60)

    yield


# ── FastAPI 实例 ──────────────────────────────────────────────

app = FastAPI(
    title="AI PR Reviewer",
    description="多 Agent 协作的智能代码评审系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 健康检查 ──────────────────────────────────────────────────


@app.get("/health")
async def health_check():
    """健康检查，同时报告 AI 服务配置状态。"""
    settings = get_settings()
    return {
        "status": "ok",
        "version": "0.1.0",
        "timestamp": datetime.now().isoformat(),
        "ai_configured": settings.ai.is_api_key_configured(),
    }


# ── 评审任务 API ──────────────────────────────────────────────


@app.post("/api/v1/review", response_model=ReviewResponse, status_code=202)
async def submit_review(request: ReviewRequest) -> ReviewResponse:
    """提交代码评审任务，异步启动评审流水线。"""
    settings = get_settings()
    if not settings.ai.is_api_key_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                f"AI 服务未配置：请在 .env 文件中设置有效的 "
                f"{settings.ai.active_provider_name()}。"
                f"当前值为占位符，无法进行代码评审。"
            ),
        )

    task_id = ReviewResponse().task_id
    _tasks[task_id] = {
        "task_id": task_id,
        "pr_url": request.pr_url,
        "review_mode": request.review_mode.value,
        "status": TaskStatus.PENDING,
        "result": None,
        "error": None,
    }
    asyncio.create_task(_run_review_pipeline(task_id, request.pr_url))
    logger.info("评审任务已创建: task_id=%s", task_id)
    return ReviewResponse(task_id=task_id, status=TaskStatus.PENDING)


@app.get("/api/v1/review/{task_id}", response_model=ReviewResult)
async def get_review_result(task_id: str) -> ReviewResult:
    """查询评审任务状态和结果。"""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    if task["status"] == TaskStatus.FAILED:
        return ReviewResult(
            task_id=task_id,
            pr_url=task["pr_url"],
            status=TaskStatus.FAILED,
            summary=task.get("error", "未知错误"),
            findings=[],
        )

    if task["status"] == TaskStatus.COMPLETED and task["result"]:
        return task["result"]

    return ReviewResult(
        task_id=task_id,
        pr_url=task["pr_url"],
        status=task["status"],
        summary="评审进行中...",
        findings=[],
    )


@app.get("/api/v1/review/{task_id}/history", response_model=HistoryComparison)
async def get_review_history(task_id: str) -> HistoryComparison:
    """查询修复验证对比数据。

    工作原理：从 SQLite 中查找同一 PR URL 的上一次评审记录，
    基于 (file, line) 匹配判断每条发现的修复状态。

    生产场景：同一个 PR 经过多次提交、多次评审后，开发者可直观看到
    哪些问题已被修复、哪些是新引入的、哪些仍未处理。

    演示/开发场景：首次评审无历史记录，所有发现均标记为 new。
    如需查看对比效果，对同一 PR 执行两次评审即可触发。
    """
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务尚未完成")

    tracker = HistoryTracker()
    result = await tracker.compare(task["pr_url"], task["result"].findings)
    return result


@app.post("/api/v1/review/{task_id}/feedback", status_code=204)
async def submit_feedback(task_id: str, feedback: FeedbackRequest) -> None:
    """提交评审结果反馈。"""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    logger.info("反馈已记录: task_id=%s, index=%d, feedback=%s",
                task_id, feedback.finding_index, feedback.feedback.value)


@app.patch("/api/v1/review/{task_id}/finding/{finding_index}")
async def update_human_status(task_id: str, finding_index: int, status: str = "pending") -> dict:
    """更新人工复核模式下某条发现的人工确认状态。"""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    findings = task.get("result").findings if task.get("result") else []
    if finding_index < 0 or finding_index >= len(findings):
        raise HTTPException(status_code=400, detail="finding_index 越界")
    findings[finding_index].human_status = status
    logger.info("人工状态更新: task_id=%s, index=%d, status=%s", task_id, finding_index, status)
    return {"task_id": task_id, "finding_index": finding_index, "human_status": status}


# ── 评审流水线 ────────────────────────────────────────────────


async def _run_review_pipeline(task_id: str, pr_url: str) -> None:
    """后台执行完整评审流程。"""
    task = _tasks.get(task_id)
    if task is None:
        return

    try:
        review_mode = task.get("review_mode", "auto")
        task["status"] = TaskStatus.RUNNING
        orchestrator = Orchestrator()
        result = await orchestrator.review_pr(pr_url, review_mode)

        task["status"] = TaskStatus.COMPLETED
        task["result"] = result

        # 持久化到 SQLite
        tracker = HistoryTracker()
        await tracker.save(task_id, pr_url, result.findings, result.summary)

        logger.info("评审完成: task_id=%s, findings=%d", task_id, len(result.findings))

    except Exception as exc:
        logger.exception("评审失败: task_id=%s", task_id)
        task["status"] = TaskStatus.FAILED
        task["error"] = classify_error(exc)
