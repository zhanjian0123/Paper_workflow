<template>
  <div class="content-container" :class="[sizeClass, paddingClass]">
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * ContentContainer - 内容容器组件
 *
 * 建立"黄金宽度"容器，约束内容最大宽度，确保视觉居中
 *
 * Props:
 * - size: 容器尺寸 ('sm', 'md', 'lg', 'xl', '2xl', 'full')
 *   - sm: 640px - 适用于窄表单、登录页
 *   - md: 768px - 适用于中等宽度内容
 *   - lg: 1024px - 适用于一般列表
 *   - xl: 1280px - 适用于主列表和详情
 *   - 2xl: 1440px - 默认，适用于仪表盘和宽桌面
 *   - full: 100% - 特殊场景，不推荐
 * - padding: 内边距 ('default', 'none', 'compact')
 */

const props = defineProps({
  size: {
    type: String,
    default: '2xl',
    validator: (value) => ['sm', 'md', 'lg', 'xl', '2xl', 'full'].includes(value)
  },
  padding: {
    type: String,
    default: 'default',
    validator: (value) => ['default', 'none', 'compact'].includes(value)
  }
})

const sizeMap = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1440px',
  full: '100%'
}

const sizeClass = computed(() => `container--${props.size}`)
const paddingClass = computed(() => `container-padding--${props.padding}`)
</script>

<style scoped>
.content-container {
  --container-max-width: 1440px;
  --container-padding-inline: var(--space-4);
  margin-left: auto;
  margin-right: auto;
  width: 100%;
  max-width: var(--container-max-width);
  padding-left: var(--container-padding-inline);
  padding-right: var(--container-padding-inline);
}

.container--sm {
  --container-max-width: 640px;
}

.container--md {
  --container-max-width: 768px;
}

.container--lg {
  --container-max-width: 1024px;
}

.container--xl {
  --container-max-width: 1280px;
}

.container--2xl {
  --container-max-width: 1440px;
}

.container--full {
  --container-max-width: 100%;
}

.container-padding--none {
  --container-padding-inline: 0;
}

.container-padding--compact {
  --container-padding-inline: var(--space-3);
}

@media (min-width: 640px) {
  .container-padding--default,
  .container-padding--compact {
    --container-padding-inline: var(--space-4);
  }
}

@media (min-width: 768px) {
  .container-padding--default {
    --container-padding-inline: var(--space-8);
  }

  .container-padding--compact {
    --container-padding-inline: var(--space-6);
  }
}

@media (min-width: 1024px) {
  .container-padding--default {
    --container-padding-inline: var(--space-12);
  }

  .container-padding--compact {
    --container-padding-inline: var(--space-8);
  }
}
</style>
