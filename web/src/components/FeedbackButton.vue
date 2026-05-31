<script setup>
import { ref } from 'vue'
import { submitFeedback } from '../api/review.js'

const props = defineProps({
  taskId: { type: String, required: true },
  findingIndex: { type: Number, required: true },
})

const voted = ref(null)

async function vote(feedback) {
  if (voted.value) return
  voted.value = feedback
  try {
    await submitFeedback(props.taskId, props.findingIndex, feedback)
  } catch {
    voted.value = null
  }
}
</script>

<template>
  <span class="feedback-btns">
    <button
      :class="{ active: voted === 'up' }"
      @click="vote('up')"
      :disabled="voted !== null"
    >👍</button>
    <button
      :class="{ active: voted === 'down' }"
      @click="vote('down')"
      :disabled="voted !== null"
    >👎</button>
  </span>
</template>
