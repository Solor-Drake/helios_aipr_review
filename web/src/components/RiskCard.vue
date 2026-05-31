<script setup>
import { ref } from 'vue'

const props = defineProps({
  finding: { type: Object, required: true },
  taskId: { type: String, default: '' },
  findingIndex: { type: Number, default: 0 },
})

const emit = defineEmits(['human-review'])

const humanStatus = ref(props.finding.human_status || 'pending')

function riskClass(level) {
  return `risk-${level}`
}

function setHumanStatus(status) {
  humanStatus.value = status
  emit('human-review', { index: props.findingIndex, status })
}
</script>

<template>
  <div :class="['risk-card', riskClass(finding.risk_level)]">
    <div class="risk-header">
      <span class="severity-badge">{{ finding.severity }}</span>
      <span class="agent-badge">{{ finding.agent }}</span>
      <span v-if="finding.repair_status !== 'new'" class="repair-badge">
        {{ finding.repair_status }}
      </span>
      <span v-if="finding.review_mode === 'manual'" class="human-badge" :class="humanStatus">
        {{ humanStatus === 'pending' ? '待确认' : humanStatus === 'confirmed_fix' ? '已确认修复' : humanStatus === 'ai_correct' ? 'AI正确' : '误报' }}
      </span>
    </div>
    <h4>{{ finding.title }}</h4>
    <p class="file-loc">{{ finding.file }}:{{ finding.line }}</p>
    <p class="desc">{{ finding.description }}</p>
    <pre class="suggestion">{{ finding.suggestion }}</pre>

    <div v-if="finding.review_mode === 'manual'" class="human-actions">
      <button class="btn-fix" @click="setHumanStatus('confirmed_fix')">✅ 确认修复</button>
      <button class="btn-correct" @click="setHumanStatus('ai_correct')">👍 AI正确</button>
      <button class="btn-false" @click="setHumanStatus('false_positive')">👎 误报</button>
    </div>
  </div>
</template>
