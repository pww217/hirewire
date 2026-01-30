<script setup lang="ts">
/**
 * SettingsView - User settings and search config management
 */
import { ref, onMounted, computed } from 'vue'
import { useJobsStore } from '@/stores/jobs'
import { useUIStore } from '@/stores/ui'
import { useSearchConfigsStore } from '@/stores/searchConfigs'
import { useSettingsStore } from '@/stores/settings'
import type { SearchConfig } from '@/types/api'
import type { SearchConfigCreate } from '@/stores/searchConfigs'

const jobsStore = useJobsStore()
const uiStore = useUIStore()
const searchConfigsStore = useSearchConfigsStore()
const settingsStore = useSettingsStore()

// User settings form state
const excludedCompanies = ref('')
const excludedKeywords = ref('')
const defaultLocation = ref('')
const defaultRemote = ref(false)
const isSaving = ref(false)

// Search config form state
const showConfigForm = ref(false)
const editingConfig = ref<SearchConfig | null>(null)
const configForm = ref<SearchConfigCreate>({
  name: '',
  search_term: '',
  location: '',
  distance: 50,
  is_remote: false,
  hours_old: 48,
  results_wanted: 100,
  country: 'USA',
  enabled: true,
})
const isSubmittingConfig = ref(false)

// Computed
const isEditMode = computed(() => editingConfig.value !== null)
const formTitle = computed(() => isEditMode.value ? 'Edit Search Config' : 'New Search Config')

onMounted(async () => {
  // Load user settings from API
  await settingsStore.fetchSettings()
  
  // Populate form with settings
  if (settingsStore.settings) {
    excludedCompanies.value = settingsStore.settings.excluded_companies?.join(', ') || ''
    excludedKeywords.value = settingsStore.settings.excluded_keywords?.join(', ') || ''
    defaultLocation.value = settingsStore.settings.default_location || ''
    defaultRemote.value = settingsStore.settings.default_remote || false
  }

  // Load search configs
  await searchConfigsStore.fetchConfigs()
})

async function saveSettings() {
  isSaving.value = true
  
  try {
    const settings = {
      excluded_companies: excludedCompanies.value
        .split(',')
        .map(s => s.trim())
        .filter(Boolean),
      excluded_keywords: excludedKeywords.value
        .split(',')
        .map(s => s.trim())
        .filter(Boolean),
      default_location: defaultLocation.value || null,
      default_remote: defaultRemote.value,
    }
    
    await settingsStore.updateSettings(settings)
    uiStore.showSuccess('Settings saved')
    
    // Refresh jobs with new exclusion filters
    jobsStore.fetchJobs(true)
    
    // Apply default filters if set
    if (settings.default_location || settings.default_remote) {
      jobsStore.setFilters({
        location: settings.default_location || '',
        isRemote: settings.default_remote ? true : null,
      })
    }
  } catch (e) {
    uiStore.showError('Failed to save settings')
  } finally {
    isSaving.value = false
  }
}

async function clearCache() {
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
    
    // Refresh jobs without exclusions
    jobsStore.fetchJobs(true)
  } catch (e) {
    uiStore.showError('Failed to clear settings')
  }
}

// Search config actions
function resetConfigForm() {
  configForm.value = {
    name: '',
    search_term: '',
    location: '',
    distance: 50,
    is_remote: false,
    hours_old: 48,
    results_wanted: 100,
    country: 'USA',
    enabled: true,
  }
  editingConfig.value = null
}

function openNewConfigForm() {
  resetConfigForm()
  showConfigForm.value = true
}

function openEditConfigForm(config: SearchConfig) {
  editingConfig.value = config
  configForm.value = {
    name: config.name,
    search_term: config.search_term,
    location: config.location || '',
    distance: config.distance || 50,
    is_remote: config.is_remote,
    hours_old: config.hours_old,
    results_wanted: config.results_wanted,
    country: config.country,
    enabled: config.enabled,
  }
  showConfigForm.value = true
}

function closeConfigForm() {
  showConfigForm.value = false
  resetConfigForm()
}

async function submitConfigForm() {
  if (!configForm.value.name || !configForm.value.search_term) {
    uiStore.showError('Name and search term are required')
    return
  }

  isSubmittingConfig.value = true

  try {
    const data = {
      ...configForm.value,
      location: configForm.value.location || null,
    }

    if (isEditMode.value && editingConfig.value) {
      await searchConfigsStore.updateConfig(editingConfig.value.id, data)
      uiStore.showSuccess('Search config updated')
    } else {
      await searchConfigsStore.createConfig(data)
      uiStore.showSuccess('Search config created')
    }
    closeConfigForm()
  } catch (e) {
    // Error already shown by API
  } finally {
    isSubmittingConfig.value = false
  }
}

