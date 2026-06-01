"""
评审历史追踪模块。

负责 SQLite 存储和修复验证：每次评审完成后将结果写入数据库，
后续对同一个 PR URL 的新评审会自动对比上次记录，标记每条发现项的修复状态。

修复验证三态：
- fixed（已修复）：上次存在、本次不存在 → 开发者根据上次评审修复了代码
- new（新引入）：上次不存在、本次存在 → 代码变更带来了新问题
- unresolved（未处理）：上次存在、本次仍存在 → 问题未被修复

注意：此功能在生产环境下才有实际意义——同一 PR 多次提交、多次评审。
单次评审或首次评审时，因无历史记录，所有发现均标记为 new。
演示环境下可通过 /history/demo 端点查看模拟效果。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from server.app.config import get_settings
from server.app.models import (
    ReviewFinding,
    RepairStatus,
    HistoryComparison,
    ComparisonSummary,
)

logger = logging.getLogger(__name__)


class HistoryTracker:
    """评审历史追踪器。

    使用 SQLite 存储评审结果，通过对比同一 PR URL 的相邻两次评审，
    实现"修复验证闭环"。
    """

    def __init__(self) -> None:
        settings = get_settings()
        db_path = Path(settings.server.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db_path)
        self._init_db()

    # ── 数据库初始化 ───────────────────────────────────────

    def _init_db(self) -> None:
        """创建 reviews 表（如果不存在）。"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    pr_url TEXT NOT NULL,
                    findings_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_pr_url
                ON reviews(pr_url, created_at DESC)
            """)
            conn.commit()

    # ── 存储 ──────────────────────────────────────────────

    async def save(self, task_id: str, pr_url: str, findings: list[ReviewFinding], summary: str) -> None:
        """保存评审结果到 SQLite。

        Args:
            task_id: 评审任务 ID。
            pr_url: PR URL。
            findings: 最终评审发现列表。
            summary: 评审摘要文本。
        """
        findings_json = json.dumps(
            [f.model_dump() for f in findings],
            ensure_ascii=False,
        )
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO reviews (task_id, pr_url, findings_json, summary) VALUES (?, ?, ?, ?)",
                (task_id, pr_url, findings_json, summary),
            )
            conn.commit()
        logger.info("已保存评审记录: task_id=%s", task_id)

    # ── 历史记录查询 ──────────────────────────────────────

    async def get_history(self, pr_url: str, limit: int = 5) -> list[dict[str, Any]]:
        """查询指定 PR 的历史评审记录。

        Args:
            pr_url: PR URL。
            limit: 最多返回的记录数。

        Returns:
            按时间倒序排列的记录列表。
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT task_id, pr_url, findings_json, summary, created_at "
                "FROM reviews WHERE pr_url = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (pr_url, limit),
            )
            rows = cursor.fetchall()
            return [
                {
                    "task_id": row[0],
                    "pr_url": row[1],
                    "findings_json": row[2],
                    "summary": row[3],
                    "created_at": row[4],
                }
                for row in rows
            ]

    # ── 修复验证对比 ──────────────────────────────────────

    async def compare(
        self,
        pr_url: str,
        current_findings: list[ReviewFinding],
    ) -> HistoryComparison:
        """对比本次评审与上次评审，标记每条发现的修复状态。

        对比规则（基于 file + line 的唯一键匹配）：
        - 上次存在、本次不存在 → fixed（已修复）
        - 上次不存在、本次存在 → new（新引入）
        - 上次存在、本次仍存在 → unresolved（未处理）

        Args:
            pr_url: PR URL。
            current_findings: 本次评审的发现列表。

        Returns:
            包含修复状态标注和对比摘要的完整结果。
        """
        # 获取上一次评审记录
        records = await self.get_history(pr_url, limit=1)
        if len(records) == 0:
            # 没有历史记录，所有发现标记为 new
            for f in current_findings:
                f.repair_status = RepairStatus.NEW
            return HistoryComparison(
                current_task_id="",
                previous_task_id=None,
                comparison=ComparisonSummary(
                    new_count=len(current_findings),
                ),
                new_items=current_findings,
            )

        previous_record = records[0]  # 最新记录 = 上一次评审
        previous_findings_list = json.loads(previous_record["findings_json"])
        previous_keys: set[tuple[str, int]] = set()
        for f in previous_findings_list:
            previous_keys.add((f["file"], f["line"]))

        fixed_count = 0
        new_count = 0
        unresolved_count = 0
        fixed_items: list[ReviewFinding] = []
        new_items: list[ReviewFinding] = []
        unresolved_items: list[ReviewFinding] = []

        for f in current_findings:
            key = (f.file, f.line)
            if key in previous_keys:
                f.repair_status = RepairStatus.UNRESOLVED
                unresolved_count += 1
                unresolved_items.append(f)
                previous_keys.discard(key)  # 标记为已匹配
            else:
                f.repair_status = RepairStatus.NEW
                new_count += 1
                new_items.append(f)

        # 剩余的 previous_keys 是已修复的
        for f_data in previous_findings_list:
            key = (f_data["file"], f_data["line"])
            if key in previous_keys:
                fixed_count += 1
                fixed_items.append(ReviewFinding(
                    agent=f_data.get("agent", "arbitrator"),
                    severity=f_data.get("severity", "low"),
                    risk_level=f_data.get("risk_level", "green"),
                    repair_status=RepairStatus.FIXED,
                    file=f_data["file"],
                    line=f_data["line"],
                    title=f_data.get("title", ""),
                    description=f_data.get("description", ""),
                    suggestion=f_data.get("suggestion", ""),
                    category=f_data.get("category", ""),
                ))

        logger.info(
            "修复验证对比完成: PR=%s, fixed=%d, new=%d, unresolved=%d",
            pr_url, fixed_count, new_count, unresolved_count,
        )

        return HistoryComparison(
            current_task_id="",
            previous_task_id=previous_record["task_id"],
            comparison=ComparisonSummary(
                fixed_count=fixed_count,
                new_count=new_count,
                unresolved_count=unresolved_count,
            ),
            fixed_items=fixed_items,
            new_items=new_items,
            unresolved_items=unresolved_items,
        )

    # ── 内部工具 ──────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """获取 SQLite 连接。"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
