<script setup>
import { ref } from 'vue'
import { submitReview } from '../api/review.js'

const emit = defineEmits(['review-started'])

const prUrl = ref('')
const reviewMode = ref('auto')
const loading = ref(false)
const error = ref('')

async function submitForm() {
  error.value = ''
  if (!prUrl.value.trim()) {
    error.value = '请输入 PR URL'
    return
  }
  loading.value = true
  try {
    const result = await submitReview(prUrl.value.trim(), reviewMode.value)
    emit('review-started', result.task_id)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <form @submit.prevent="submitForm" class="review-form">
    <div class="form-row">
      <input
        v-model="prUrl"
        type="url"
        placeholder="https://github.com/owner/repo/pull/42"
        :disabled="loading"
      />
      <select v-model="reviewMode" :disabled="loading">
        <option value="auto">AI 自动模式</option>
        <option value="manual">人工复核模式</option>
      </select>
      <button type="submit" :disabled="loading">
        {{ loading ? '提交中...' : '开始评审' }}
      </button>
    </div>
    <div v-if="error" class="error-box">
      <span class="error-icon">⚠️</span>
      <span class="error-text">{{ error }}</span>
    </div>
  </form>
</template>
