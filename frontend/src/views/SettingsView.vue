<script setup lang="ts">
/**
 * SettingsView - User preferences
 */
import { ref, onMounted } from 'vue'
import { useJobsStore } from '@/stores/jobs'
import { useUIStore } from '@/stores/ui'
import { useSettingsStore } from '@/stores/settings'

const jobsStore = useJobsStore()
const uiStore = useUIStore()
const settingsStore = useSettingsStore()

// Preferred locations (chips)
const preferredLocations = ref<string[]>([])
const locationInput = ref('')

// Other settings
const includedKeywords = ref('')
const excludedKeywords = ref('')
const defaultRemote = ref(false)
const isSaving = ref(false)

onMounted(async () => {
  await settingsStore.fetchSettings()
  if (settingsStore.settings) {
    preferredLocations.value = [...(settingsStore.settings.preferred_locations || [])]
    includedKeywords.value = settingsStore.settings.included_keywords?.join(', ') || ''
    excludedKeywords.value = settingsStore.settings.excluded_keywords?.join(', ') || ''
    defaultRemote.value = settingsStore.settings.default_remote || false
  }
})

function addLocation() {
  const val = locationInput.value.trim()
  if (!val) return
  // Support comma-separated bulk entry
  const parts = val.split(',').map((s) => s.trim()).filter(Boolean)
  for (const part of parts) {
    if (!preferredLocations.value.includes(part)) {
      preferredLocations.value.push(part)
    }
  }
  locationInput.value = ''
}

function removeLocation(idx: number) {
  preferredLocations.value.splice(idx, 1)
}

function onLocationKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addLocation()
  } else if (e.key === 'Backspace' && !locationInput.value && preferredLocations.value.length) {
    preferredLocations.value.pop()
  }
}

async function saveSettings() {
  isSaving.value = true
  try {
    const settings = {
      preferred_locations: preferredLocations.value,
      included_keywords: includedKeywords.value
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      excluded_keywords: excludedKeywords.value
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      default_remote: defaultRemote.value,
    }

    await settingsStore.updateSettings(settings)
    uiStore.showSuccess('Settings saved')
    // Apply remote default to active filters so the job list reflects it immediately
    if (settings.default_remote) {
      jobsStore.setFilters({ isRemote: true })
    } else if (jobsStore.filters.isRemote === true) {
      // Only clear if it was set by the setting (not an explicit user filter)
      jobsStore.setFilters({ isRemote: null })
    }
    jobsStore.fetchJobs(true)
  } catch {
    uiStore.showError('Failed to save settings')
  } finally {
    isSaving.value = false
  }
}

async function clearSettings() {
  try {
    await settingsStore.updateSettings({
      preferred_locations: [],
      included_keywords: [],
      excluded_keywords: [],
      default_remote: false,
    })
    preferredLocations.value = []
    includedKeywords.value = ''
    excludedKeywords.value = ''
    defaultRemote.value = false
    uiStore.showSuccess('Settings cleared')
    jobsStore.fetchJobs(true)
  } catch {
    uiStore.showError('Failed to clear settings')
  }
}
</script>

<template>
  <div class="settings-view">
    <header class="settings-header">
      <h1 class="settings-title">Settings</h1>
    </header>

    <main class="settings-content">
      <form class="settings-form" @submit.prevent="saveSettings">
        <!-- Job Filters -->
        <section class="settings-section">
          <h2 class="section-title">Job Filters</h2>
          <p class="section-description">
            Applied automatically to the job list. Leave locations empty to see all locations.
          </p>

          <!-- Preferred locations chip input -->
          <div class="form-group">
            <label class="form-label">Preferred Locations</label>
            <div class="chip-input" @click="($refs.locInput as HTMLInputElement)?.focus()">
              <span
                v-for="(loc, idx) in preferredLocations"
                :key="loc"
                class="chip"
              >
                {{ loc }}
                <button type="button" class="chip-remove" @click.stop="removeLocation(idx)">✕</button>
              </span>
              <input
                ref="locInput"
                v-model="locationInput"
                class="chip-text-input"
                type="text"
                placeholder="Add location…"
                @keydown="onLocationKeydown"
                @blur="addLocation"
              />
            </div>
            <p class="form-hint">Press Enter or comma to add. e.g. "New York", "San Francisco", "Remote"</p>
          </div>

          <div class="form-group">
            <label class="form-checkbox">
              <input v-model="defaultRemote" type="checkbox" />
              <span class="checkbox-box"></span>
              <span class="checkbox-label">Show only remote jobs by default</span>
            </label>
          </div>
        </section>

        <!-- Content Filters -->
        <section class="settings-section">
          <h2 class="section-title">Content Filters</h2>
          <p class="section-description">
            Narrow by title keywords. Separate multiple values with commas.
          </p>

          <div class="form-group">
            <label class="form-label">Included Keywords</label>
            <input
              v-model="includedKeywords"
              type="text"
              class="input"
              placeholder="e.g., engineer, analyst, designer"
            />
            <p class="form-hint">Only show jobs whose titles contain at least one of these.</p>
          </div>

          <div class="form-group">
            <label class="form-label">Excluded Keywords</label>
            <input
              v-model="excludedKeywords"
              type="text"
              class="input"
              placeholder="e.g., intern, director, staff"
            />
            <p class="form-hint">Hide jobs whose titles contain any of these.</p>
          </div>
        </section>

        <div class="settings-actions">
          <button type="submit" class="btn btn-primary" :disabled="isSaving">
            {{ isSaving ? 'Saving...' : 'Save Settings' }}
          </button>
          <button type="button" class="btn btn-secondary" @click="clearSettings">
            Clear All
          </button>
        </div>
      </form>

      <section class="settings-section about-section">
        <h2 class="section-title">About HireWire</h2>
        <p class="about-text">
          HireWire tracks job listings directly from company ATS boards (Greenhouse, Lever, Ashby).
        </p>
        <p class="about-version">v0.2.0</p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.settings-header {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-color);
}

.settings-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.settings-content {
  flex: 1;
  padding: var(--space-5);
  overflow-y: auto;
  max-width: 800px;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.settings-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
}

.section-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-2) 0;
}

.section-description {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-bottom: var(--space-4);
}

.form-group {
  margin-bottom: var(--space-4);
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.form-hint {
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

/* Chip input */
.chip-input {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-2);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  min-height: 40px;
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
  background: var(--bg-active);
  color: var(--accent-primary);
  border-radius: 12px;
  font-size: var(--text-xs);
  font-weight: 500;
  white-space: nowrap;
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
  min-width: 120px;
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

/* Checkbox */
.form-checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  cursor: pointer;
  user-select: none;
}

.form-checkbox input {
  display: none;
}

.form-checkbox .checkbox-box {
  width: 20px;
  height: 20px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  position: relative;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.form-checkbox input:checked + .checkbox-box {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
}

.form-checkbox input:checked + .checkbox-box::after {
  content: '✓';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: white;
  font-size: 12px;
  font-weight: 600;
}

.form-checkbox .checkbox-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--text-primary);
  transition: border-color var(--transition-fast);
  box-sizing: border-box;
}

.input:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.input::placeholder {
  color: var(--text-muted);
}

.settings-actions {
  display: flex;
  gap: var(--space-3);
}

.about-section {
  margin-top: var(--space-2);
}

.about-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}

.about-version {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  border: none;
}

.btn-primary {
  background: var(--accent-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-primary-hover, #2563eb);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background: var(--bg-hover);
}
</style>
