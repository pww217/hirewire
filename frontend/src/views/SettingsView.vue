<script setup lang="ts">
/**
 * SettingsView - Company import/export and about.
 */
import { ref } from 'vue'
import { useCompaniesStore } from '@/stores/companies'
import type { CompanyImportResponse } from '@/types/api'

const companiesStore = useCompaniesStore()

const isExporting = ref(false)
const isImporting = ref(false)
const importFile = ref<File | null>(null)
const importResult = ref<CompanyImportResponse | null>(null)
const importError = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const isClearingRatings = ref(false)
const clearRatingsConfirm = ref(false)
const clearRatingsResult = ref<{ cleared: number } | null>(null)
const clearRatingsError = ref<string | null>(null)

async function handleClearRatings() {
  isClearingRatings.value = true
  clearRatingsResult.value = null
  clearRatingsError.value = null
  clearRatingsConfirm.value = false
  try {
    clearRatingsResult.value = await companiesStore.clearGlassdoorRatings()
  } catch (e) {
    clearRatingsError.value = e instanceof Error ? e.message : 'Clear failed'
  } finally {
    isClearingRatings.value = false
  }
}

async function handleExport() {
  isExporting.value = true
  try {
    await companiesStore.exportCompanies()
  } catch (e) {
    console.error(e)
  } finally {
    isExporting.value = false
  }
}

function onFileSelected(e: Event) {
  const target = e.target as HTMLInputElement
  importFile.value = target.files?.[0] ?? null
  importResult.value = null
  importError.value = null
}

async function handleImport() {
  if (!importFile.value) return
  isImporting.value = true
  importResult.value = null
  importError.value = null
  try {
    importResult.value = await companiesStore.importCompanies(importFile.value)
    importFile.value = null
    if (fileInput.value) fileInput.value.value = ''
  } catch (e) {
    importError.value = e instanceof Error ? e.message : 'Import failed'
  } finally {
    isImporting.value = false
  }
}
</script>

<template>
  <div class="settings-view">
    <header class="settings-header">
      <h1 class="settings-title">Settings</h1>
    </header>

    <main class="settings-content">

      <!-- Company Data -->
      <section class="settings-section">
        <h2 class="section-title">Company Data</h2>
        <p class="section-desc">Export your tracked companies or bulk-import new ones via CSV. Import deduplicates by ATS type + slug and skips anything already tracked.</p>

        <div class="action-row">
          <div class="action-block">
            <span class="action-label">Export</span>
            <p class="action-hint">Download all tracked companies as a CSV file.</p>
            <button
              class="btn btn-secondary"
              :disabled="isExporting"
              @click="handleExport"
            >
              {{ isExporting ? 'Exporting…' : 'Export Companies' }}
            </button>
          </div>

          <div class="action-divider" />

          <div class="action-block">
            <span class="action-label">Import</span>
            <p class="action-hint">CSV must have columns: <code>name</code>, <code>ats_type</code>, <code>ats_identifier</code>. Optional: <code>website</code>, <code>enabled</code>.</p>
            <div class="import-row">
              <input
                ref="fileInput"
                type="file"
                accept=".csv"
                class="file-input"
                @change="onFileSelected"
              />
              <button
                class="btn btn-primary"
                :disabled="!importFile || isImporting"
                @click="handleImport"
              >
                {{ isImporting ? 'Importing…' : 'Import' }}
              </button>
            </div>
            <div v-if="importResult" class="result-box result-success">
              <strong>Done:</strong> {{ importResult.imported }} imported, {{ importResult.skipped }} skipped.
              <ul v-if="importResult.errors.length" class="error-list">
                <li v-for="(err, i) in importResult.errors" :key="i">{{ err }}</li>
              </ul>
            </div>
            <div v-if="importError" class="result-box result-error">{{ importError }}</div>
          </div>
        </div>
      </section>

      <!-- Glassdoor Data -->
      <section class="settings-section">
        <h2 class="section-title">Glassdoor Data</h2>
        <p class="section-desc">Clear all stored Glassdoor ratings and company IDs. Ratings will be re-fetched from scratch on the next refresh run.</p>

        <div class="action-block">
          <span class="action-label">Clear All Ratings</span>
          <p class="action-hint">Wipes glassdoor_rating, glassdoor_id, and glassdoor_url for all companies.</p>

          <div v-if="!clearRatingsConfirm">
            <button
              class="btn btn-danger"
              :disabled="isClearingRatings"
              @click="clearRatingsConfirm = true"
            >
              Clear Glassdoor Ratings
            </button>
          </div>

          <div v-else class="confirm-row">
            <span class="confirm-prompt">Are you sure? This cannot be undone.</span>
            <button
              class="btn btn-danger"
              :disabled="isClearingRatings"
              @click="handleClearRatings"
            >
              {{ isClearingRatings ? 'Clearing…' : 'Yes, clear all' }}
            </button>
            <button
              class="btn btn-secondary"
              :disabled="isClearingRatings"
              @click="clearRatingsConfirm = false"
            >
              Cancel
            </button>
          </div>

          <div v-if="clearRatingsResult" class="result-box result-success">
            Cleared Glassdoor data for <strong>{{ clearRatingsResult.cleared }}</strong> {{ clearRatingsResult.cleared === 1 ? 'company' : 'companies' }}.
          </div>
          <div v-if="clearRatingsError" class="result-box result-error">{{ clearRatingsError }}</div>
        </div>
      </section>

      <!-- About -->
      <section class="settings-section">
        <h2 class="section-title">About HireWire</h2>
        <p class="about-text">
          HireWire tracks job listings directly from company ATS boards (Greenhouse, Lever, Ashby).
          Use the filter panel on the main view to search and filter jobs by location, work type, keywords, and more.
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

.section-desc {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-4);
  line-height: 1.6;
}

.action-row {
  display: flex;
  gap: var(--space-5);
  align-items: flex-start;
}

.action-block {
  flex: 1;
}

.action-divider {
  width: 1px;
  background: var(--border-color);
  align-self: stretch;
  flex-shrink: 0;
}

.action-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}

.action-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-bottom: var(--space-3);
  line-height: 1.5;
}

.action-hint code {
  font-family: var(--font-mono);
  background: var(--bg-tertiary);
  padding: 1px 4px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
}

.import-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.file-input {
  flex: 1;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-2);
  cursor: pointer;
}

.file-input::-webkit-file-upload-button {
  display: none;
}

.result-box {
  margin-top: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}

.result-success {
  background: color-mix(in srgb, var(--accent-success) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent-success) 30%, transparent);
  color: var(--accent-success);
}

.result-error {
  background: color-mix(in srgb, var(--accent-error) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent-error) 30%, transparent);
  color: var(--accent-error);
}

.error-list {
  margin-top: var(--space-2);
  padding-left: var(--space-4);
  color: var(--accent-warning);
  font-size: var(--text-xs);
}

.confirm-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.confirm-prompt {
  font-size: var(--text-sm);
  color: var(--accent-warning);
  margin-right: var(--space-1);
}

.btn-danger {
  background: color-mix(in srgb, var(--accent-error) 15%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent-error) 40%, transparent);
  color: var(--accent-error);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-danger:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent-error) 25%, transparent);
}

.btn-danger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.about-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
  line-height: 1.6;
}

.about-version {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
}
</style>
