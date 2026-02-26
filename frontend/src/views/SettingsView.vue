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

const excludedCompanies = ref('')
const excludedKeywords = ref('')
const defaultLocation = ref('')
const defaultRemote = ref(false)
const isSaving = ref(false)

onMounted(async () => {
  await settingsStore.fetchSettings()

  if (settingsStore.settings) {
    excludedCompanies.value = settingsStore.settings.excluded_companies?.join(', ') || ''
    excludedKeywords.value = settingsStore.settings.excluded_keywords?.join(', ') || ''
    defaultLocation.value = settingsStore.settings.default_location || ''
    defaultRemote.value = settingsStore.settings.default_remote || false
  }
})

async function saveSettings() {
  isSaving.value = true

  try {
    const settings = {
      excluded_companies: excludedCompanies.value
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      excluded_keywords: excludedKeywords.value
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      default_location: defaultLocation.value || null,
      default_remote: defaultRemote.value,
    }

    await settingsStore.updateSettings(settings)
    uiStore.showSuccess('Settings saved')

    jobsStore.fetchJobs(true)

    if (settings.default_location || settings.default_remote) {
      jobsStore.setFilters({
        location: settings.default_location || '',
        isRemote: settings.default_remote ? true : null,
      })
    }
  } catch {
    uiStore.showError('Failed to save settings')
  } finally {
    isSaving.value = false
  }
}

async function clearSettings() {
  try {
    await settingsStore.updateSettings({
      excluded_companies: [],
      excluded_keywords: [],
      default_location: null,
      default_remote: false,
    })
    excludedCompanies.value = ''
    excludedKeywords.value = ''
    defaultLocation.value = ''
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
        <!-- Default Filters -->
        <section class="settings-section">
          <h2 class="section-title">Default Filters</h2>
          <p class="section-description">
            Applied automatically when opening the dashboard.
          </p>

          <div class="form-group">
            <label class="form-label">Default Location</label>
            <input
              v-model="defaultLocation"
              type="text"
              class="input"
              placeholder="e.g., San Francisco, CA"
            />
          </div>

          <div class="form-group">
            <label class="form-checkbox">
              <input v-model="defaultRemote" type="checkbox" />
              <span class="checkbox-box"></span>
              <span class="checkbox-label">Show only remote jobs by default</span>
            </label>
          </div>
        </section>

        <!-- Exclusions -->
        <section class="settings-section">
          <h2 class="section-title">Exclusions</h2>
          <p class="section-description">
            Hide jobs from specific companies or containing certain title keywords.
            Separate multiple values with commas.
          </p>

          <div class="form-group">
            <label class="form-label">Excluded Companies</label>
            <input
              v-model="excludedCompanies"
              type="text"
              class="input"
              placeholder="e.g., Acme Corp, Initech"
            />
          </div>

          <div class="form-group">
            <label class="form-label">Excluded Keywords</label>
            <input
              v-model="excludedKeywords"
              type="text"
              class="input"
              placeholder="e.g., senior, manager, director"
            />
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
