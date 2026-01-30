<script setup lang="ts">
/**
 * SortControls - Sorting options for job list
 */
import type { SortBy, SortOrder } from '@/stores/jobs'

interface Props {
  sortBy: SortBy
  sortOrder: SortOrder
}

defineProps<Props>()

const emit = defineEmits<{
  change: [sortBy: SortBy, sortOrder: SortOrder]
}>()

const sortOptions: { value: SortBy; label: string }[] = [
  { value: 'date_posted', label: 'Date Posted' },
  { value: 'company', label: 'Company' },
  { value: 'title', label: 'Title' },
]

function handleSortByChange(e: Event) {
  const value = (e.target as HTMLSelectElement).value as SortBy
  emit('change', value, 'desc')
}

function toggleOrder(currentOrder: SortOrder) {
  emit('change', 'date_posted', currentOrder === 'desc' ? 'asc' : 'desc')
}
</script>

<template>
  <div class="sort-controls">
    <label class="sort-label">Sort by:</label>
    <select 
      class="sort-select"
      :value="sortBy"
      @change="handleSortByChange"
    >
      <option 
        v-for="opt in sortOptions" 
        :key="opt.value" 
        :value="opt.value"
      >
        {{ opt.label }}
      </option>
    </select>
    <button 
      class="sort-order-btn"
      :title="sortOrder === 'desc' ? 'Newest first' : 'Oldest first'"
      @click="toggleOrder(sortOrder)"
    >
      {{ sortOrder === 'desc' ? '↓' : '↑' }}
    </button>
  </div>
</template>

<style scoped>
.sort-controls {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.sort-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.sort-select {
  padding: var(--space-1) var(--space-2);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-family: inherit;
  font-size: var(--text-sm);
  cursor: pointer;
}

.sort-select:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.sort-order-btn {
  padding: var(--space-1) var(--space-2);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--text-base);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.sort-order-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
</style>
