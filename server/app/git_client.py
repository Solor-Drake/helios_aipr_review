"""
Git 平台 API 客户端模块。

封装 GitHub 和 GitLab 的 API 调用，提供统一的 PR diff 拉取、文件内容获取、
评论回写接口。通过 URL 自动识别平台，调用方无需关心底层差异。
"""

from __future__ import annotations

import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Any

import httpx
from github import Github, Auth
from github.PullRequest import PullRequest as GhPullRequest

from server.app.config import get_settings

logger = logging.getLogger(__name__)


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class PRInfo:
    """从 PR URL 解析出的结构化信息。"""

    platform: str          # "github" | "gitlab"
    owner: str             # 仓库所有者
    repo: str              # 仓库名
    pr_number: int         # PR 编号
    api_url: str           # 平台 API 根地址


@dataclass
class FileChange:
    """单个文件的变更信息。"""

    filename: str          # 文件路径
    status: str            # "added" | "modified" | "removed" | "renamed"
    patch: str | None      # unified diff 文本
    raw_content: str | None  # 变更后的完整文件内容（base64 解码后）


# ── URL 解析 ──────────────────────────────────────────────────


def parse_pr_url(pr_url: str) -> PRInfo:
    """从 GitHub 或 GitLab PR URL 解析出结构化信息。

    Args:
        pr_url: 完整的 PR URL。
            GitHub 格式: https://github.com/{owner}/{repo}/pull/{number}
            GitLab 格式: https://gitlab.com/{owner}/{repo}/-/merge_requests/{number}

    Returns:
        PRInfo 结构体。

    Raises:
        ValueError: URL 格式无法识别时抛出。
    """
    pr_url = pr_url.rstrip("/")

    # GitHub: https://github.com/owner/repo/pull/42
    gh_match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)",
        pr_url,
    )
    if gh_match:
        owner, repo, number = gh_match.groups()
        return PRInfo(
            platform="github",
            owner=owner,
            repo=repo,
            pr_number=int(number),
            api_url="https://api.github.com",
        )

    # GitLab: https://gitlab.com/owner/repo/-/merge_requests/42
    gl_match = re.match(
        r"https?://gitlab\.com/([^/]+)/([^/]+)/-/merge_requests/(\d+)",
        pr_url,
    )
    if gl_match:
        owner, repo, number = gl_match.groups()
        return PRInfo(
            platform="gitlab",
            owner=owner,
            repo=repo,
            pr_number=int(number),
            api_url="https://gitlab.com/api/v4",
        )

    raise ValueError(f"无法识别的 PR URL 格式: {pr_url}")


# ── 抽象基类 ──────────────────────────────────────────────────


class BaseGitClient(ABC):
    """Git 平台客户端抽象基类。"""

    @abstractmethod
    async def get_pr_diff(self, pr_info: PRInfo) -> str:
        """获取 PR 的 unified diff 文本。"""
        ...

    @abstractmethod
    async def get_pr_files(self, pr_info: PRInfo) -> list[FileChange]:
        """获取 PR 中所有变更文件的 diff 及完整内容。"""
        ...

    @abstractmethod
    async def post_comment(self, pr_info: PRInfo, body: str) -> None:
        """在 PR 下发布评论（评审报告）。"""
        ...


# ── GitHub 客户端 ─────────────────────────────────────────────


