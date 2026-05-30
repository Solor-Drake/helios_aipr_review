const BASE_URL = '/api/v1'

/**
 * 提交 PR 评审任务。
 * @param {string} prUrl - GitHub/GitLab PR URL
 * @returns {Promise<{task_id: string, status: string}>}
 */
export async function submitReview(prUrl) {
  const resp = await fetch(`${BASE_URL}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pr_url: prUrl }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.detail || `请求失败: ${resp.status}`)
  }
  return resp.json()
}

/**
 * 查询评审任务状态和结果。
 * @param {string} taskId - 任务 ID
 * @returns {Promise<{task_id: string, status: string, findings: Array}>}
 */
export async function getReviewResult(taskId) {
  const resp = await fetch(`${BASE_URL}/review/${encodeURIComponent(taskId)}`)
  if (!resp.ok) {
    if (resp.status === 404) return null
    throw new Error(`查询失败: ${resp.status}`)
  }
  return resp.json()
}
