<script setup lang="ts">
/**
 * FilterPanel - Job filter controls (all client-side)
 */
import { ref } from 'vue'
import type { FilterState } from '@/stores/jobs'
import BaseInput from '@/components/common/BaseInput.vue'

interface Props {
  modelValue: FilterState
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [filters: FilterState]
  clear: []
}>()

const includedInput = ref('')
const excludedInput = ref('')

function updateFilter<K extends keyof FilterState>(key: K, value: FilterState[K]) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function toggleRemote(value: boolean | null) {
  updateFilter('isRemote', value)
}

// ── Keyword chip helpers ───────────────────────────────────────────────────

function addIncludedKeyword() {
  const val = includedInput.value.trim()
  if (!val) return
  const parts = val.split(',').map(s => s.trim()).filter(Boolean)
  const current = [...props.modelValue.includedKeywords]
  for (const p of parts) {
    if (!current.includes(p)) current.push(p)
  }
  updateFilter('includedKeywords', current)
  includedInput.value = ''
}

function addExcludedKeyword() {
  const val = excludedInput.value.trim()
  if (!val) return
  const parts = val.split(',').map(s => s.trim()).filter(Boolean)
  const current = [...props.modelValue.excludedKeywords]
  for (const p of parts) {
    if (!current.includes(p)) current.push(p)
  }
  updateFilter('excludedKeywords', current)
  excludedInput.value = ''
}

function removeIncluded(kw: string) {
  updateFilter('includedKeywords', props.modelValue.includedKeywords.filter(k => k !== kw))
}

function removeExcluded(kw: string) {
  updateFilter('excludedKeywords', props.modelValue.excludedKeywords.filter(k => k !== kw))
}

function onIncludedKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addIncludedKeyword()
  } else if (e.key === 'Backspace' && !includedInput.value && props.modelValue.includedKeywords.length) {
    updateFilter('includedKeywords', props.modelValue.includedKeywords.slice(0, -1))
  }
}

function onExcludedKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addExcludedKeyword()
  } else if (e.key === 'Backspace' && !excludedInput.value && props.modelValue.excludedKeywords.length) {
    updateFilter('excludedKeywords', props.modelValue.excludedKeywords.slice(0, -1))
  }
}

function handleClear() {
  includedInput.value = ''
  excludedInput.value = ''
  emit('clear')
}
</script>

<template>
  <aside class="filter-panel">
    <div class="filter-panel-header">
      <h2 class="filter-panel-title">Filters</h2>
      <button
        v-if="modelValue.isRemote !== null ||
              modelValue.location ||
              modelValue.jobType ||
              modelValue.postedAfter ||
              modelValue.includedKeywords.length ||
              modelValue.excludedKeywords.length"
        class="btn btn-ghost btn-sm"
        @click="handleClear"
      >
        Clear all
      </button>
    </div>

    <!-- Location -->
    <div class="filter-group">
      <label class="filter-label">Location</label>
      <BaseInput
        :model-value="modelValue.location"
        placeholder="City, state, or country"
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
          Remote only
        </button>
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

    <!-- Included Keywords -->
    <div class="filter-group">
      <label class="filter-label">
        Include Keywords
        <span class="label-hint">title or description</span>
      </label>
      <div class="chip-input" @click="($refs.includedInputEl as HTMLInputElement)?.focus()">
        <span v-for="kw in modelValue.includedKeywords" :key="kw" class="chip chip-include">
          {{ kw }}
          <button type="button" class="chip-remove" @click.stop="removeIncluded(kw)">✕</button>
        </span>
        <input
          ref="includedInputEl"
          v-model="includedInput"
          class="chip-text-input"
          type="text"
          placeholder="e.g. engineer, analyst"
          @keydown="onIncludedKeydown"
          @blur="addIncludedKeyword"
        />
      </div>
      <p class="filter-hint">OR match — show jobs containing any keyword</p>
    </div>

    <!-- Excluded Keywords -->
    <div class="filter-group">
      <label class="filter-label">
        Exclude Keywords
        <span class="label-hint">title only</span>
      </label>
      <div class="chip-input" @click="($refs.excludedInputEl as HTMLInputElement)?.focus()">
        <span v-for="kw in modelValue.excludedKeywords" :key="kw" class="chip chip-exclude">
          {{ kw }}
          <button type="button" class="chip-remove" @click.stop="removeExcluded(kw)">✕</button>
        </span>
        <input
          ref="excludedInputEl"
          v-model="excludedInput"
          class="chip-text-input"
          type="text"
          placeholder="e.g. intern, director"
          @keydown="onExcludedKeydown"
          @blur="addExcludedKeyword"
        />
      </div>
      <p class="filter-hint">Hide jobs whose titles contain any keyword</p>
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
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.label-hint {
  font-size: var(--text-xs);
  font-weight: 400;
  color: var(--text-muted);
}

.filter-hint {
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
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

/* Chip input */
.chip-input {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  padding: var(--space-2);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  min-height: 38px;
  cursor: text;
  transition: border-color var(--transition-fast);
}

.chip-input:focus-within {
  border-color: var(--accent-primary);
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px 2px 10px;
  border-radius: 12px;
  font-size: var(--text-xs);
  font-weight: 500;
  white-space: nowrap;
}

.chip-include {
  background: rgba(59, 130, 246, 0.15);
  color: var(--accent-primary);
}

.chip-exclude {
  background: rgba(239, 68, 68, 0.12);
  color: #e05252;
}

.chip-remove {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  padding: 0;
  font-size: 10px;
  opacity: 0.7;
  line-height: 1;
  display: flex;
  align-items: center;
}

.chip-remove:hover {
  opacity: 1;
}

.chip-text-input {
  flex: 1;
  min-width: 100px;
  background: none;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: var(--text-sm);
  padding: 2px 4px;
}

.chip-text-input::placeholder {
  color: var(--text-muted);
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
