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

const manualPendingCount = computed(() => {
  if (!result.value?.findings) return 0
  return result.value.findings.filter(f => f.human_status === 'pending').length
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
    const res = await getReviewResult(id)
    if (res && res.status === 'completed') {
      result.value = res
      polling.value = false
      await loadHistory(id)
      return
    }
    if (res && res.status === 'failed') {
      error.value = '评审失败，请重试'
      polling.value = false
      return
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
</script>

<template>
  <div class="home">
    <h1>☀️ AI PR Reviewer</h1>
    <p class="subtitle">多 Agent 协作代码评审系统</p>
    <ReviewForm @review-started="handleReviewStarted" />

    <div v-if="polling" class="polling">
      <span class="spinner"></span> 太阳神之眼正在审视代码...
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="result">
      <p class="summary">{{ result.summary }}</p>

      <div v-if="manualPendingCount > 0" class="pending-count">
        待确认: {{ manualPendingCount }} 项
      </div>

      <ComparisonView
        v-if="history"
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
