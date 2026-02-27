<script setup lang="ts">
/**
 * Sidebar - Company-first navigation
 * Shows tracked companies with job counts, plus All Jobs / Favorites entries.
 */
import { computed, ref, onMounted, watch } from 'vue'
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

const companySearch = ref('')

const filteredCompanies = computed(() => {
  const q = companySearch.value.trim().toLowerCase()
  if (!q) return companiesStore.companies
  return companiesStore.companies.filter((c) =>
    c.name.toLowerCase().includes(q)
  )
})

function selectCompany(id: number | null) {
  companiesStore.selectCompany(id)
  // Navigate to dashboard when selecting a company
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

// Re-fetch jobs whenever the selected company changes
watch(() => companiesStore.selectedCompanyId, () => {
  jobsStore.fetchJobs(true)
})

async function syncCompany(id: number, e: Event) {
  e.stopPropagation()
  if (isSyncingId.value === id) return
  isSyncingId.value = id
  try {
    await api.post(`/api/companies/${id}/sync`)
    uiStore.showSuccess('Sync triggered')
    // Refresh company list to get updated job_count
    await companiesStore.fetchCompanies()
    if (companiesStore.selectedCompanyId === id) {
      await jobsStore.fetchJobs(true)
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
        <span v-if="jobsStore.total > 0 && isAllJobsActive" class="nav-badge">
          {{ jobsStore.total.toLocaleString() }}
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
      <button class="add-btn" title="Add company" @click="emit('open-add-company')">
        <span>+</span>
      </button>
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
        @click="selectCompany(company.id)"
      >
        <span class="company-name">{{ company.name }}</span>
        <span v-if="company.job_count > 0" class="company-badge">
          {{ company.job_count }}
        </span>
        <button
          class="company-sync-btn"
          :class="{ spinning: isSyncingId === company.id }"
          :title="`Sync ${company.name}`"
          @click="syncCompany(company.id, $event)"
        >
          ↻
        </button>
      </button>
    </div>

    <!-- Footer -->
    <div class="sidebar-footer">
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

.company-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
}

.footer-nav-link {
  margin-bottom: 0;
}
</style>
