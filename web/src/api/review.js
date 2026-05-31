const BASE_URL = '/api/v1'

/**
 * 提交 PR 评审任务。
 * @param {string} prUrl - GitHub/GitLab PR URL
 * @returns {Promise<{task_id: string, status: string}>}
 */
export async function submitReview(prUrl, reviewMode = 'auto') {
  const resp = await fetch(`${BASE_URL}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pr_url: prUrl, review_mode: reviewMode }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.detail || `请求失败: ${resp.status}`)
  }
  return resp.json()
}

/**
 * 提交评审反馈（👍/👎）。
 * @param {string} taskId - 任务 ID
 * @param {number} findingIndex - 发现项索引
 * @param {string} feedback - "up" | "down"
 */
export async function submitFeedback(taskId, findingIndex, feedback) {
  const resp = await fetch(`${BASE_URL}/review/${encodeURIComponent(taskId)}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ finding_index: findingIndex, feedback }),
  })
  if (!resp.ok) throw new Error(`提交反馈失败: ${resp.status}`)
}

/**
 * 查询修复验证对比数据。
 * @param {string} taskId - 任务 ID
 * @returns {Promise<{comparison: Object, fixed_items: Array, new_items: Array, unresolved_items: Array}>}
 */
export async function getReviewHistory(taskId) {
  const resp = await fetch(`${BASE_URL}/review/${encodeURIComponent(taskId)}/history`)
  if (!resp.ok) throw new Error(`查询历史失败: ${resp.status}`)
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
