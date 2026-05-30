<script setup>
defineProps({
  finding: {
    type: Object,
    required: true,
  },
})

function riskClass(level) {
  return `risk-${level}`
}
</script>

<template>
  <div :class="['risk-card', riskClass(finding.risk_level)]">
    <div class="risk-header">
      <span class="severity-badge">{{ finding.severity }}</span>
      <span class="agent-badge">{{ finding.agent }}</span>
      <span class="repair-badge" v-if="finding.repair_status !== 'new'">
        {{ finding.repair_status }}
      </span>
    </div>
    <h4>{{ finding.title }}</h4>
    <p class="file-loc">{{ finding.file }}:{{ finding.line }}</p>
    <p class="desc">{{ finding.description }}</p>
    <pre class="suggestion">{{ finding.suggestion }}</pre>
  </div>
</template>
