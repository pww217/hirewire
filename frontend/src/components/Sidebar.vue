<script setup lang="ts">
/**
 * Sidebar - Company-first navigation
 * Shows tracked companies with job counts and glassdoor ratings.
 * Company management actions (rename, sync, delete) live on the company page header.
 */
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCompaniesStore } from '@/stores/companies'
import { useFavoritesStore } from '@/stores/favorites'
import { useApplicationsStore } from '@/stores/applications'
import { useJobsStore } from '@/stores/jobs'
import { useUIStore } from '@/stores/ui'
import { useApi } from '@/composables/useApi'

const route = useRoute()
const router = useRouter()
const companiesStore = useCompaniesStore()
const favoritesStore = useFavoritesStore()
const applicationsStore = useApplicationsStore()
const jobsStore = useJobsStore()

const emit = defineEmits<{ 'open-add-company': [] }>()
const uiStore = useUIStore()
const api = useApi()

const companySearch = ref('')
const isSyncingAll = ref(false)
const isRefreshingRatings = ref(false)

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

const hasMissingRatings = computed(() =>
  companiesStore.companies.some((c) => c.enabled && c.glassdoor_rating === null)
)

async function refreshMissingRatings() {
  if (isRefreshingRatings.value) return
  isRefreshingRatings.value = true
  try {
    const result = await api.post<{ refreshed: number; still_missing: number }>('/api/companies/refresh-ratings')
    if (result.refreshed > 0) {
      uiStore.showSuccess(`Fetched ${result.refreshed} missing Glassdoor rating${result.refreshed !== 1 ? 's' : ''}`)
      await companiesStore.fetchCompanies()
      jobsStore.fetchAllJobs()
    } else {
      uiStore.showInfo('No new ratings retrieved — Glassdoor may be blocking requests')
    }
  } catch {
    uiStore.showError('Failed to refresh Glassdoor ratings')
  } finally {
    isRefreshingRatings.value = false
  }
}

const filteredCompanies = computed(() => {
  const q = companySearch.value.trim().toLowerCase()
  const list = q
    ? companiesStore.companies.filter((c) => c.name.toLowerCase().includes(q))
    : [...companiesStore.companies]
  return list.sort((a, b) => a.name.localeCompare(b.name))
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

      <RouterLink to="/applied" class="nav-link" :class="{ active: route.name === 'applied' }">
        <span class="nav-icon">✅</span>
        <span class="nav-label">Applied</span>
        <span v-if="applicationsStore.appliedCount > 0" class="nav-badge nav-badge-green">
          {{ applicationsStore.appliedCount }}
        </span>
      </RouterLink>

      <RouterLink to="/hidden" class="nav-link" :class="{ active: route.name === 'hidden' }">
        <span class="nav-icon">🙈</span>
        <span class="nav-label">Hidden</span>
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
        :title="company.name"
        @click="selectCompany(company.id)"
      >
        <span class="company-name">{{ company.name }}</span>

        <!-- Glassdoor rating -->
        <a
          v-if="company.glassdoor_rating && company.glassdoor_url"
          :href="company.glassdoor_url"
          class="company-rating has-rating"
          :title="`Glassdoor: ${company.glassdoor_rating.toFixed(1)}/5 — click to view reviews`"
          target="_blank"
          rel="noopener"
          @click.stop
        >
          ★ {{ company.glassdoor_rating.toFixed(1) }}
        </a>
        <span
          v-else-if="company.glassdoor_rating"
          class="company-rating has-rating"
          :title="`Glassdoor: ${company.glassdoor_rating.toFixed(1)}/5`"
        >
          ★ {{ company.glassdoor_rating.toFixed(1) }}
        </span>
        <a
          v-else-if="company.glassdoor_url"
          :href="company.glassdoor_url"
          class="company-rating rating-unavailable"
          title="Glassdoor rating unavailable — click to view on Glassdoor"
          target="_blank"
          rel="noopener"
          @click.stop
        >
          ★ --
        </a>
        <span
          v-else-if="company.glassdoor_id"
          class="company-rating rating-unavailable"
          title="Glassdoor rating unavailable"
        >
          ★ --
        </span>

        <!-- Unread badge (always highlighted when > 0) -->
        <span
          v-if="(jobsStore.unseenByCompany.get(company.id) ?? 0) > 0"
          class="company-badge"
        >
          {{ jobsStore.unseenByCompany.get(company.id) }}
        </span>
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
      <button
        class="refresh-ratings-btn"
        :class="{ spinning: isRefreshingRatings, 'has-missing': hasMissingRatings }"
        :disabled="isRefreshingRatings"
        title="Retry fetching missing Glassdoor ratings"
        @click="refreshMissingRatings"
      >
        <span class="sync-icon">★</span>
        <span class="sync-label">{{ isRefreshingRatings ? 'Fetching...' : 'Retry Ratings' }}</span>
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

.nav-badge-green {
  background: #22c55e;
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

/* Company list - scrollable */
.company-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-1) var(--space-2) var(--space-2);
  scrollbar-width: thin;
  scrollbar-color: var(--border-color) transparent;
  min-height: 0;
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
  gap: var(--space-2);
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
  min-width: 0;
}

/* Glassdoor rating - orange when rated */
.company-rating {
  font-size: 10px;
  font-weight: 500;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.company-rating.has-rating {
  color: #d4900a;
}

a.company-rating.has-rating {
  text-decoration: none;
  border-radius: 3px;
  padding: 1px 2px;
  transition: background var(--transition-fast);
}

a.company-rating.has-rating:hover {
  background: rgba(212, 144, 10, 0.12);
  text-decoration: underline;
}

.company-item.active .company-rating.has-rating {
  color: #e8a020;
}

.company-rating.rating-unavailable {
  color: var(--text-muted);
  opacity: 0.6;
}

a.company-rating.rating-unavailable {
  text-decoration: none;
  border-radius: 3px;
  padding: 1px 2px;
  transition: background var(--transition-fast), opacity var(--transition-fast);
}

a.company-rating.rating-unavailable:hover {
  background: rgba(128, 128, 128, 0.1);
  opacity: 1;
  text-decoration: underline;
}

/* Unread badge - always highlighted when count > 0 */
.company-badge {
  padding: 1px 6px;
  background: var(--accent-primary);
  border: 1px solid var(--accent-primary);
  color: white;
  font-size: var(--text-xs);
  font-weight: 600;
  border-radius: 9px;
  min-width: 18px;
  text-align: center;
  flex-shrink: 0;
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

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.refresh-ratings-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-weight: 400;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
  opacity: 0.6;
}

.refresh-ratings-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-secondary);
  opacity: 1;
}

.refresh-ratings-btn.has-missing {
  color: var(--text-secondary);
  font-weight: 500;
  opacity: 1;
}

.refresh-ratings-btn:disabled {
  cursor: not-allowed;
}

.refresh-ratings-btn.spinning .sync-icon {
  display: inline-block;
  animation: spin 1s linear infinite;
}
</style>
