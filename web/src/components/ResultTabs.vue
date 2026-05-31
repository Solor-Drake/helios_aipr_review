<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  findings: { type: Array, required: true },
})

const tabs = [
  { key: 'all', label: '全部' },
  { key: 'security', label: '安全' },
  { key: 'performance', label: '性能' },
  { key: 'logic', label: '逻辑' },
  { key: 'style', label: '风格' },
]
const activeTab = ref('all')

const filteredFindings = computed(() => {
  if (activeTab.value === 'all') return props.findings
  return props.findings.filter(f => f.agent === activeTab.value)
})
</script>

<template>
  <div class="result-tabs">
    <nav>
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span class="count" v-if="tab.key === 'all'">
          ({{ findings.length }})
        </span>
        <span class="count" v-else>
          ({{ findings.filter(f => f.agent === tab.key).length }})
        </span>
      </button>
    </nav>
    <slot :findings="filteredFindings" />
  </div>
</template>