async function deleteConfig(config: SearchConfig) {
  if (!confirm(`Delete "${config.name}"? This cannot be undone.`)) {
    return
  }

  try {
    await searchConfigsStore.deleteConfig(config.id)
    uiStore.showSuccess('Search config deleted')
  } catch (e) {
    // Error already shown by API
  }
}

async function toggleConfig(config: SearchConfig) {
  try {
    await searchConfigsStore.toggleConfig(config.id)
  } catch (e) {
    // Error already shown by API
  }
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString()
}

const hoursOptions = [
  { value: 24, label: 'Last 24 hours' },
  { value: 48, label: 'Last 48 hours' },
  { value: 72, label: 'Last 3 days' },
  { value: 168, label: 'Last week' },
]

const countryOptions = [
  { value: 'USA', label: 'United States' },
  { value: 'UK', label: 'United Kingdom' },
  { value: 'Canada', label: 'Canada' },
  { value: 'Germany', label: 'Germany' },
  { value: 'France', label: 'France' },
  { value: 'Australia', label: 'Australia' },
  { value: 'India', label: 'India' },
  { value: 'Netherlands', label: 'Netherlands' },
  { value: 'Singapore', label: 'Singapore' },
  { value: 'Ireland', label: 'Ireland' },
]
</script>

<template>
  <div class="settings-view">
    <header class="settings-header">
      <h1 class="settings-title">Settings</h1>
    </header>
    
    <main class="settings-content">
      <!-- Search Configs Section -->
      <section class="settings-section">
        <div class="section-header">
          <div>
            <h2 class="section-title">Search Configurations</h2>
            <p class="section-description">
              Define what jobs to search for. The scraper will run these searches periodically.
            </p>
          </div>
          <button class="btn btn-primary btn-sm" @click="openNewConfigForm">
            + Add Config
          </button>
        </div>

        <!-- Loading state -->
        <div v-if="searchConfigsStore.isLoading" class="loading-state">
          Loading search configs...
        </div>

        <!-- Empty state -->
        <div v-else-if="searchConfigsStore.configs.length === 0" class="empty-state">
          <p>No search configurations yet.</p>
          <p class="empty-hint">Add a search config to start finding jobs.</p>
        </div>

        <!-- Configs list -->
        <div v-else class="configs-list">
          <div 
            v-for="config in searchConfigsStore.configs" 
            :key="config.id"
            class="config-card"
            :class="{ 
              'config-disabled': !config.enabled,
              'config-editing': editingConfig?.id === config.id
            }"
          >
            <!-- Collapsed view -->
            <template v-if="editingConfig?.id !== config.id">
              <div class="config-header">
                <div class="config-title-row">
                  <h3 class="config-name">{{ config.name }}</h3>
                  <span 
                    class="config-badge"
                    :class="config.enabled ? 'badge-enabled' : 'badge-disabled'"
                  >
                    {{ config.enabled ? 'Active' : 'Paused' }}
                  </span>
                </div>
                <div class="config-actions">
                  <button 
                    class="btn-icon" 
                    :title="config.enabled ? 'Pause' : 'Enable'"
                    :aria-label="config.enabled ? 'Pause search' : 'Enable search'"
                    @click="toggleConfig(config)"
                  >
                    {{ config.enabled ? '⏸' : '▶' }}
                  </button>
                  <button 
                    class="btn-icon" 
                    title="Edit"
                    aria-label="Edit search config"
                    @click="openEditConfigForm(config)"
                  >
                    ✏️
                  </button>
                  <button 
                    class="btn-icon btn-danger" 
                    title="Delete"
                    aria-label="Delete search config"
                    @click="deleteConfig(config)"
                  >
                    🗑️
                  </button>
                </div>
              </div>
              <div class="config-details">
                <div class="config-field">
                  <span class="field-label">Search:</span>
                  <span class="field-value">{{ config.search_term }}</span>
                </div>
                <div class="config-meta">
                  <span v-if="config.location" class="meta-item">
                    📍 {{ config.location }}
                  </span>
                  <span v-if="config.is_remote" class="meta-item">
                    🏠 Remote
                  </span>
                  <span class="meta-item">
                    🌍 {{ config.country }}
                  </span>
                  <span class="meta-item">
                    ⏱️ {{ config.hours_old }}h
                  </span>
                  <span class="meta-item">
                    📊 {{ config.results_wanted }} max
                  </span>
                </div>
              </div>
            </template>
            
            <!-- Inline edit form -->
            <template v-else>
              <form class="config-inline-form" @submit.prevent="submitConfigForm">
                <div class="inline-form-header">
                  <h3 class="config-name">Edit: {{ config.name }}</h3>
                  <button 
                    type="button" 
                    class="btn-icon" 
                    title="Cancel"
                    @click="closeConfigForm"
                  >
                    ✕
                  </button>
                </div>
                
                <div class="inline-form-fields">
                  <div class="form-row">
                    <div class="form-group">
                      <label class="form-label">Name *</label>
                      <input 
                        v-model="configForm.name"
                        type="text"
                        class="input"
                        required
                      />
                    </div>
                    <div class="form-group">
                      <label class="form-label">Search Term *</label>
                      <input 
                        v-model="configForm.search_term"
                        type="text"
                        class="input"
                        required
                      />
                    </div>
                  </div>

                  <div class="form-row">
                    <div class="form-group">
                      <label class="form-label">Location</label>
                      <input 
                        v-model="configForm.location"
                        type="text"
                        class="input"
                        placeholder="e.g., San Francisco, CA"
                      />
                    </div>
                    <div class="form-group">
                      <label class="form-label">Country</label>
                      <select v-model="configForm.country" class="input">
                        <option v-for="opt in countryOptions" :key="opt.value" :value="opt.value">
                          {{ opt.label }}
                        </option>
                      </select>
                    </div>
                  </div>

                  <div class="form-row">
                    <div class="form-group">
                      <label class="form-label">Max Age</label>
                      <select v-model.number="configForm.hours_old" class="input">
                        <option v-for="opt in hoursOptions" :key="opt.value" :value="opt.value">
                          {{ opt.label }}
                        </option>
                      </select>
                    </div>
                    <div class="form-group">
                      <label class="form-label">Max Results</label>
                      <input 
                        v-model.number="configForm.results_wanted"
                        type="number"
                        class="input"
                        min="10"
                        max="500"
                      />
                    </div>
                  </div>

                  <div class="form-row">
                    <div class="form-group">
                      <label class="form-checkbox">
                        <input v-model="configForm.is_remote" type="checkbox" />
                        <span class="checkbox-box"></span>
                        <span class="checkbox-label">Remote only</span>
                      </label>
                    </div>
                    <div class="form-group">
                      <label class="form-checkbox">
                        <input v-model="configForm.enabled" type="checkbox" />
                        <span class="checkbox-box"></span>
                        <span class="checkbox-label">Enabled</span>
                      </label>
                    </div>
                  </div>
                </div>

                <div class="inline-form-actions">
                  <button type="button" class="btn btn-ghost" @click="closeConfigForm">
                    Cancel
                  </button>
                  <button 
                    type="submit" 
                    class="btn btn-primary"
                    :disabled="isSubmittingConfig"
                  >
                    {{ isSubmittingConfig ? 'Saving...' : 'Save Changes' }}
                  </button>
                </div>
              </form>
            </template>
          </div>
        </div>
      </section>

      <!-- Config Form Modal (for creating new configs only) -->
      <div v-if="showConfigForm && !isEditMode" class="modal-overlay" @click.self="closeConfigForm">
        <div class="modal-content">
          <div class="modal-header">
            <h2>{{ formTitle }}</h2>
            <button class="btn-close" @click="closeConfigForm">&times;</button>
          </div>
          <form class="config-form" @submit.prevent="submitConfigForm">
            <div class="form-group">
              <label class="form-label">Name *</label>
              <input 
                v-model="configForm.name"
                type="text"
                class="input"
                placeholder="e.g., SEO Remote Jobs"
                required
              />
            </div>

            <div class="form-group">
              <label class="form-label">Search Term *</label>
              <input 
                v-model="configForm.search_term"
                type="text"
                class="input"
                placeholder='e.g., "SEO" OR "search engine optimization"'
                required
              />
              <p class="form-hint">Supports OR operators for multiple keywords</p>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Location</label>
                <input 
                  v-model="configForm.location"
                  type="text"
                  class="input"
                  placeholder="e.g., San Francisco, CA"
                />
              </div>
              <div class="form-group">
                <label class="form-label">Distance (miles)</label>
                <input 
                  v-model.number="configForm.distance"
                  type="number"
                  class="input"
                  min="0"
                  max="500"
                />
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Max Age</label>
                <select v-model.number="configForm.hours_old" class="input">
                  <option v-for="opt in hoursOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Max Results</label>
                <input 
                  v-model.number="configForm.results_wanted"
                  type="number"
                  class="input"
                  min="10"
                  max="500"
                />
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="form-checkbox">
                  <input v-model="configForm.is_remote" type="checkbox" />
                  <span class="checkbox-box"></span>
                  <span class="checkbox-label">Remote jobs only</span>
                </label>
              </div>
              <div class="form-group">
                <label class="form-label">Country</label>
                <select v-model="configForm.country" class="input">
                  <option v-for="opt in countryOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-checkbox">
                <input v-model="configForm.enabled" type="checkbox" />
                <span class="checkbox-box"></span>
                <span class="checkbox-label">Enable this search</span>
              </label>
            </div>

            <div class="form-actions">
              <button type="button" class="btn btn-secondary" @click="closeConfigForm">
                Cancel
              </button>
              <button 
                type="submit" 
                class="btn btn-primary"
                :disabled="isSubmittingConfig"
              >
                {{ isSubmittingConfig ? 'Saving...' : (isEditMode ? 'Update' : 'Create') }}
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- User Settings Form -->
      <form class="settings-form" @submit.prevent="saveSettings">
        <!-- Default Filters Section -->
        <section class="settings-section">
          <h2 class="section-title">Default Filters</h2>
          <p class="section-description">
            Set your preferred filters that will be applied by default when you open the dashboard.
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
              <input 
                v-model="defaultRemote"
                type="checkbox"
              />
              <span class="checkbox-box"></span>
              <span class="checkbox-label">Show only remote jobs by default</span>
            </label>
          </div>
        </section>
        
        <!-- Exclusions Section -->
        <section class="settings-section">
          <h2 class="section-title">Exclusions</h2>
          <p class="section-description">
            Hide jobs from specific companies or containing certain keywords.
            Separate multiple values with commas.
          </p>
          
          <div class="form-group">
            <label class="form-label">Excluded Companies</label>
            <input 
              v-model="excludedCompanies"
              type="text"
              class="input"
              placeholder="e.g., Acme Corp, Initech, Umbrella"
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
        
        <!-- Actions -->
        <div class="settings-actions">
          <button 
            type="submit" 
            class="btn btn-primary"
            :disabled="isSaving"
          >
            {{ isSaving ? 'Saving...' : 'Save Settings' }}
          </button>
          <button 
            type="button"
            class="btn btn-secondary"
            @click="clearCache"
          >
            Clear Cache
          </button>
        </div>
      </form>
      
      <!-- About Section -->
      <section class="settings-section about-section">
        <h2 class="section-title">About HireWire</h2>
        <p class="about-text">
          HireWire is a job search aggregator that helps you find opportunities 
          across multiple job boards and company career pages.
        </p>
        <p class="about-version">
          Version 0.1.0
        </p>
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

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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

