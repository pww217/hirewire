<script setup lang="ts">
/**
 * SettingsView - User settings page
 */
import { ref, onMounted } from 'vue'
import { useJobsStore } from '@/stores/jobs'
import { useUIStore } from '@/stores/ui'

const jobsStore = useJobsStore()
const uiStore = useUIStore()

const excludedCompanies = ref('')
const excludedKeywords = ref('')
const defaultLocation = ref('')
const defaultRemote = ref(false)
const isSaving = ref(false)

onMounted(() => {
  // Load from localStorage for now (Phase 2 will use API)
  const saved = localStorage.getItem('hirewire_settings')
  if (saved) {
    try {
      const settings = JSON.parse(saved)
      excludedCompanies.value = settings.excludedCompanies?.join(', ') || ''
      excludedKeywords.value = settings.excludedKeywords?.join(', ') || ''
      defaultLocation.value = settings.defaultLocation || ''
      defaultRemote.value = settings.defaultRemote || false
    } catch (e) {
      console.error('Failed to load settings:', e)
    }
  }
})

async function saveSettings() {
  isSaving.value = true
  
  try {
    const settings = {
      excludedCompanies: excludedCompanies.value
        .split(',')
        .map(s => s.trim())
        .filter(Boolean),
      excludedKeywords: excludedKeywords.value
        .split(',')
        .map(s => s.trim())
        .filter(Boolean),
      defaultLocation: defaultLocation.value || null,
      defaultRemote: defaultRemote.value,
    }
    
    localStorage.setItem('hirewire_settings', JSON.stringify(settings))
    uiStore.showSuccess('Settings saved')
    
    // Apply default filters
    if (settings.defaultLocation || settings.defaultRemote) {
      jobsStore.setFilters({
        location: settings.defaultLocation || '',
        isRemote: settings.defaultRemote ? true : null,
      })
    }
  } catch (e) {
    uiStore.showError('Failed to save settings')
  } finally {
    isSaving.value = false
  }
}

function clearCache() {
  localStorage.removeItem('hirewire_settings')
  localStorage.removeItem('hirewire_ui_prefs')
  excludedCompanies.value = ''
  excludedKeywords.value = ''
  defaultLocation.value = ''
  defaultRemote.value = false
  uiStore.showSuccess('Cache cleared')
}
</script>

<template>
  <div class="settings-view">
    <header class="settings-header">
      <h1 class="settings-title">Settings</h1>
    </header>
    
    <main class="settings-content">
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
  max-width: 600px;
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
</style>
