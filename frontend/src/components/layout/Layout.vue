<template>
  <div class="layout-container">
    <slot />
  </div>
</template>

<style scoped>
.layout-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at top, rgba(255, 255, 255, 0.9), transparent 42%),
    var(--bg-secondary);
  padding: var(--space-8) 0 var(--space-10);
}

@media (max-width: 768px) {
  .layout-container {
    padding: var(--space-5) 0 var(--space-8);
  }
}
</style>
