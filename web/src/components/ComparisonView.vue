<script setup>
defineProps({
  comparison: { type: Object, required: true },
  fixedItems: { type: Array, default: () => [] },
  unresolvedItems: { type: Array, default: () => [] },
})
</script>

<template>
  <div class="comparison-view">
    <div class="summary">
      <span class="fixed">✅ 已修复: {{ comparison.fixed_count }}</span>
      <span class="new">🆕 新引入: {{ comparison.new_count }}</span>
      <span class="unresolved">⚠️ 未处理: {{ comparison.unresolved_count }}</span>
    </div>
    <div v-if="fixedItems.length" class="fixed-list">
      <h4>已修复项</h4>
      <ul>
        <li v-for="(item, i) in fixedItems" :key="i">
          {{ item.file }}:{{ item.line }} — {{ item.title }}
        </li>
      </ul>
    </div>
    <div v-if="unresolvedItems.length" class="unresolved-list">
      <h4>未处理项</h4>
      <ul>
        <li v-for="(item, i) in unresolvedItems" :key="i">
          {{ item.file }}:{{ item.line }} — {{ item.title }}
        </li>
      </ul>
    </div>
  </div>
</template>
