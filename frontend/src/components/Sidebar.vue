<script setup lang="ts">
/**
 * Sidebar - Company-first navigation
 * Shows tracked companies with job counts, plus All Jobs / Favorites entries.
 */
import { computed, ref, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCompaniesStore } from '@/stores/companies'
import { useFavoritesStore } from '@/stores/favorites'
import { useJobsStore } from '@/stores/jobs'
import { useUIStore } from '@/stores/ui'
import { useApi } from '@/composables/useApi'

const route = useRoute()
const router = useRouter()
const companiesStore = useCompaniesStore()
const favoritesStore = useFavoritesStore()
const jobsStore = useJobsStore()
const uiStore = useUIStore()
const api = useApi()

const emit = defineEmits<{ 'open-add-company': [] }>()

const isSyncingId = ref<number | null>(null)
const isDeletingId = ref<number | null>(null)
const isSyncingAll = ref(false)
const editingId = ref<number | null>(null)
const editingName = ref('')

const companySearch = ref('')

function hasUnseenJobs(companyId: number): boolean {
  return (jobsStore.unseenByCompany.get(companyId) ?? 0) > 0
}

// --- Relative time helper ---
function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

const filteredCompanies = computed(() => {
  const q = companySearch.value.trim().toLowerCase()
  if (!q) return companiesStore.companies
  return companiesStore.companies.filter((c) =>
    c.name.toLowerCase().includes(q)
  )
})

function selectCompany(id: number | null) {
  companiesStore.selectCompany(id)
  if (route.name !== 'dashboard') {
    router.push('/')
  }
}

function isCompanyActive(id: number) {
  return route.name === 'dashboard' && companiesStore.selectedCompanyId === id
}

const isAllJobsActive = computed(
  () => route.name === 'dashboard' && companiesStore.selectedCompanyId === null
)

onMounted(() => {
  companiesStore.fetchCompanies()
})

// No fetch needed on company switch — filteredJobs is a computed over allJobs

// --- Inline rename ---
function startEditing(id: number, name: string, e: Event) {
  e.stopPropagation()
  editingId.value = id
  editingName.value = name
  nextTick(() => {
    const input = document.querySelector('.company-edit-input') as HTMLInputElement | null
    input?.focus()
    input?.select()
  })
}

async function saveEdit(id: number) {
  const trimmed = editingName.value.trim()
  if (trimmed && trimmed !== companiesStore.companies.find(c => c.id === id)?.name) {
    try {
      await companiesStore.updateCompany(id, { name: trimmed })
    } catch {
      uiStore.showError('Failed to rename company')
    }
  }
  editingId.value = null
}

function cancelEdit() {
  editingId.value = null
}

// --- Sync ---
async function syncAll() {
  if (isSyncingAll.value) return
  isSyncingAll.value = true
  try {
    await api.post('/api/companies/sync-all')
    uiStore.showSuccess('Full sync triggered')
    await companiesStore.fetchCompanies()
    jobsStore.fetchAllJobs()
  } catch {
    uiStore.showError('Sync failed or scraper not available')
  } finally {
    isSyncingAll.value = false
  }
}

async function deleteCompany(id: number, e: Event) {
  e.stopPropagation()
  if (isDeletingId.value === id) return
  if (!confirm('Remove this company and its jobs?')) return
  isDeletingId.value = id
  try {
    await companiesStore.deleteCompany(id)
    jobsStore.fetchAllJobs()
  } catch {
    uiStore.showError('Failed to delete company')
  } finally {
    isDeletingId.value = null
  }
}

async function syncCompany(id: number, e: Event) {
  e.stopPropagation()
  if (isSyncingId.value === id) return
  isSyncingId.value = id
  try {
    const result = await companiesStore.syncCompany(id)
    if (result && result.new_jobs > 0) {
      uiStore.showSuccess(`Sync done — ${result.new_jobs} new job${result.new_jobs === 1 ? '' : 's'}`)
    } else {
      uiStore.showSuccess('Sync complete — no new jobs')
    }
  } catch {
    uiStore.showError('Sync failed or scraper not available')
  } finally {
    isSyncingId.value = null
  }
}
</script>

