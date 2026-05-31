<script setup>
import { ref } from 'vue'
import { getReviewResult, getReviewHistory } from '../api/review.js'
import ReviewForm from '../components/ReviewForm.vue'
import ResultTabs from '../components/ResultTabs.vue'
import RiskCard from '../components/RiskCard.vue'
import ComparisonView from '../components/ComparisonView.vue'
import FeedbackButton from '../components/FeedbackButton.vue'

const taskId = ref('')
const result = ref(null)
const history = ref(null)
const polling = ref(false)
const error = ref('')

async function handleReviewStarted(id) {
  taskId.value = id
  result.value = null
  history.value = null
  error.value = ''
  await pollResult(id)
}

async function pollResult(id) {
  polling.value = true
  const maxAttempts = 60
  for (let i = 0; i < maxAttempts; i++) {
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
</script>

<template>
  <div class="home">
    <h1>AI PR Reviewer</h1>
    <ReviewForm @review-started="handleReviewStarted" />

    <div v-if="polling" class="polling">评审中，请稍候...</div>
    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="result">
      <p class="summary">{{ result.summary }}</p>

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
        >
          <FeedbackButton
            v-if="taskId"
            :task-id="taskId"
            :finding-index="i"
          />
        </RiskCard>
      </ResultTabs>
    </template>
  </div>
</template>
