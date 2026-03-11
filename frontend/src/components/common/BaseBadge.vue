<script setup lang="ts">
/**
 * BaseBadge - Reusable badge component
 */
interface Props {
  variant?: 'default' | 'new' | 'stale' | 'remote' | 'source' | 'favorite'
}

withDefaults(defineProps<Props>(), {
  variant: 'default'
})
</script>

<template>
  <span class="badge" :class="`badge-${variant}`">
    <slot />
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  font-weight: 500;
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.badge-new {
  background: rgba(34, 197, 94, 0.15);
  color: var(--status-new);
}

.badge-stale {
  background: rgba(234, 179, 8, 0.15);
  color: var(--status-stale);
}

.badge-remote {
  background: rgba(59, 130, 246, 0.15);
  color: var(--status-remote);
}

.badge-source {
  background: rgba(139, 92, 246, 0.15);
  color: var(--accent-secondary);
}

.badge-favorite {
  background: rgba(245, 158, 11, 0.15);
  color: var(--status-favorite);
}
</style>
