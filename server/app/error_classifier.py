"""
错误分类与用户友好化模块。

负责捕获评审流水线中的各类原始异常，将其映射为普通用户能够理解的
中文错误信息。分类规则覆盖 GitHub API、LLM API、网络、存储等常见
故障场景。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def classify_error(exc: Exception) -> str:
    """将原始异常转换为用户可理解的错误信息。

    按优先级从高到低匹配已知错误模式，匹配命中后返回对应的中文说明；
    未命中任何已知模式时返回包含原始错误信息的通用提示。

    Args:
        exc: 评审流水线中捕获的原始异常。

    Returns:
        面向终端用户的中文错误描述字符串。
    """
    raw = str(exc)
    raw_lower = raw.lower()

    # ── L3：所有 Agent 全部失败 ────────────────────────────
    # （orchestrator 抛出的 RuntimeError，本身已为用户友好格式）

    if "所有 AI Agent 均评审失败" in raw:
        return raw

    # ── LLM / AI 服务错误 ──────────────────────────────────
    # 必须在 GitHub HTTP 状态码检测之前执行，
    # 因为 LLM 错误中也可能包含 401/403 等状态码。

    if "API 调用失败" in raw:
        inner = _extract_inner_error(raw)
        return _classify_llm_error(inner)

    # ── GitHub API 错误 ────────────────────────────────────

    if _has_http_status(raw, "403") and "rate limit" in raw_lower:
        return (
            "GitHub API 访问频率超限（HTTP 403）。\n"
            "原因：未配置 GitHub Token 时，每小时仅允许 60 次 API 请求。\n"
            "解决方法：在 .env 文件中添加 GITHUB_TOKEN=ghp_xxxx，然后重启服务。"
        )

    if _has_http_status(raw, "404"):
        return (
            "未找到指定的 PR（HTTP 404）。\n"
            "可能原因：\n"
            "  1) PR 不存在或已被删除\n"
            "  2) 仓库为私有仓库，未配置有效的 GitHub Token\n"
            "  3) PR URL 输入有误\n"
            "请检查 URL 是否正确，或在 .env 中配置 GITHUB_TOKEN。"
        )

    if _has_http_status(raw, "401"):
        return (
            "GitHub 认证失败（HTTP 401）。\n"
            "请检查 .env 文件中的 GITHUB_TOKEN 是否有效或已过期。"
        )

    # ── 网络 / 连接错误 ────────────────────────────────────

    if any(kw in raw_lower for kw in ("timeout", "timed out", "timedout")):
        return (
            "请求超时，AI 服务或 GitHub 服务响应过慢。\n"
            "请检查网络连接是否正常，或稍后重试。\n"
            "如持续出现此问题，可在 .env 中将 REQUEST_TIMEOUT 调大后重试。"
        )

    if any(kw in raw_lower for kw in ("connection", "connecterror", "refused", "unreachable")):
        return (
            "无法连接到远程服务，请检查：\n"
            "  1) 服务器是否能够访问外网\n"
            "  2) 是否需要配置网络代理\n"
            "  3) 防火墙是否阻止了对外连接"
        )

    # ── URL / 输入校验错误 ─────────────────────────────────

    if "url" in raw_lower and ("无法识别" in raw or "unrecognized" in raw_lower):
        return (
            "PR URL 格式不支持。\n"
            "当前仅支持以下格式：\n"
            "  - GitHub: https://github.com/owner/repo/pull/123\n"
            "  - GitLab: https://gitlab.com/owner/repo/-/merge_requests/123"
        )

    if "pull request" in raw_lower or "pr url" in raw_lower or "检测到" in raw:
        return (
            "PR URL 格式不正确。\n"
            "请输入完整的 GitHub 或 GitLab Pull Request 链接。"
        )

    # ── 存储错误 ───────────────────────────────────────────

    if any(kw in raw_lower for kw in ("sqlite", "database", "permission denied", "readonly")):
        return (
            "数据存储失败，服务器磁盘可能已满或目录权限不足。\n"
            "请联系管理员检查服务器磁盘空间和 data 目录写入权限。"
        )

    # ── 未知错误 ───────────────────────────────────────────

    return (
        f"评审过程发生未预期的错误。\n"
        f"错误详情：{raw[:300]}\n"
        f"如问题持续出现，请联系管理员并提供以上错误信息。"
    )


# ── 内部辅助函数 ──────────────────────────────────────────


def _has_http_status(raw: str, code: str) -> bool:
    """检测异常信息中是否包含指定 HTTP 状态码。"""
    return code in raw or f"'{code}" in raw


def _extract_inner_error(raw: str) -> str:
    """从 Agent 级别的 RuntimeError 中提取内层异常信息。

    各 Agent 的 _call_llm 失败时将原始异常包装为：
        RuntimeError("Agent <type> API 调用失败: <原始异常>")
    此函数提取 ": " 之后的部分以便进一步分类。
    """
    if "API 调用失败: " in raw:
        return raw.split("API 调用失败: ", 1)[1]
    return raw


def _classify_llm_error(inner: str) -> str:
    """对内层 LLM API 异常做二次分类。"""
    inner_lower = inner.lower()

    if any(kw in inner_lower for kw in ("401", "unauthorized", "authentication", "invalid api key")):
        return (
            "AI 服务认证失败，API Key 无效或已过期。\n"
            "请在 .env 文件中配置有效的 DASHSCOPE_API_KEY 或 DEEPSEEK_API_KEY。"
        )

    if any(kw in inner_lower for kw in ("403", "forbidden", "insufficient")):
        return (
            "AI 服务拒绝访问（403），可能是 API Key 权限不足或账户欠费。\n"
            "请登录 AI 服务平台检查账户状态和 API Key 权限。"
        )

    if any(kw in inner_lower for kw in ("429", "rate limit", "quota")):
        return (
            "AI 服务调用频率超限或配额已用完。\n"
            "请稍后重试，或登录 AI 服务平台检查 API 调用配额。"
        )

    if any(kw in inner_lower for kw in ("timeout", "timed out")):
        return (
            "AI 服务响应超时。\n"
            "当前超时设置为 120 秒，可能因网络延迟或模型负载过高导致。\n"
            "请稍后重试，或在 .env 中调大 REQUEST_TIMEOUT。"
        )

    if any(kw in inner_lower for kw in ("connection", "connect", "dns", "resolve")):
        return (
            "无法连接到 AI 服务。\n"
            "请检查服务器是否能访问外网，以及 AI 服务地址是否正确。\n"
            f"当前服务地址在 .env 的 DASHSCOPE_BASE_URL 或 DEEPSEEK_BASE_URL 中配置。"
        )

    # 未识别的 LLM 错误，保留原始信息方便排查
    return (
        f"AI 服务调用异常。\n"
        f"错误详情：{inner[:200]}"
    )
