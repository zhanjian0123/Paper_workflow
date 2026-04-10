<template>
  <div class="loading-spinner-container" :style="{ width: containerSize, height: containerSize }">
    <div class="loading-spinner" :style="{ width: size, height: size }">
      <svg viewBox="0 0 50 50" class="spinner-svg">
        <defs>
          <linearGradient id="spinner-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="var(--brand-primary)" />
            <stop offset="100%" stop-color="var(--info-solid)" />
          </linearGradient>
        </defs>
        <circle
          class="spinner-track"
          cx="25"
          cy="25"
          r="20"
          fill="none"
          :stroke-width="strokeWidth"
        />
        <circle
          class="spinner-path"
          cx="25"
          cy="25"
          r="20"
          fill="none"
          :stroke-width="strokeWidth"
          stroke="url(#spinner-gradient)"
        />
      </svg>
    </div>
    <div v-if="$slots.default" class="loading-text">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: {
    type: String,
    default: '40px',
    validator: (value) => {
      return /^[0-9]+(px|%|em|rem)?$/.test(value) || value === 'auto'
    },
  },
  strokeWidth: {
    type: Number,
    default: 4,
    validator: (value) => {
      return value >= 1 && value <= 20
    },
  },
  containerSize: {
    type: String,
    default: '60px',
    validator: (value) => {
      return /^[0-9]+(px|%|em|rem)?$/.test(value) || value === 'auto'
    },
  },
})
</script>

<style scoped>
@import '@/styles/variables.css';

.loading-spinner-container {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
}

.loading-spinner {
  position: relative;
  animation: spin 1.2s var(--ease-linear) infinite;
}

.spinner-svg {
  width: 100%;
  height: 100%;
}

.spinner-track {
  stroke: var(--gray-200);
  stroke-linecap: round;
}

.spinner-path {
  stroke-linecap: round;
  stroke-dasharray: 1, 150;
  stroke-dashoffset: 0;
  animation: dash 1.5s var(--ease-in-out) infinite;
}

.loading-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
  animation: pulse 1.5s var(--ease-in-out) infinite;
}

@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}

@keyframes dash {
  0% {
    stroke-dasharray: 1, 150;
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -35;
  }
  100% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -124;
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
