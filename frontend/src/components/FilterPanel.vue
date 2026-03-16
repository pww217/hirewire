<script setup lang="ts">
/**
 * FilterPanel - Job filter controls (all client-side)
 */
import { ref } from 'vue'
import type { FilterState } from '@/stores/jobs'

interface Props {
  modelValue: FilterState
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [filters: FilterState]
  clear: []
}>()

const locationInput = ref('')
const titleInput = ref('')
const descriptionInput = ref('')
const excludedInput = ref('')

function updateFilter<K extends keyof FilterState>(key: K, value: FilterState[K]) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function toggleRemote(value: boolean | null) {
  updateFilter('isRemote', value)
}

// ── Location chip helpers ──────────────────────────────────────────────────

function addLocation() {
  const val = locationInput.value.trim()
  if (!val) return
  updateFilter('locations', addChips(val, props.modelValue.locations))
  locationInput.value = ''
}

function removeLocation(loc: string) {
  updateFilter('locations', props.modelValue.locations.filter(l => l !== loc))
}

function onLocationKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addLocation()
  } else if (e.key === 'Backspace' && !locationInput.value && props.modelValue.locations.length) {
    updateFilter('locations', props.modelValue.locations.slice(0, -1))
  }
}

// ── Keyword chip helpers ───────────────────────────────────────────────────

function addChips(input: string, current: string[]): string[] {
  const parts = input.split(',').map(s => s.trim()).filter(Boolean)
  const result = [...current]
  for (const p of parts) {
    if (!result.includes(p)) result.push(p)
  }
  return result
}

function addTitleKeyword() {
  const val = titleInput.value.trim()
  if (!val) return
  updateFilter('titleKeywords', addChips(val, props.modelValue.titleKeywords))
  titleInput.value = ''
}

function addDescriptionKeyword() {
  const val = descriptionInput.value.trim()
  if (!val) return
  updateFilter('descriptionKeywords', addChips(val, props.modelValue.descriptionKeywords))
  descriptionInput.value = ''
}

function addExcludedKeyword() {
  const val = excludedInput.value.trim()
  if (!val) return
  updateFilter('excludedKeywords', addChips(val, props.modelValue.excludedKeywords))
  excludedInput.value = ''
}

function removeTitleKeyword(kw: string) {
  updateFilter('titleKeywords', props.modelValue.titleKeywords.filter(k => k !== kw))
}

function removeDescriptionKeyword(kw: string) {
  updateFilter('descriptionKeywords', props.modelValue.descriptionKeywords.filter(k => k !== kw))
}

function removeExcluded(kw: string) {
  updateFilter('excludedKeywords', props.modelValue.excludedKeywords.filter(k => k !== kw))
}

function onTitleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addTitleKeyword()
  } else if (e.key === 'Backspace' && !titleInput.value && props.modelValue.titleKeywords.length) {
    updateFilter('titleKeywords', props.modelValue.titleKeywords.slice(0, -1))
  }
}

function onDescriptionKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addDescriptionKeyword()
  } else if (e.key === 'Backspace' && !descriptionInput.value && props.modelValue.descriptionKeywords.length) {
    updateFilter('descriptionKeywords', props.modelValue.descriptionKeywords.slice(0, -1))
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
  locationInput.value = ''
  titleInput.value = ''
  descriptionInput.value = ''
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
            modelValue.locations.length ||
            modelValue.jobType ||
            modelValue.postedAfter ||
            modelValue.titleKeywords.length ||
            modelValue.descriptionKeywords.length ||
            modelValue.excludedKeywords.length ||
            modelValue.minGlassdoorRating !== null"
        class="btn btn-ghost btn-sm"
        @click="handleClear"
      >
        Clear all
      </button>
    </div>

    <!-- Location -->
    <div class="filter-group">
      <label class="filter-label">Location</label>
      <div class="chip-input" @click="($refs.locationInputEl as HTMLInputElement)?.focus()">
        <span v-for="loc in modelValue.locations" :key="loc" class="chip chip-location">
          {{ loc }}
          <button type="button" class="chip-remove" @click.stop="removeLocation(loc)">✕</button>
        </span>
        <input
          ref="locationInputEl"
          v-model="locationInput"
          class="chip-text-input"
          type="text"
          placeholder="e.g. Austin, Dallas"
          @keydown="onLocationKeydown"
          @blur="addLocation"
        />
      </div>
      <p class="filter-hint">OR match — show jobs in any of these locations</p>
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

    <!-- Title Keywords -->
    <div class="filter-group">
      <label class="filter-label">
        Title Keywords
        <span class="label-hint">title only</span>
      </label>
      <div class="chip-input" @click="($refs.titleInputEl as HTMLInputElement)?.focus()">
        <span v-for="kw in modelValue.titleKeywords" :key="kw" class="chip chip-include">
          {{ kw }}
          <button type="button" class="chip-remove" @click.stop="removeTitleKeyword(kw)">✕</button>
        </span>
        <input
          ref="titleInputEl"
          v-model="titleInput"
          class="chip-text-input"
          type="text"
          placeholder="e.g. engineer, analyst"
          @keydown="onTitleKeydown"
          @blur="addTitleKeyword"
        />
      </div>
      <p class="filter-hint">OR match — show jobs whose title contains any keyword</p>
    </div>

    <!-- Description Keywords -->
    <div class="filter-group">
      <label class="filter-label">
        Description Keywords
        <span class="label-hint">description only</span>
      </label>
      <div class="chip-input" @click="($refs.descriptionInputEl as HTMLInputElement)?.focus()">
        <span v-for="kw in modelValue.descriptionKeywords" :key="kw" class="chip chip-include">
          {{ kw }}
          <button type="button" class="chip-remove" @click.stop="removeDescriptionKeyword(kw)">✕</button>
        </span>
        <input
          ref="descriptionInputEl"
          v-model="descriptionInput"
          class="chip-text-input"
          type="text"
          placeholder="e.g. Python, SQL"
          @keydown="onDescriptionKeydown"
          @blur="addDescriptionKeyword"
        />
      </div>
      <p class="filter-hint">OR match — show jobs whose description mentions any keyword</p>
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

    <!-- Glassdoor Rating -->
    <div class="filter-group">
      <label class="filter-label">
        Min Glassdoor Rating
        <span class="label-hint">unrated jobs included</span>
      </label>
      <div class="star-filter">
        <button
          v-for="star in [1, 2, 3, 4]"
          :key="star"
          class="star-btn"
          :class="{ active: modelValue.minGlassdoorRating !== null && star <= modelValue.minGlassdoorRating }"
          :title="`${star}+ stars`"
          @click="updateFilter('minGlassdoorRating', modelValue.minGlassdoorRating === star ? null : star)"
        >
          ★
        </button>
        <span v-if="modelValue.minGlassdoorRating" class="star-label">
          {{ modelValue.minGlassdoorRating }}+ stars
        </span>
        <button
          v-if="modelValue.minGlassdoorRating"
          class="star-clear"
          @click="updateFilter('minGlassdoorRating', null)"
        >
          ✕
        </button>
      </div>
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

.chip-location {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
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

/* Star rating filter */
.star-filter {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.star-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: var(--border-color);
  padding: 0 2px;
  line-height: 1;
  transition: color var(--transition-fast), transform var(--transition-fast);
}

.star-btn:hover,
.star-btn.active {
  color: #d4900a;
}

.star-btn:hover {
  transform: scale(1.15);
}

.star-label {
  font-size: var(--text-xs);
  color: #d4900a;
  font-weight: 500;
  margin-left: var(--space-1);
}

.star-clear {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: var(--text-xs);
  padding: 0 var(--space-1);
  line-height: 1;
}

.star-clear:hover {
  color: var(--text-primary);
}
</style>
