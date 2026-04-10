<template>
  <div class="form-section" :class="sizeClass">
    <label v-if="label" class="form-label">
      {{ label }}
      <span v-if="required" class="required-mark">*</span>
    </label>
    <div class="form-control-wrapper" :style="controlStyle">
      <slot />
    </div>
    <p v-if="hint" class="form-hint">{{ hint }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * FormSection - 表单区域组件
 *
 * 控制表单控件的最大宽度，防止过度拉伸
 *
 * Props:
 * - label: 标签文本
 * - required: 是否必填
 * - hint: 提示信息
 * - maxWidth: 最大宽度 ('sm', 'md', 'lg', 'none')
 *   - sm: 320px - 短输入（数字、日期等）
 *   - md: 480px - 中等输入（邮箱、电话等）
 *   - lg: 640px - 长输入（URL、地址等）
 *   - none: 100% - 不限制
 */

defineProps({
  label: {
    type: String,
    default: ''
  },
  required: {
    type: Boolean,
    default: false
  },
  hint: {
    type: String,
    default: ''
  },
  maxWidth: {
    type: String,
    default: 'lg',
    validator: (value) => ['sm', 'md', 'lg', 'none'].includes(value)
  }
})

const sizeMap = {
  sm: '320px',
  md: '480px',
  lg: '640px',
  none: '100%'
}

const controlStyle = computed(() => ({
  maxWidth: sizeMap[maxWidth.value]
}))
</script>

<style scoped>
.form-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.form-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.required-mark {
  color: var(--danger-base);
}

.form-control-wrapper {
  width: 100%;
}

.form-hint {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
</style>
