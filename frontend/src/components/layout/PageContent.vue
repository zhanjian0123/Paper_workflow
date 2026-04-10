<template>
  <div class="page-content" :style="contentStyle">
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * PageContent - 页面内容区域组件
 *
 * 提供统一的垂直间距系统
 *
 * Props:
 * - spacing: 垂直间距 ('tight', 'default', 'loose')
 *   - tight: space-y-4
 *   - default: space-y-6
 *   - loose: space-y-8
 */

const props = defineProps({
  spacing: {
    type: String,
    default: 'default',
    validator: (value) => ['tight', 'default', 'loose'].includes(value)
  }
})

const spacingMap = {
  tight: 'var(--space-4)',
  default: 'var(--space-6)',
  loose: 'var(--space-8)'
}

const contentStyle = computed(() => ({
  display: 'flex',
  flexDirection: 'column',
  gap: spacingMap[props.spacing]
}))
</script>

<style scoped>
.page-content {
  flex: 1;
}
</style>
