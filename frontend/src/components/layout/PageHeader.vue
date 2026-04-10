<template>
  <div class="page-header" :class="sizeClass">
    <div class="page-header-content">
      <div class="page-header-info">
        <h1 v-if="title" class="page-title">{{ title }}</h1>
        <p v-if="subtitle" class="page-subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.actions" class="page-header-actions">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * PageHeader - 页面头部组件
 *
 * 统一的页面标题区域，确保视觉基准线对齐
 *
 * Props:
 * - title: 页面标题
 * - subtitle: 副标题/描述
 * - size: 尺寸 ('default', 'compact')
 */

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  subtitle: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'default',
    validator: (value) => ['default', 'compact'].includes(value)
  }
})

const sizeClass = computed(() => `page-header--${props.size}`)
</script>

<style scoped>
.page-header {
  margin-bottom: var(--space-2);
  padding: 0;
}

.page-header--compact {
  margin-bottom: var(--space-4);
}

.page-header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-6);
}

.page-header-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.page-title {
  font-size: var(--text-4xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin: 0;
  letter-spacing: var(--tracking-tighter);
  line-height: var(--leading-tight);
}

.page-subtitle {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin: 0;
  max-width: 72ch;
  line-height: var(--leading-relaxed);
}

.page-header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  flex-shrink: 0;
}

/* 响应式 */
@media (max-width: 768px) {
  .page-header-content {
    flex-direction: column;
    align-items: stretch;
  }

  .page-title {
    font-size: var(--text-3xl);
  }

  .page-header-actions {
    justify-content: flex-start;
    width: 100%;
  }
}
</style>
