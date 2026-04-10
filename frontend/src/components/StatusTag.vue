<template>
  <span
    class="status-tag"
    :class="[
      `status-tag--${typeClass}`,
      {
        'status-tag--dot': showDot,
        'status-tag--pulse': showDot && status === 'running',
        'status-tag--small': size === 'small',
        'status-tag--large': size === 'large'
      }
    ]"
    :style="tagStyle"
  >
    <span v-if="showDot" class="status-dot" :class="`status-dot--${typeClass}`"></span>
    <span class="status-text">{{ text }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    default: 'pending',
    validator: (value) => {
      return ['pending', 'running', 'completed', 'failed', 'cancelled'].includes(value)
    },
  },
  showDot: {
    type: Boolean,
    default: false,
  },
  size: {
    type: String,
    default: 'default',
    validator: (value) => {
      return ['small', 'default', 'large'].includes(value)
    },
  },
  effect: {
    type: String,
    default: 'light',
    validator: (value) => {
      return ['light', 'plain'].includes(value)
    },
  },
  type: {
    type: String,
    default: '',
    validator: (value) => {
      return ['', 'success', 'warning', 'danger', 'info', 'primary'].includes(value)
    },
  },
  text: {
    type: String,
    default: '',
  },
})

const statusMap = {
  pending: { type: 'info', text: '等待中' },
  running: { type: 'warning', text: '运行中' },
  completed: { type: 'success', text: '已完成' },
  failed: { type: 'danger', text: '失败' },
  cancelled: { type: 'info', text: '已取消' },
}

const statusConfig = computed(() => statusMap[props.status] || { type: 'info', text: props.status })
const typeClass = computed(() => props.type || statusConfig.value.type)
const text = computed(() => props.text || statusConfig.value.text)

const sizeMap = {
  small: { padding: '3px 8px', fontSize: '11px', dotSize: '5px', gap: '5px' },
  default: { padding: '5px 10px', fontSize: '12px', dotSize: '6px', gap: '6px' },
  large: { padding: '6px 12px', fontSize: '13px', dotSize: '7px', gap: '7px' },
}

const tagStyle = computed(() => ({
  padding: `${sizeMap[props.size]?.padding || sizeMap.default.padding}`,
  fontSize: sizeMap[props.size]?.fontSize || sizeMap.default.fontSize,
  gap: sizeMap[props.size]?.gap || sizeMap.default.gap,
}))
</script>

<style scoped>
@import '@/styles/variables.css';

.status-tag {
  display: inline-flex;
  align-items: center;
  border-radius: var(--radius-full);
  font-weight: var(--font-medium);
  letter-spacing: var(--tracking-tight);
  transition: var(--transition-base);
  border: 1px solid transparent;
  white-space: nowrap;
}

/* =============================================
   Light Effect - 低饱和度背景 + 深色文字
   更精致的色彩方案
   ============================================= */

/* Success - 祖母绿系 */
.status-tag--success {
  background-color: var(--success-light);
  color: var(--success-dark);
  border-color: var(--success-light);
}

.status-tag--success .status-dot {
  background-color: var(--success-base);
  box-shadow: 0 0 0 2px var(--success-light);
}

/* Warning - 琥珀色系 */
.status-tag--warning {
  background-color: var(--warning-light);
  color: var(--warning-dark);
  border-color: var(--warning-light);
}

.status-tag--warning .status-dot {
  background-color: var(--warning-base);
  box-shadow: 0 0 0 2px var(--warning-light);
}

/* Danger - 玫瑰红系 */
.status-tag--danger {
  background-color: var(--danger-light);
  color: var(--danger-dark);
  border-color: var(--danger-light);
}

.status-tag--danger .status-dot {
  background-color: var(--danger-base);
  box-shadow: 0 0 0 2px var(--danger-light);
}

/* Info - 中性灰色系 */
.status-tag--info {
  background-color: var(--gray-100);
  color: var(--gray-600);
  border-color: var(--gray-100);
}

.status-tag--info .status-dot {
  background-color: var(--gray-500);
  box-shadow: 0 0 0 2px var(--gray-100);
}

/* Primary - 蓝色系 */
.status-tag--primary {
  background-color: var(--info-light);
  color: var(--info-dark);
  border-color: var(--info-light);
}

.status-tag--primary .status-dot {
  background-color: var(--info-base);
  box-shadow: 0 0 0 2px var(--info-light);
}

/* =============================================
   Plain Effect - 透明背景 + 边框
   ============================================= */

.status-tag--success[effect="plain"] {
  background-color: transparent;
  color: var(--success-base);
  border-color: var(--success-base);
}

.status-tag--success[effect="plain"] .status-dot {
  background-color: var(--success-base);
}

.status-tag--warning[effect="plain"] {
  background-color: transparent;
  color: var(--warning-base);
  border-color: var(--warning-base);
}

.status-tag--warning[effect="plain"] .status-dot {
  background-color: var(--warning-base);
}

.status-tag--danger[effect="plain"] {
  background-color: transparent;
  color: var(--danger-base);
  border-color: var(--danger-base);
}

.status-tag--danger[effect="plain"] .status-dot {
  background-color: var(--danger-base);
}

.status-tag--info[effect="plain"] {
  background-color: transparent;
  color: var(--gray-500);
  border-color: var(--gray-500);
}

.status-tag--info[effect="plain"] .status-dot {
  background-color: var(--gray-500);
}

/* =============================================
   状态圆点
   ============================================= */

.status-dot {
  display: inline-block;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.status-tag--small .status-dot {
  width: 5px;
  height: 5px;
}

.status-tag--default .status-dot,
.status-tag:not(.status-tag--small):not(.status-tag--large) .status-dot {
  width: 6px;
  height: 6px;
}

.status-tag--large .status-dot {
  width: 7px;
  height: 7px;
}

/* =============================================
   运行中状态的脉动动画
   ============================================= */

.status-tag--pulse .status-dot {
  animation: pulse 2s var(--ease-in-out) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(0.92);
  }
}

/* =============================================
   Hover Effect - 微妙的悬浮反馈
   ============================================= */

.status-tag:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
}

/* =============================================
   Active/Pressed Effect
   ============================================= */

.status-tag:active {
  transform: translateY(0);
  transition: none;
}

/* =============================================
   Size Modifiers
   ============================================= */

.status-tag--small {
  padding: 3px 8px !important;
  font-size: 11px !important;
}

.status-tag--large {
  padding: 6px 12px !important;
  font-size: 13px !important;
}
</style>
