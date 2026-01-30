<script setup lang="ts">
/**
 * EmptyState - Display when no content is available
 */
interface Props {
  icon?: string
  title: string
  description?: string
}

withDefaults(defineProps<Props>(), {
  icon: '📭',
  description: ''
})
</script>

<template>
  <div class="empty-state">
    <div class="empty-state-icon">{{ icon }}</div>
    <h3 class="empty-state-title">{{ title }}</h3>
    <p v-if="description" class="empty-state-description">{{ description }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty-state {
  text-align: center;
  padding: var(--space-8) var(--space-4);
}

.empty-state-icon {
  font-size: 48px;
  margin-bottom: var(--space-4);
  opacity: 0.7;
}

.empty-state-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.empty-state-description {
  font-size: var(--text-base);
  color: var(--text-secondary);
  max-width: 400px;
  margin: 0 auto;
}
</style>