<template>
  <nav class="sidebar">
    <!-- Brand -->
    <div class="sidebar-header">
      <RouterLink to="/" class="sidebar-brand" @click="selectCompany(null)">
        <span class="sidebar-logo">💼</span>
        <span class="sidebar-title">HireWire</span>
      </RouterLink>
    </div>

    <!-- Company search -->
    <div class="sidebar-search">
      <input
        v-model="companySearch"
        class="search-input"
        type="text"
        placeholder="Search companies..."
        autocomplete="off"
      />
    </div>

    <!-- Static nav items -->
    <div class="sidebar-nav-static">
      <RouterLink
        to="/"
        class="nav-link"
        :class="{ active: isAllJobsActive }"
        @click="selectCompany(null)"
      >
        <span class="nav-icon">📋</span>
        <span class="nav-label">All Jobs</span>
        <span v-if="jobsStore.unseenTotal > 0" class="nav-badge">
          {{ jobsStore.unseenTotal.toLocaleString() }}
        </span>
      </RouterLink>

      <RouterLink to="/favorites" class="nav-link" :class="{ active: route.name === 'favorites' }">
        <span class="nav-icon">⭐</span>
        <span class="nav-label">Favorites</span>
        <span v-if="favoritesStore.favoriteCount > 0" class="nav-badge">
          {{ favoritesStore.favoriteCount }}
        </span>
      </RouterLink>
    </div>

    <!-- Companies section -->
    <div class="section-header">
      <span class="section-label">Companies</span>
      <div class="section-actions">
        <button class="add-btn" title="Add company" @click="emit('open-add-company')">
          +
        </button>
      </div>
    </div>

    <!-- Company list -->
    <div class="company-list">
      <div
        v-if="companiesStore.isLoading && companiesStore.companies.length === 0"
        class="company-list-empty"
      >
        Loading...
      </div>

      <div
        v-else-if="filteredCompanies.length === 0"
        class="company-list-empty"
      >
        <span v-if="companySearch">No match</span>
        <span v-else>No companies yet.<br />Click + to add one.</span>
      </div>

      <button
        v-for="company in filteredCompanies"
        :key="company.id"
        class="company-item"
        :class="{ active: isCompanyActive(company.id), disabled: !company.enabled }"
        :title="`Last synced: ${timeAgo(company.last_scraped)}`"
        @click="selectCompany(company.id)"
      >
        <span v-if="hasUnseenJobs(company.id)" class="new-dot" aria-label="Unseen jobs"></span>
        <template v-if="editingId === company.id">
          <input
            v-model="editingName"
            class="company-edit-input"
            @click.stop
            @keydown.enter="saveEdit(company.id)"
            @keydown.escape="cancelEdit"
            @blur="saveEdit(company.id)"
          />
        </template>
        <template v-else>
          <span class="company-name">{{ company.name }}</span>
          <span v-if="company.glassdoor_rating" class="company-rating" :title="`Glassdoor: ${company.glassdoor_rating}/5`">
            ★ {{ company.glassdoor_rating.toFixed(1) }}
          </span>
        </template>
        <span v-if="(jobsStore.unseenByCompany.get(company.id) ?? 0) > 0 && editingId !== company.id" class="company-badge">
          {{ jobsStore.unseenByCompany.get(company.id) }}
        </span>
        <button
          v-if="editingId !== company.id"
          class="company-edit-btn"
          :title="`Rename ${company.name}`"
          @click="startEditing(company.id, company.name, $event)"
        >
          ✎
        </button>
        <button
          v-if="editingId !== company.id"
          class="company-sync-btn"
          :class="{ spinning: isSyncingId === company.id }"
          :title="`Sync ${company.name}`"
          @click="syncCompany(company.id, $event)"
        >
          ↻
        </button>
        <button
          v-if="editingId !== company.id"
          class="company-delete-btn"
          :title="`Remove ${company.name}`"
          @click="deleteCompany(company.id, $event)"
        >
          ✕
        </button>
      </button>
    </div>

    <!-- Footer -->
    <div class="sidebar-footer">
      <button
        class="sync-all-btn"
        :class="{ spinning: isSyncingAll }"
        :disabled="isSyncingAll"
        title="Sync all companies"
        @click="syncAll"
      >
        <span class="sync-icon">↻</span>
        <span class="sync-label">{{ isSyncingAll ? 'Syncing...' : 'Sync All' }}</span>
      </button>
      <RouterLink to="/settings" class="nav-link footer-nav-link" :class="{ active: route.name === 'settings' }">
        <span class="nav-icon">⚙️</span>
        <span class="nav-label">Settings</span>
      </RouterLink>
    </div>
  </nav>