class GitHubClient(BaseGitClient):
    """GitHub API 客户端，基于 PyGithub。

    使用 Token 认证，支持 github.com 和 GitHub Enterprise。
    Token 校验延迟到首次 API 调用时执行，避免 mock 测试时阻断对象创建。
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._token = settings.github.github_token
        self._gh: Github | None = None
        self._http = httpx.AsyncClient(
            timeout=30,
        )

    def _ensure_token(self) -> str | None:
        """返回 GitHub Token，未配置时返回 None（降级为未认证模式）。

        未认证模式下 API 限速为 60 次/小时，认证后为 5000 次/小时。
        """
        return self._token or None

    def _ensure_gh(self) -> Github | None:
        """延迟初始化 PyGithub 客户端，无 token 时返回 None。"""
        if self._gh is None:
            token = self._ensure_token()
            if token:
                auth = Auth.Token(token)
                self._gh = Github(auth=auth)
            else:
                self._gh = Github()  # 未认证模式，限速 60次/小时
        return self._gh

    # ── 公共接口 ──────────────────────────────────────────

    async def get_pr_diff(self, pr_info: PRInfo) -> str:
        """通过 GitHub REST API 获取 PR 的 unified diff。"""
        url = (
            f"https://api.github.com/repos"
            f"/{pr_info.owner}/{pr_info.repo}"
            f"/pulls/{pr_info.pr_number}"
        )
        headers = {"Accept": "application/vnd.github.v3.diff"}
        token = self._ensure_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = await self._http.get(url, headers=headers)
        response.raise_for_status()
        logger.info(
            "获取 GitHub PR #%d diff 成功，大小 %d 字节",
            pr_info.pr_number,
            len(response.text),
        )
        return response.text

    async def get_pr_files(self, pr_info: PRInfo) -> list[FileChange]:
        """获取 PR 中所有文件的变更详情。

        包括文件状态（新增/修改/删除）、patch 和完整内容。
        """
        url = (
            f"https://api.github.com/repos"
            f"/{pr_info.owner}/{pr_info.repo}"
            f"/pulls/{pr_info.pr_number}/files"
        )
        headers = {"Accept": "application/vnd.github.v3+json"}
        token = self._ensure_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = await self._http.get(url, headers=headers)
        resp.raise_for_status()
        files_data = resp.json()

        changes: list[FileChange] = []
        for f in files_data:
            raw = None
            if f.get("contents_url"):
                try:
                    raw = await self._fetch_raw_content(f["contents_url"])
                except Exception:
                    raw = None
            changes.append(FileChange(
                filename=f["filename"],
                status=f.get("status", "modified"),
                patch=f.get("patch"),
                raw_content=raw,
            ))

        logger.info("获取 GitHub PR #%d 文件列表: %d 个文件", pr_info.pr_number, len(changes))
        return changes

    async def post_comment(self, pr_info: PRInfo, body: str) -> None:
        """在指定 PR 下发布评论。"""
        gh_pr = self._get_pr_obj(pr_info)
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, gh_pr.create_issue_comment, body)
        logger.info("已向 GitHub PR #%d 发布评论", pr_info.pr_number)

    # ── 内部方法 ──────────────────────────────────────────

    def _get_pr_obj(self, pr_info: PRInfo) -> GhPullRequest:
        """获取 PyGithub 的 PullRequest 对象。"""
        gh = self._ensure_gh()
        repo = gh.get_repo(f"{pr_info.owner}/{pr_info.repo}")
        return repo.get_pull(pr_info.pr_number)

    async def _fetch_raw_content(self, contents_url: str) -> str | None:
        """获取文件的原始内容（base64 解码）。"""
        try:
            raw_headers = {"Accept": "application/vnd.github.v3.raw"}
            token = self._ensure_token()
            if token:
                raw_headers["Authorization"] = f"Bearer {token}"
            resp = await self._http.get(contents_url, headers=raw_headers)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None

    async def close(self) -> None:
        """关闭 HTTP 客户端连接。"""
        await self._http.aclose()


# ── GitLab 客户端 ─────────────────────────────────────────────


class GitLabClient(BaseGitClient):
    """GitLab API 客户端，基于 httpx。

    支持 gitlab.com 和自托管 GitLab 实例。
    Token 校验延迟到首次 API 调用时执行。
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._token = settings.github.gitlab_token
        self._http = httpx.AsyncClient(
            timeout=30,
        )

    def _ensure_token(self) -> str | None:
        """返回 GitLab Token，未配置时返回 None（降级为未认证模式）。"""
        return self._token or None

    async def get_pr_diff(self, pr_info: PRInfo) -> str:
        """获取 GitLab MR 的变更 diff。"""
        project_id = self._encode_project_id(pr_info)
        url = (
            f"{pr_info.api_url}/projects/{project_id}"
            f"/merge_requests/{pr_info.pr_number}/changes"
        )
        resp = await self._http.get(
            url,
            headers=({"PRIVATE-TOKEN": token} if (token := self._ensure_token()) else None),
        )
        resp.raise_for_status()
        data = resp.json()
        # GitLab 返回每个文件的 diff，拼接成 unified diff
        diffs: list[str] = []
        for change in data.get("changes", []):
            diffs.append(change.get("diff", ""))
        logger.info(
            "获取 GitLab MR !%d diff 成功，%d 个文件变更",
            pr_info.pr_number,
            len(diffs),
        )
        return "\n".join(diffs)

    async def get_pr_files(self, pr_info: PRInfo) -> list[FileChange]:
        """获取 GitLab MR 的所有文件变更详情。"""
        project_id = self._encode_project_id(pr_info)
        url = (
            f"{pr_info.api_url}/projects/{project_id}"
            f"/merge_requests/{pr_info.pr_number}/changes"
        )
        resp = await self._http.get(
            url,
            headers=({"PRIVATE-TOKEN": token} if (token := self._ensure_token()) else None),
        )
        resp.raise_for_status()
        data = resp.json()

        changes: list[FileChange] = []
        for c in data.get("changes", []):
            changes.append(FileChange(
                filename=c.get("new_path", ""),
                status="modified",
                patch=c.get("diff"),
                raw_content=None,  # GitLab changes API 不含完整内容
            ))
        logger.info(
            "获取 GitLab MR !%d 文件列表: %d 个文件",
            pr_info.pr_number,
            len(changes),
        )
        return changes

    async def post_comment(self, pr_info: PRInfo, body: str) -> None:
        """在 GitLab MR 下发布评论。"""
        project_id = self._encode_project_id(pr_info)
        url = (
            f"{pr_info.api_url}/projects/{project_id}"
            f"/merge_requests/{pr_info.pr_number}/notes"
        )
        resp = await self._http.post(
            url,
            json={"body": body},
            headers=({"PRIVATE-TOKEN": token} if (token := self._ensure_token()) else None),
        )
        resp.raise_for_status()
        logger.info("已向 GitLab MR !%d 发布评论", pr_info.pr_number)

    async def close(self) -> None:
        """关闭 HTTP 客户端连接。"""
        await self._http.aclose()

    @staticmethod
    def _encode_project_id(pr_info: PRInfo) -> str:
        """GitLab 要求 project ID 为 URL 编码的 'owner/repo'。"""
        return f"{pr_info.owner}%2F{pr_info.repo}"


# ── 工厂函数 ──────────────────────────────────────────────────


def create_git_client(pr_url: str) -> BaseGitClient:
    """根据 PR URL 自动创建对应的平台客户端。

    Args:
        pr_url: GitHub 或 GitLab 的 PR URL。

    Returns:
        对应平台的 BaseGitClient 实例。

    Raises:
        ValueError: URL 格式不支持时抛出。
    """
    pr_info = parse_pr_url(pr_url)
    if pr_info.platform == "github":
        return GitHubClient()
    if pr_info.platform == "gitlab":
        return GitLabClient()
    raise ValueError(f"不支持的平台: {pr_info.platform}")
