<template>
  <el-card class="stat-card-custom" :style="cardStyle">
    <div class="stat-card-content">
      <div class="stat-card-icon" :style="{ backgroundColor: iconBg }">
        <el-icon :size="24" :color="iconColor">
          <component :is="icon" />
        </el-icon>
      </div>
      <div class="stat-card-info">
        <div class="stat-card-title">{{ title }}</div>
        <div class="stat-card-value">
          <el-statistic :value="value" :suffix="suffix" />
        </div>
        <div v-if="subtext" class="stat-card-subtext">{{ subtext }}</div>
      </div>
    </div>
    <div v-if="trend !== undefined && trend !== null" class="stat-card-trend" :class="trend > 0 ? 'trend-up' : 'trend-down'">
      <el-icon class="trend-icon"><Top v-if="trend > 0" /><Bottom v-else /></el-icon>
      <span class="trend-value">{{ Math.abs(trend) }}%</span>
    </div>
  </el-card>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  value: {
    type: Number,
    required: true,
    validator: (value) => {
      return typeof value === 'number' && value >= 0
    },
  },
  suffix: {
    type: String,
    default: '',
  },
  subtext: {
    type: String,
    default: '',
  },
  icon: {
    type: String,
    default: 'DataLine',
  },
  iconColor: {
    type: String,
    default: '#2563eb',
    validator: (value) => {
      return /^#[0-9A-Fa-f]{6}$/.test(value) || value.startsWith('rgb') || value.startsWith('hsl')
    },
  },
  iconBg: {
    type: String,
    default: '#eff6ff',
    validator: (value) => {
      return /^#[0-9A-Fa-f]{6}$/.test(value) || value.startsWith('rgb') || value.startsWith('hsl')
    },
  },
  trend: {
    type: Number,
    default: 0,
    validator: (value) => {
      return value >= -100 && value <= 100
    },
  },
  cardStyle: {
    type: Object,
    default: () => ({}),
  },
})
</script>

<style scoped>
@import '@/styles/variables.css';

.stat-card-custom {
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-card);
  transition: var(--transition-base);
  overflow: hidden;
  position: relative;
  background: var(--bg-primary);
}

.stat-card-custom::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--brand-primary) 0%, var(--info-solid) 100%);
  opacity: 0;
  transition: var(--transition-base);
}

.stat-card-custom:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-card-hover);
  border-color: transparent;
}

.stat-card-custom:hover::before {
  opacity: 1;
}

.stat-card-content {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.stat-card-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: var(--transition-spring);
}

.stat-card-custom:hover .stat-card-icon {
  transform: scale(1.08) rotate(3deg);
}

.stat-card-info {
  flex: 1;
  min-width: 0;
}

.stat-card-title {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
  margin-bottom: var(--space-2);
  letter-spacing: var(--tracking-tight);
}

.stat-card-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1;
  letter-spacing: var(--tracking-tight);
}

.stat-card-value :deep(.el-statistic__content) {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  letter-spacing: var(--tracking-tight);
}

.stat-card-value :deep(.el-statistic__title) {
  display: none;
}

.stat-card-subtext {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}

.stat-card-trend {
  position: absolute;
  top: var(--space-4);
  right: var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  padding: 3px 8px;
  border-radius: var(--radius-full);
  transition: var(--transition-base);
}

.stat-card-trend.trend-up {
  color: var(--success-dark);
  background-color: var(--success-light);
}

.stat-card-trend.trend-down {
  color: var(--danger-dark);
  background-color: var(--danger-light);
}

.trend-icon {
  font-size: 14px;
}

.trend-value {
  font-weight: var(--font-bold);
}
</style>
