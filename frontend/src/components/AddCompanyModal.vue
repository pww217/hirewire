<script setup lang="ts">
/**
 * AddCompanyModal - Add a new company to track.
 *
 * Flow:
 *  1. User pastes a career page URL → auto-detect ATS type + slug
 *  2. If detected: show preview, confirm or adjust
 *  3. If not detected: show manual ATS type + slug fields
 *  4. Always require a company name
 *  5. Submit → POST /api/companies
 */
import { ref, computed } from 'vue'
import { useCompaniesStore } from '@/stores/companies'
import { useUIStore } from '@/stores/ui'
import type { ATSType } from '@/types/api'

const emit = defineEmits<{ close: []; created: [id: number] }>()

const companiesStore = useCompaniesStore()
const uiStore = useUIStore()

// Form state
const url = ref('')
const name = ref('')
const atsType = ref<ATSType | null>(null)
const atsIdentifier = ref('')

// Detection state
const isDetecting = ref(false)
const detectionDone = ref(false)
const detectionSuccess = ref(false)
const detectionMessage = ref('')

// Submission state
const isSubmitting = ref(false)

const ATS_LABELS: Record<ATSType, string> = {
  greenhouse: 'Greenhouse',
  lever: 'Lever',
  ashby: 'Ashby',
}

const canSubmit = computed(
  () =>
    name.value.trim().length > 0 &&
    atsType.value !== null &&
    atsIdentifier.value.trim().length > 0 &&
    !isSubmitting.value
)

// Capitalize a slug into a display name: "monarchmoney" → "Monarchmoney"
function slugToName(slug: string): string {
  return slug.charAt(0).toUpperCase() + slug.slice(1)
}

async function detectFromUrl() {
  const trimmed = url.value.trim()
  if (!trimmed) return

  isDetecting.value = true
  detectionDone.value = false

  try {
    const result = await companiesStore.detectAts(trimmed)
    detectionDone.value = true

    if (result.detected && result.ats_type && result.ats_identifier) {
      atsType.value = result.ats_type
      atsIdentifier.value = result.ats_identifier
      detectionSuccess.value = true
      detectionMessage.value = `Detected: ${ATS_LABELS[result.ats_type]} (${result.ats_identifier})`
    } else {
      detectionSuccess.value = false
      detectionMessage.value = 'Could not detect ATS automatically — fill in manually below.'
    }

    // Pre-fill name from slug if empty
    if (!name.value && result.ats_identifier) {
      name.value = slugToName(result.ats_identifier)
    }
  } catch {
    detectionDone.value = true
    detectionSuccess.value = false
    detectionMessage.value = 'Detection failed — fill in manually below.'
  } finally {
    isDetecting.value = false
  }
}

// Trigger detection on URL blur or Enter
function onUrlBlur() {
  if (url.value.trim() && !detectionDone.value) {
    detectFromUrl()
  }
}

function onUrlKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault()
    detectFromUrl()
  }
}

async function submit() {
  if (!canSubmit.value) return

  isSubmitting.value = true
  try {
    const company = await companiesStore.createCompany({
      name: name.value.trim(),
      ats_type: atsType.value!,
      ats_identifier: atsIdentifier.value.trim(),
      enabled: true,
    })
    // Select the new company so the user lands on its view
    // DashboardView will auto-trigger sync (with spinner) when it detects a new unsynced company
    companiesStore.selectCompany(company.id)
    emit('created', company.id)
    emit('close')
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Failed to add company'
    uiStore.showError(msg)
  } finally {
    isSubmitting.value = false
  }
}

function close() {
  emit('close')
}
</script>

<template>
  <div class="modal-overlay" @click.self="close">
    <div class="modal">
      <div class="modal-header">
        <h2 class="modal-title">Add Company</h2>
        <button class="modal-close" @click="close">✕</button>
      </div>

      <div class="modal-body">
        <!-- URL input + detect -->
        <div class="field">
          <label class="field-label">Career page URL</label>
          <div class="url-row">
            <input
              v-model="url"
              class="field-input"
              type="url"
              placeholder="https://jobs.lever.co/stripe"
              autocomplete="off"
              @blur="onUrlBlur"
              @keydown="onUrlKeydown"
            />
            <button
              class="detect-btn"
              :disabled="isDetecting || !url.trim()"
              @click="detectFromUrl"
            >
              {{ isDetecting ? '…' : 'Detect' }}
            </button>
          </div>
          <p
            v-if="detectionDone"
            class="detect-result"
            :class="{ success: detectionSuccess, warn: !detectionSuccess }"
          >
            {{ detectionMessage }}
          </p>
          <p v-else class="field-hint">
            Paste a Greenhouse, Lever, or Ashby careers URL to auto-detect the ATS.
          </p>
        </div>

        <!-- Company name -->
        <div class="field">
          <label class="field-label">Company name <span class="required">*</span></label>
          <input
            v-model="name"
            class="field-input"
            type="text"
            placeholder="Acme Corp"
            autocomplete="off"
          />
        </div>

        <!-- ATS type -->
        <div class="field-row">
          <div class="field">
            <label class="field-label">ATS <span class="required">*</span></label>
            <select v-model="atsType" class="field-input field-select">
              <option :value="null" disabled>Select…</option>
              <option value="greenhouse">Greenhouse</option>
              <option value="lever">Lever</option>
              <option value="ashby">Ashby</option>
            </select>
          </div>

          <div class="field field-flex">
            <label class="field-label">Slug / identifier <span class="required">*</span></label>
            <input
              v-model="atsIdentifier"
              class="field-input"
              type="text"
              placeholder="acme"
              autocomplete="off"
            />
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn btn-secondary" @click="close">Cancel</button>
        <button class="btn btn-primary" :disabled="!canSubmit" @click="submit">
          {{ isSubmitting ? 'Adding…' : 'Add Company' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--space-4);
}

.modal {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 480px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-color);
}

.modal-title {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: var(--text-base);
  cursor: pointer;
  padding: var(--space-1);
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast);
}

.modal-close:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.modal-footer {
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.field-flex {
  flex: 1;
}

.field-row {
  display: flex;
  gap: var(--space-3);
}

.field-label {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
}

.required {
  color: var(--accent-danger, #ef4444);
}

.field-input {
  padding: var(--space-2) var(--space-3);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-sm);
  outline: none;
  transition: border-color var(--transition-fast);
}

.field-input:focus {
  border-color: var(--border-focus);
}

.field-select {
  cursor: pointer;
  appearance: none;
}

.field-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin: 0;
}

.url-row {
  display: flex;
  gap: var(--space-2);
}

.url-row .field-input {
  flex: 1;
}

.detect-btn {
  padding: var(--space-2) var(--space-3);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition-fast);
}

.detect-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--border-focus);
}

.detect-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.detect-result {
  font-size: var(--text-xs);
  margin: 0;
}

.detect-result.success {
  color: var(--accent-success, #22c55e);
}

.detect-result.warn {
  color: var(--accent-warning, #f59e0b);
}

/* Buttons */
.btn {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--transition-fast);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-tertiary);
  border-color: var(--border-color);
  color: var(--text-secondary);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.btn-primary {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}
</style>