/* Configs List */
.configs-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.config-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.config-card.config-disabled {
  opacity: 0.7;
}

.config-card.config-editing {
  border-color: var(--accent-primary);
  background: var(--bg-secondary);
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-3);
}

.config-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.config-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.config-badge {
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}

.badge-enabled {
  background: var(--success-bg, rgba(34, 197, 94, 0.2));
  color: var(--success-text, #22c55e);
}

.badge-disabled {
  background: var(--warning-bg, rgba(234, 179, 8, 0.2));
  color: var(--warning-text, #eab308);
}

.config-actions {
  display: flex;
  gap: var(--space-1);
}

.btn-icon {
  background: transparent;
  border: none;
  padding: var(--space-2);
  cursor: pointer;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  transition: background var(--transition-fast);
}

.btn-icon:hover {
  background: var(--bg-hover);
}

.btn-icon.btn-danger:hover {
  background: rgba(239, 68, 68, 0.2);
}

.config-details {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.config-field {
  display: flex;
  gap: var(--space-2);
}

.field-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
  flex-shrink: 0;
}

.field-value {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.config-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.meta-item {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

/* Inline edit form */
.config-inline-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.inline-form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-color);
}

.inline-form-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.inline-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-color);
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border: none;
}

.btn-ghost:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

/* Loading and Empty States */
.loading-state,
.empty-state {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-muted);
}

.empty-hint {
  font-size: var(--text-sm);
  margin-top: var(--space-2);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
  margin: var(--space-4);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.btn-close {
  background: transparent;
  border: none;
  font-size: var(--text-xl);
  color: var(--text-muted);
  cursor: pointer;
  padding: var(--space-1);
  line-height: 1;
}

.btn-close:hover {
  color: var(--text-primary);
}

.config-form {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.form-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-color);
}

/* Form Elements */
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

.settings-actions {
  display: flex;
  gap: var(--space-3);
}

.about-section {
  margin-top: var(--space-6);
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

/* Button styles */
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

.btn-sm {
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-xs);
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

/* Input styles */
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

select.input {
  cursor: pointer;
}
</style>
