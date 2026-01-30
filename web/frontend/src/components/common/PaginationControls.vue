<script setup lang="ts">
/**
 * PaginationControls - Page navigation component
 */
import { computed } from 'vue'

interface Props {
  page: number
  totalPages: number
  maxVisible?: number
}

const props = withDefaults(defineProps<Props>(), {
  maxVisible: 5
})

const emit = defineEmits<{
  change: [page: number]
}>()

const visiblePages = computed(() => {
  const pages: (number | string)[] = []
  const total = props.totalPages
  const current = props.page
  const maxVisible = props.maxVisible
  
  if (total <= maxVisible) {
    // Show all pages
    for (let i = 1; i <= total; i++) {
      pages.push(i)
    }
  } else {
    // Always show first page
    pages.push(1)
    
    // Calculate start and end of visible range
    let start = Math.max(2, current - Math.floor(maxVisible / 2))
    let end = Math.min(total - 1, start + maxVisible - 3)
    
    // Adjust start if end is too close to total
    start = Math.max(2, end - maxVisible + 3)
    
    // Add ellipsis after first page if needed
    if (start > 2) {
      pages.push('...')
    }
    
    // Add middle pages
    for (let i = start; i <= end; i++) {
      pages.push(i)
    }
    
    // Add ellipsis before last page if needed
    if (end < total - 1) {
      pages.push('...')
    }
    
    // Always show last page
    pages.push(total)
  }
  
  return pages
})

function goToPage(page: number | string) {
  if (typeof page === 'number' && page !== props.page) {
    emit('change', page)
  }
}

function prevPage() {
  if (props.page > 1) {
    emit('change', props.page - 1)
  }
}

function nextPage() {
  if (props.page < props.totalPages) {
    emit('change', props.page + 1)
  }
}
</script>

<template>
  <div class="pagination">
    <button 
      class="pagination-btn"
      :disabled="page <= 1"
      @click="prevPage"
    >
      ← Prev
    </button>
    
    <div class="pagination-pages">
      <button
        v-for="(p, idx) in visiblePages"
        :key="idx"
        class="pagination-page"
        :class="{ active: p === page, ellipsis: p === '...' }"
        :disabled="p === '...'"
        @click="goToPage(p)"
      >
        {{ p }}
      </button>
    </div>
    
    <button 
      class="pagination-btn"
      :disabled="page >= totalPages"
      @click="nextPage"
    >
      Next →
    </button>
  </div>
</template>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding-top: var(--space-4);
}

.pagination-btn {
  padding: var(--space-2) var(--space-3);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.pagination-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--border-focus);
}

.pagination-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pagination-pages {
  display: flex;
  gap: var(--space-1);
}

.pagination-page {
  min-width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.pagination-page:hover:not(:disabled):not(.active) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.pagination-page.active {
  background: var(--accent-primary);
  color: white;
}

.pagination-page.ellipsis {
  cursor: default;
  color: var(--text-muted);
}
</style>
