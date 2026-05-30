<script setup>
import { ref } from 'vue'
import { submitReview } from '../api/review.js'

const emit = defineEmits(['review-started'])

const prUrl = ref('')
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
    const result = await submitReview(prUrl.value.trim())
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
    <input
      v-model="prUrl"
      type="url"
      placeholder="https://github.com/owner/repo/pull/42"
      :disabled="loading"
    />
    <button type="submit" :disabled="loading">
      {{ loading ? '提交中...' : '开始评审' }}
    </button>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>
