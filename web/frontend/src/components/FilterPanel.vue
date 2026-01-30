<script setup lang="ts">
/**
 * FilterPanel - Job filter controls
 */
import { computed } from 'vue'
import type { FilterState } from '@/stores/jobs'
import type { CompanySize } from '@/types/api'
import BaseInput from '@/components/common/BaseInput.vue'
import FilterCheckbox from './FilterCheckbox.vue'

const COMPANY_SIZES: CompanySize[] = ['1-10', '11-50', '51-200', '201-500', '501-1000', '1000+']

interface Props {
  modelValue: FilterState
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [filters: FilterState]
  clear: []
}>()

// Handlers
function updateFilter<K extends keyof FilterState>(key: K, value: FilterState[K]) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function toggleCompanySize(size: CompanySize) {
  const current = props.modelValue.companySizes
  const updated = current.includes(size)
    ? current.filter(s => s !== size)
    : [...current, size]
  updateFilter('companySizes', updated as CompanySize[])
}

function toggleRemote(value: boolean | null) {
  updateFilter('isRemote', value)
}

function handleClear() {
  emit('clear')
}

const activeFilterCount = computed(() => {
  let count = 0
  if (props.modelValue.location) count++
  if (props.modelValue.isRemote !== null) count++
  if (props.modelValue.companySizes.length > 0) count++
  if (props.modelValue.jobType) count++
  if (props.modelValue.postedAfter) count++
  return count
})
</script>

<template>
  <aside class="filter-panel">
    <div class="filter-panel-header">
      <h2 class="filter-panel-title">Filters</h2>
      <button 
        v-if="activeFilterCount > 0"
        class="btn btn-ghost btn-sm"
        @click="handleClear"
      >
        Clear ({{ activeFilterCount }})
      </button>
    </div>
    
    <!-- Location -->
    <div class="filter-group">
      <label class="filter-label">Location</label>
      <BaseInput
        :model-value="modelValue.location"
        placeholder="City, State, or Country"
        @update:model-value="updateFilter('location', $event)"
      />
    </div>
    
    <!-- Remote -->
    <div class="filter-group">
      <label class="filter-label">Work Type</label>
      <div class="filter-options">
        <button 
          class="filter-option-btn"
          :class="{ active: modelValue.isRemote === true }"
          @click="toggleRemote(modelValue.isRemote === true ? null : true)"
        >
          Remote
        </button>
        <button 
          class="filter-option-btn"
          :class="{ active: modelValue.isRemote === false }"
          @click="toggleRemote(modelValue.isRemote === false ? null : false)"
        >
          On-site
        </button>
      </div>
    </div>
    
    <!-- Company Size -->
    <div class="filter-group">
      <label class="filter-label">Company Size</label>
      <div class="filter-checkboxes">
        <FilterCheckbox
          v-for="size in COMPANY_SIZES"
          :key="size"
          :checked="modelValue.companySizes.includes(size)"
          :label="size + ' employees'"
          @change="toggleCompanySize(size)"
        />
      </div>
    </div>
    
    <!-- Posted Date -->
    <div class="filter-group">
      <label class="filter-label">Posted</label>
      <select 
        class="input"
        :value="modelValue.postedAfter || ''"
        @change="updateFilter('postedAfter', ($event.target as HTMLSelectElement).value || null)"
      >
        <option value="">Any time</option>
        <option value="today">Today</option>
        <option value="week">Past week</option>
        <option value="month">Past month</option>
      </select>
    </div>
  </aside>
</template>

<style scoped>
.filter-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
}

.filter-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-color);
}

.filter-panel-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.btn-sm {
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
}

.filter-group {
  margin-bottom: var(--space-4);
}

.filter-group:last-child {
  margin-bottom: 0;
}

.filter-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.filter-options {
  display: flex;
  gap: var(--space-2);
}

.filter-option-btn {
  flex: 1;
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

.filter-option-btn:hover {
  border-color: var(--border-focus);
  color: var(--text-primary);
}

.filter-option-btn.active {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: white;
}

.filter-checkboxes {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-family: inherit;
  font-size: var(--text-sm);
  cursor: pointer;
}

.input:focus {
  outline: none;
  border-color: var(--accent-primary);
}
</style>
