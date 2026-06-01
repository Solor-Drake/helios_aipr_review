<script setup>
import { ref, computed } from 'vue'
import { getReviewResult, getReviewHistory } from '../api/review.js'
import ReviewForm from '../components/ReviewForm.vue'
import ResultTabs from '../components/ResultTabs.vue'
import RiskCard from '../components/RiskCard.vue'
import ComparisonView from '../components/ComparisonView.vue'

const taskId = ref('')
const result = ref(null)
const history = ref(null)
const polling = ref(false)
const error = ref('')

const isManualMode = computed(() => {
  if (!result.value?.findings || result.value.findings.length === 0) return false
  return result.value.findings[0].review_mode === 'manual'
})

const manualPendingCount = computed(() => {
  const statuses = { pending: 0, confirmed_fix: 0, ai_correct: 0, false_positive: 0 }
  if (!result.value?.findings) return statuses
  result.value.findings.forEach(f => {
    const s = f.human_status || 'pending'
    if (statuses.hasOwnProperty(s)) statuses[s]++
  })
  return statuses
})

async function handleReviewStarted(id) {
  taskId.value = id
  result.value = null
  history.value = null
  error.value = ''
  await pollResult(id)
}

async function pollResult(id) {
  polling.value = true
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 2000))
    try {
      const res = await getReviewResult(id)
      if (!res) continue  // 404，继续轮询
      if (res.status === 'completed') {
        result.value = res
        polling.value = false
        await loadHistory(id)
        return
      }
      if (res.status === 'failed') {
        error.value = res.summary || '评审失败，请重试'
        polling.value = false
        return
      }
    } catch (e) {
      // 网络异常等意外错误，继续轮询直到超时
      if (i >= 59) {
        error.value = `评审超时或连接异常: ${e.message}`
        polling.value = false
        return
      }
    }
  }
  polling.value = false
  error.value = '评审超时，请重试'
}

async function loadHistory(id) {
  try {
    history.value = await getReviewHistory(id)
  } catch {
    history.value = null
  }
}

function onHumanReview({ index, status }) {
  if (!result.value?.findings) return
  result.value.findings[index].human_status = status
}

function hasComparison(c) {
  return c && (c.fixed_count > 0 || c.new_count > 0 || c.unresolved_count > 0)
}
</script>

<template>
  <div class="home">
    <h1>☀️ AI PR Reviewer</h1>
    <p class="subtitle">多 Agent 协作代码评审系统</p>
    <ReviewForm @review-started="handleReviewStarted" />

    <div v-if="polling" class="polling">
      <span class="spinner"></span> 太阳神之眼正在审视代码...
    </div>
    <div v-if="error" class="error-box">
      <span class="error-icon">⚠️</span>
      <span class="error-text">{{ error }}</span>
    </div>

    <template v-if="result">
      <p class="summary">{{ result.summary }}</p>

      <div v-if="isManualMode" class="pending-count">
        待确认: {{ manualPendingCount.pending }} |
        已确认: {{ manualPendingCount.confirmed_fix + manualPendingCount.ai_correct }} |
        误报: {{ manualPendingCount.false_positive }}
      </div>

      <ComparisonView
        v-if="history && hasComparison(history.comparison)"
        :comparison="history.comparison"
        :fixed-items="history.fixed_items"
        :unresolved-items="history.unresolved_items"
      />

      <ResultTabs :findings="result.findings" v-slot="{ findings }">
        <RiskCard
          v-for="(f, i) in findings"
          :key="i"
          :finding="f"
          :task-id="taskId"
          :finding-index="i"
          @human-review="onHumanReview"
        />
      </ResultTabs>
    </template>
  </div>
</template>
