"""
FastAPI 应用入口。

定义路由、CORS 中间件、应用生命周期事件。
依赖注入：通过 get_settings() 获取全局配置。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from server.app.config import get_settings
from server.app.models import (
    HealthResponse,
    ReviewRequest,
    ReviewResponse,
    ReviewResult,
    HistoryComparison,
    FeedbackRequest,
    TaskStatus,
)


# ── 应用生命周期 ──────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用启动/关闭时的资源管理。"""
    settings = get_settings()
    app.state.settings = settings
    # 启动时初始化数据库连接（阶段5实现）
    yield
    # 关闭时清理资源（阶段5实现）


# ── FastAPI 实例 ──────────────────────────────────────────────

app = FastAPI(
    title="AI PR Reviewer",
    description="多 Agent 协作的智能代码评审系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS：开发阶段允许所有来源，生产环境通过环境变量限制
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 健康检查 ──────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查端点，用于 K8s / Docker Compose 的 healthcheck 探针。"""
    return HealthResponse()


# ── 评审任务 API ──────────────────────────────────────────────


@app.post("/api/v1/review", response_model=ReviewResponse, status_code=202)
async def submit_review(request: ReviewRequest) -> ReviewResponse:
    """提交代码评审任务。

    接收 PR URL，创建异步评审任务并立即返回 task_id。
    实际评审逻辑在 orchestrator 中异步执行（阶段4实现）。
    """
    # 阶段4：将任务加入后台队列并异步执行
    # task_id = await orchestrator.submit(request.pr_url)
    response = ReviewResponse(
        status=TaskStatus.PENDING,
    )
    return response


@app.get("/api/v1/review/{task_id}", response_model=ReviewResult)
async def get_review_result(task_id: str) -> ReviewResult:
    """查询评审任务状态和结果。

    根据 task_id 返回任务的当前状态：
    - pending: 排队中
    - running: 评审进行中
    - completed: 已完成，包含完整发现列表
    - failed: 评审失败
    """
    # 阶段4/5：从 SQLite 查询任务结果
    raise HTTPException(status_code=404, detail="任务不存在或尚未实现")


@app.get(
    "/api/v1/review/{task_id}/history",
    response_model=HistoryComparison,
)
async def get_review_history(task_id: str) -> HistoryComparison:
    """查询同一 PR 的修复验证对比数据。

    对比本次评审与上次评审的结果，标记每个发现项的修复状态：
    - fixed: 上次存在、本次不存在
    - new: 本次新发现
    - unresolved: 上次存在、本次仍存在
    """
    # 阶段5：从 SQLite 查询历史记录并对比
    raise HTTPException(status_code=404, detail="历史记录尚未实现")


@app.post(
    "/api/v1/review/{task_id}/feedback",
    status_code=204,
)
async def submit_feedback(task_id: str, feedback: FeedbackRequest) -> None:
    """提交评审结果反馈。

    用户对某条发现进行 👍 或 👎 反馈，用于后续优化 Agent 准确率。
    """
    # 阶段5：将反馈写入 SQLite
    raise HTTPException(status_code=404, detail="反馈功能尚未实现")