</template>

<style scoped>
.sidebar {
  width: 240px;
  min-width: 240px;
  height: 100vh;
  position: sticky;
  top: 0;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}

/* Header */
.sidebar-header {
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  text-decoration: none;
}

.sidebar-logo {
  font-size: var(--text-2xl);
}

.sidebar-title {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
}

/* Search */
.sidebar-search {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.search-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-sm);
  outline: none;
  box-sizing: border-box;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.search-input:focus {
  border-color: var(--border-focus);
}

/* Static nav (All Jobs, Favorites) */
.sidebar-nav-static {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: var(--text-sm);
  font-weight: 500;
  transition: all var(--transition-fast);
  margin-bottom: var(--space-1);
  cursor: pointer;
}

.nav-link:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-link.active {
  background: var(--bg-active);
  color: var(--accent-primary);
}

.nav-icon {
  font-size: 1rem;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

.nav-label {
  flex: 1;
}

.nav-badge {
  padding: 1px 7px;
  background: var(--accent-primary);
  color: white;
  font-size: var(--text-xs);
  font-weight: 600;
  border-radius: 10px;
  min-width: 20px;
  text-align: center;
}

/* Companies section header */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3) var(--space-1);
  flex-shrink: 0;
}

.section-label {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.section-actions {
  display: flex;
  gap: var(--space-1);
}

.add-btn {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: var(--text-base);
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  line-height: 1;
}

.add-btn:hover {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: white;
}

/* Company list */
.company-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-1) var(--space-2) var(--space-2);
  scrollbar-width: thin;
  scrollbar-color: var(--border-color) transparent;
}

.company-list-empty {
  padding: var(--space-3);
  color: var(--text-muted);
  font-size: var(--text-xs);
  text-align: center;
  line-height: 1.5;
}

.company-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  transition: all var(--transition-fast);
  margin-bottom: 2px;
}

.company-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.company-item.active {
  background: var(--bg-active);
  color: var(--accent-primary);
}

.company-item.disabled {
  opacity: 0.5;
}

.new-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-primary);
  flex-shrink: 0;
}

.company-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.company-rating {
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 500;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.company-item.active .company-rating {
  color: var(--accent-primary);
  opacity: 0.7;
}

.company-edit-input {
  flex: 1;
  min-width: 0;
  padding: 2px 4px;
  background: var(--bg-tertiary);
  border: 1px solid var(--accent-primary);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 500;
  outline: none;
}

.company-edit-btn {
  display: none;
  width: 18px;
  height: 18px;
  border-radius: 3px;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: color var(--transition-fast);
}

.company-item:hover .company-edit-btn {
  display: flex;
}

.company-edit-btn:hover {
  color: var(--accent-primary);
}

.company-badge {
  padding: 1px 6px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  font-size: var(--text-xs);
  font-weight: 600;
  border-radius: 9px;
  min-width: 18px;
  text-align: center;
  flex-shrink: 0;
}

.company-item.active .company-badge {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: white;
}

.company-sync-btn {
  display: none;
  width: 18px;
  height: 18px;
  border-radius: 3px;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 14px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: color var(--transition-fast);
}

.company-item:hover .company-sync-btn {
  display: flex;
}

.company-sync-btn:hover {
  color: var(--accent-primary);
}

.company-delete-btn {
  display: none;
  width: 18px;
  height: 18px;
  border-radius: 3px;
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: color var(--transition-fast);
}

.company-item:hover .company-delete-btn {
  display: flex;
}

.company-delete-btn:hover {
  color: #e05252;
}

.company-sync-btn.spinning {
  display: flex;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Footer */
.sidebar-footer {
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.footer-nav-link {
  margin-bottom: 0;
}

.sync-all-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.sync-all-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.sync-all-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.sync-icon {
  font-size: 1rem;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

.sync-all-btn.spinning .sync-icon {
  display: inline-block;
  animation: spin 1s linear infinite;
}
</style>
