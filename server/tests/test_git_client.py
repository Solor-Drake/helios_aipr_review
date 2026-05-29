"""
git_client.py 单元测试。

测试 URL 解析、平台自动识别、API 调用（mock HTTP）。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import httpx

from server.app.git_client import (
    parse_pr_url,
    PRInfo,
    FileChange,
    create_git_client,
    GitHubClient,
    GitLabClient,
)


# ── URL 解析测试 ──────────────────────────────────────────────


class TestParsePRUrl:
    """测试 parse_pr_url 函数。"""

    def test_parse_github_url(self) -> None:
        pr_info = parse_pr_url("https://github.com/owner/repo/pull/42")
        assert pr_info.platform == "github"
        assert pr_info.owner == "owner"
        assert pr_info.repo == "repo"
        assert pr_info.pr_number == 42

    def test_parse_gitlab_url(self) -> None:
        pr_info = parse_pr_url(
            "https://gitlab.com/group/project/-/merge_requests/99"
        )
        assert pr_info.platform == "gitlab"
        assert pr_info.owner == "group"
        assert pr_info.repo == "project"
        assert pr_info.pr_number == 99

    def test_parse_url_trailing_slash(self) -> None:
        """URL 末尾有斜杠也能正确解析。"""
        pr_info = parse_pr_url("https://github.com/o/r/pull/1/")
        assert pr_info.pr_number == 1

    def test_parse_invalid_url(self) -> None:
        with pytest.raises(ValueError, match="无法识别"):
            parse_pr_url("https://example.com/not/a/pr")

    def test_parse_non_pr_url(self) -> None:
        """不是 PR 的 GitHub URL 也报错。"""
        with pytest.raises(ValueError, match="无法识别"):
            parse_pr_url("https://github.com/o/r/issues/1")


# ── 工厂函数测试 ──────────────────────────────────────────────


class TestCreateGitClient:
    """测试 create_git_client 工厂函数。"""

    def test_create_github_client(self) -> None:
        client = create_git_client("https://github.com/o/r/pull/1")
        assert isinstance(client, GitHubClient)

    def test_create_gitlab_client(self) -> None:
        client = create_git_client(
            "https://gitlab.com/o/r/-/merge_requests/1"
        )
        assert isinstance(client, GitLabClient)

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(ValueError):
            create_git_client("https://invalid.com/pr")


# ── GitHub 客户端 HTTP mock 测试 ──────────────────────────────


GITHUB_PR_INFO = PRInfo(
    platform="github",
    owner="test-owner",
    repo="test-repo",
    pr_number=1,
    api_url="https://api.github.com",
)


class TestGitHubClient:
    """测试 GitHubClient 的 API 调用（mock HTTP）。"""

    @pytest.mark.asyncio
    async def test_get_pr_diff(self) -> None:
        client = GitHubClient()
        mock_response = httpx.Response(
            200,
            text="diff --git a/file.py b/file.py\n@@ -1 +1 @@\n-old\n+new",
            request=httpx.Request("GET", "http://test"),
        )
        with patch.object(client._http, "get", AsyncMock(return_value=mock_response)):
            diff = await client.get_pr_diff(GITHUB_PR_INFO)
            assert "diff --git" in diff
        await client.close()

    @pytest.mark.asyncio
    async def test_get_pr_files(self) -> None:
        client = GitHubClient()
        files_json = [
            {
                "filename": "src/main.py",
                "status": "modified",
                "patch": "@@ -1 +1 @@\n-old\n+new",
                "contents_url": None,
            },
            {
                "filename": "src/new.py",
                "status": "added",
                "patch": None,
                "contents_url": None,
            },
        ]
        resp_files = httpx.Response(
            200,
            json=files_json,
            request=httpx.Request("GET", "http://test"),
        )
        with patch.object(client._http, "get", AsyncMock(return_value=resp_files)):
            files = await client.get_pr_files(GITHUB_PR_INFO)
            assert len(files) == 2
            assert files[0].filename == "src/main.py"
            assert files[0].status == "modified"
        await client.close()

    @pytest.mark.asyncio
    async def test_get_pr_diff_http_error(self) -> None:
        client = GitHubClient()
        mock_response = httpx.Response(
            404,
            text="Not Found",
            request=httpx.Request("GET", "http://test"),
        )
        with patch.object(client._http, "get", AsyncMock(return_value=mock_response)):
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_pr_diff(GITHUB_PR_INFO)
        await client.close()


GITLAB_PR_INFO = PRInfo(
    platform="gitlab",
    owner="test-group",
    repo="test-project",
    pr_number=1,
    api_url="https://gitlab.com/api/v4",
)


class TestGitLabClient:
    """测试 GitLabClient 的 API 调用（mock HTTP）。"""

    @pytest.mark.asyncio
    async def test_get_pr_diff(self) -> None:
        client = GitLabClient()
        client._token = "fake-token"  # mock token，绕过延迟校验
        resp_json = {
            "changes": [
                {"diff": "diff --git a/file.py b/file.py\n-old\n+new"},
                {"diff": "diff --git a/main.py b/main.py\n-old\n+new"},
            ]
        }
        mock_response = httpx.Response(
            200,
            json=resp_json,
            request=httpx.Request("GET", "http://test"),
        )
        with patch.object(client._http, "get", AsyncMock(return_value=mock_response)):
            diff = await client.get_pr_diff(GITLAB_PR_INFO)
            assert "diff --git" in diff
            # 两个文件的 diff 用换行拼接
            assert diff.count("diff --git") == 2
        await client.close()

    @pytest.mark.asyncio
    async def test_get_pr_files(self) -> None:
        client = GitLabClient()
        client._token = "fake-token"  # mock token
        resp_json = {
            "changes": [
                {
                    "new_path": "src/main.py",
                    "diff": "@@ -1 +1 @@",
                }
            ]
        }
        mock_response = httpx.Response(
            200,
            json=resp_json,
            request=httpx.Request("GET", "http://test"),
        )
        with patch.object(client._http, "get", AsyncMock(return_value=mock_response)):
            files = await client.get_pr_files(GITLAB_PR_INFO)
            assert len(files) == 1
            assert files[0].filename == "src/main.py"
        await client.close()

    @pytest.mark.asyncio
    async def test_post_comment(self) -> None:
        client = GitLabClient()
        client._token = "fake-token"  # mock token
        mock_response = httpx.Response(
            201,
            json={"id": 1},
            request=httpx.Request("POST", "http://test"),
        )
        with patch.object(client._http, "post", AsyncMock(return_value=mock_response)):
            await client.post_comment(GITLAB_PR_INFO, "评审报告内容")
            # 不抛异常即成功
        await client.close()
