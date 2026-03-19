<script setup lang="ts">
/**
 * DashboardView - Main job listing page
 * 
 * Keyboard shortcuts:
 * - j/↓: Next job
 * - k/↑: Previous job
 * - f: Toggle favorite
 * - h: Hide job
 * - Enter: Open job detail
 * - /: Focus search
 * - Esc: Clear selection / close filter panel
 */
import { onMounted, watch, watchEffect, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useJobsStore } from '@/stores/jobs'
import { useFavoritesStore } from '@/stores/favorites'
import { useUIStore } from '@/stores/ui'
import { useStatsStore } from '@/stores/stats'
import { useViewedStore } from '@/stores/viewed'
import { useCompaniesStore } from '@/stores/companies'
import { useApplicationsStore } from '@/stores/applications'
import { useKeyboardNav } from '@/composables/useKeyboardNav'
import SearchBar from '@/components/SearchBar.vue'
import FilterPanel from '@/components/FilterPanel.vue'
import SortControls from '@/components/SortControls.vue'
import JobList from '@/components/JobList.vue'

const router = useRouter()
const jobsStore = useJobsStore()
const favoritesStore = useFavoritesStore()
const uiStore = useUIStore()
const statsStore = useStatsStore()
const viewedStore = useViewedStore()
const companiesStore = useCompaniesStore()
const applicationsStore = useApplicationsStore()

const showStatsDetails = ref(false)
const searchBarRef = ref<{ focus: () => void } | null>(null)

// --- Company management state (previously in Sidebar) ---
const isSyncingCompany = ref(false)
const isDeletingCompany = ref(false)
const isEditingName = ref(false)
const editingName = ref('')
const removedCompany = ref<typeof companiesStore.companies[0] | null>(null)

const selectedCompany = computed(() => companiesStore.selectedCompany)

const companyUnseenCount = computed(() =>
  selectedCompany.value
    ? (jobsStore.unseenByCompany.get(selectedCompany.value.id) ?? 0)
    : 0
)

const globalUnseenCount = computed(() => jobsStore.unseenTotal)

function startRename() {
  if (!selectedCompany.value) return
  if (isEditingName.value) {
    cancelRename()
    return
  }
  editingName.value = selectedCompany.value.name
  isEditingName.value = true
}

async function saveRename() {
  if (!selectedCompany.value) return
  const trimmed = editingName.value.trim()
  isEditingName.value = false
  if (trimmed && trimmed !== selectedCompany.value.name) {
    try {
      await companiesStore.updateCompany(selectedCompany.value.id, { name: trimmed })
    } catch {
      uiStore.showError('Failed to rename company')
    }
  }
}

function cancelRename() {
  isEditingName.value = false
}

async function syncSelectedCompany() {
  if (!selectedCompany.value || isSyncingCompany.value) return
  isSyncingCompany.value = true
  try {
    const result = await companiesStore.syncCompany(selectedCompany.value.id)
    if (result && result.new_jobs > 0) {
      uiStore.showSuccess(`Sync done — ${result.new_jobs} new job${result.new_jobs === 1 ? '' : 's'}`)
    } else {
      uiStore.showSuccess('Sync complete — no new jobs')
    }
  } catch {
    uiStore.showError('Sync failed or scraper not available')
  } finally {
    isSyncingCompany.value = false
  }
}

async function deleteSelectedCompany() {
  if (!selectedCompany.value || isDeletingCompany.value) return
  const company = selectedCompany.value
  isDeletingCompany.value = true
  try {
    await companiesStore.deleteCompany(company.id)
    jobsStore.removeJobsByCompany(company.id)
    removedCompany.value = company
  } catch {
    uiStore.showError('Failed to delete company')
  } finally {
    isDeletingCompany.value = false
  }
}

async function restoreCompany() {
  if (!removedCompany.value) return
  const cached = removedCompany.value
  removedCompany.value = null
  try {
    const created = await companiesStore.createCompany({
      name: cached.name,
      website: cached.website,
      ats_type: cached.ats_type,
      ats_identifier: cached.ats_identifier,
    })
    companiesStore.selectCompany(created.id)
  } catch {
    uiStore.showError('Failed to restore company')
  }
}

async function handleMarkAllRead(companyId?: number) {
  try {
    await viewedStore.markAllSeen(companyId)
    uiStore.showSuccess('Marked all as read')
  } catch {
    uiStore.showError('Failed to mark as read')
  }
}

// Keyboard navigation
const { selectedJobId } = useKeyboardNav({
  jobs: () => jobsStore.filteredJobs,
  onFavorite: handleFavorite,
  onHide: handleHide,
  onOpenJob: handleJobClick,
  onClosePanel: () => {
    if (uiStore.isFilterPanelOpen) {
      uiStore.toggleFilterPanel()
    }
  },
  searchInputRef: () => {
    searchBarRef.value?.focus()
    return null // We're using the focus method directly
  },
})

onMounted(async () => {
  await jobsStore.loadSettings()
  jobsStore.fetchAllJobs()
  jobsStore.startAutoRefresh()
  statsStore.fetchStats()
})

watchEffect(() => {
  const label = companiesStore.selectedCompany?.name ?? 'All Jobs'
  const unseen = companiesStore.selectedCompany
    ? (jobsStore.unseenByCompany.get(companiesStore.selectedCompany.id) ?? 0)
    : jobsStore.unseenTotal
  document.title = unseen > 0 ? `(${unseen}) ${label} | HireWire` : `${label} | HireWire`
})

// Auto-sync when a newly-added company (never scraped) is selected
// Also clear any cached removed company when navigating away
watch(selectedCompany, (company, prev) => {
  if (company?.id !== prev?.id) {
    removedCompany.value = null
  }
  if (company && company.id !== prev?.id && company.last_scraped === null && !isSyncingCompany.value) {
    syncSelectedCompany()
  }
})

// Sync favorites and applied state from all loaded jobs when they change
watch(() => jobsStore.allJobs, (jobs) => {
  favoritesStore.syncFromJobs(jobs)
  applicationsStore.syncFromJobs(jobs)
})

function handleSearch(query: string) {
  jobsStore.setFilters({ q: query })
}

function handleFilterChange(filters: typeof jobsStore.filters) {
  jobsStore.setFilters(filters)
}

function handleClearFilters() {
  jobsStore.clearFilters()
}

function handleSortChange(sortBy: typeof jobsStore.sortBy, sortOrder: typeof jobsStore.sortOrder) {
  jobsStore.setSort(sortBy, sortOrder)
}

async function handleFavorite(jobId: number) {
  try {
    await favoritesStore.toggleFavorite(jobId)
  } catch (e) {
    uiStore.showError('Failed to update favorite')
  }
}

async function handleApply(jobId: number) {
  try {
    await applicationsStore.toggleApplied(jobId)
  } catch {
    uiStore.showError('Failed to update applied status')
  }
}

async function handleMarkUnread(jobId: number) {
  try {
    await viewedStore.markAsUnread(jobId)
  } catch {
    uiStore.showError('Failed to mark as unread')
  }
}

async function handleHide(jobId: number) {
  try {
    const hiddenJob = await jobsStore.hideJob(jobId)
    
    // Show toast with undo option
    uiStore.showWithUndo('Job hidden', async () => {
      try {
        await jobsStore.unhideJob(jobId, hiddenJob || undefined)
        uiStore.showSuccess('Job restored')
      } catch {
        uiStore.showError('Failed to restore job')
      }
    })
  } catch (e) {
    uiStore.showError('Failed to hide job')
  }
}

function handleJobClick(jobId: number) {
  viewedStore.markAsViewed(jobId)
  router.push({ name: 'job-detail', params: { id: jobId } })
}
</script>

<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="dashboard-header">
      <!-- Company management bar (shown when a company is selected, or just removed) -->
      <div v-if="selectedCompany || removedCompany" class="company-bar">
        <!-- Removed state -->
        <template v-if="removedCompany && !selectedCompany">
          <div class="company-bar-name">
            <h2 class="company-bar-title company-bar-title--removed">{{ removedCompany.name }} removed</h2>
          </div>
          <div class="company-bar-actions">
            <button
              class="btn btn-ghost btn-sm btn-restore"
              title="Restore this company"
              @click="restoreCompany"
            >
              ↩ Restore
            </button>
          </div>
        </template>

        <!-- Normal state -->
        <template v-else-if="selectedCompany">
          <!-- Name / inline rename -->
          <div class="company-bar-name">
            <template v-if="isEditingName">
              <input
                v-model="editingName"
                class="company-rename-input"
                @keydown.enter="saveRename"
                @keydown.escape="cancelRename"
                @blur="saveRename"
                autofocus
              />
            </template>
            <template v-else>
              <h2 class="company-bar-title">{{ selectedCompany.name }}</h2>
            </template>

            <!-- Glassdoor rating -->
            <a
              v-if="selectedCompany.glassdoor_url"
              :href="selectedCompany.glassdoor_url"
              class="company-bar-rating"
              target="_blank"
              rel="noopener"
              title="View Glassdoor reviews"
            >
              ★ {{ selectedCompany.glassdoor_rating?.toFixed(1) ?? 'N/A' }}
            </a>
            <span
              v-else-if="selectedCompany.glassdoor_rating"
              class="company-bar-rating"
            >
              ★ {{ selectedCompany.glassdoor_rating.toFixed(1) }}
            </span>
          </div>

          <!-- Actions -->
          <div class="company-bar-actions">
            <button
              v-if="companyUnseenCount > 0"
              class="btn btn-ghost btn-sm"
              title="Mark all jobs as read"
              :disabled="viewedStore.isMarkingAllSeen"
              @click="handleMarkAllRead(selectedCompany.id)"
            >
              ✓ Mark all read
            </button>
            <button
              class="btn btn-ghost btn-sm"
              :class="{ active: isEditingName }"
              title="Rename company"
              @click="startRename"
            >
              ✎ Rename
            </button>
            <button
              class="btn btn-ghost btn-sm sync-btn"
              title="Sync this company"
              :disabled="isSyncingCompany"
              @click="syncSelectedCompany"
            >
              <span class="sync-icon" :class="{ spinning: isSyncingCompany }">↻</span>
              <span>{{ isSyncingCompany ? 'Syncing...' : 'Sync' }}</span>
            </button>
            <button
              class="btn btn-ghost btn-sm btn-danger"
              title="Remove this company"
              :disabled="isDeletingCompany"
              @click="deleteSelectedCompany"
            >
              ✕ Remove
            </button>
          </div>
        </template>
      </div>

      <div class="header-top">
        <h1 v-if="!selectedCompany" class="dashboard-title">All Jobs</h1>
        <div class="dashboard-search">
          <SearchBar 
            ref="searchBarRef"
            :model-value="jobsStore.filters.q"
            @search="handleSearch"
          />
        </div>
        <div class="dashboard-controls">
          <!-- Mark all read (global, only when on All Jobs) -->
          <button
            v-if="!selectedCompany && globalUnseenCount > 0"
            class="btn btn-ghost btn-sm"
            title="Mark all jobs as read"
            :disabled="viewedStore.isMarkingAllSeen"
            @click="handleMarkAllRead()"
          >
            ✓ Mark all read
          </button>
          <SortControls
            :sort-by="jobsStore.sortBy"
            :sort-order="jobsStore.sortOrder"
            @change="handleSortChange"
          />
          <button 
            class="btn btn-ghost filter-toggle"
            :aria-expanded="uiStore.isFilterPanelOpen"
            aria-controls="filter-panel"
            @click="uiStore.toggleFilterPanel()"
          >
            <span class="filter-icon" aria-hidden="true">⚙</span>
            <span class="filter-text">Filters</span>
            <span v-if="jobsStore.activeFilterCount > 0" class="filter-count">
              {{ jobsStore.activeFilterCount }}
            </span>
            <span class="toggle-indicator" :class="{ open: uiStore.isFilterPanelOpen }" aria-hidden="true">
              ▼
            </span>
          </button>
        </div>
      </div>
      
      <!-- Stats Bar -->
      <div class="stats-bar">
        <div class="stats-summary" @click="showStatsDetails = !showStatsDetails">
          <span class="stat-item">
            <span class="stat-value">{{ statsStore.totalJobs.toLocaleString() }}</span>
            <span class="stat-label">jobs</span>
          </span>
          <span class="stat-divider">|</span>
          <span class="stat-item">
            <span class="stat-value">+{{ statsStore.jobsLast24h }}</span>
            <span class="stat-label">today</span>
          </span>
          <span class="stat-divider">|</span>
          <span class="stat-item">
            <span class="stat-label">Updated</span>
            <span class="stat-value">{{ statsStore.lastUpdatedFormatted }}</span>
          </span>
          <button class="stats-toggle" :class="{ expanded: showStatsDetails }">
            {{ showStatsDetails ? '▲' : '▼' }}
          </button>
        </div>
        
        <!-- Stats Details (expandable) -->
        <Transition name="expand">
          <div v-if="showStatsDetails" class="stats-details">
            <div class="stats-section">
              <h4 class="stats-section-title">Jobs by Source</h4>
              <div class="source-list">
                <div 
                  v-for="source in statsStore.jobsBySource" 
                  :key="source.source"
                  class="source-item"
                >
                  <span class="source-name">{{ source.source }}</span>
                  <span class="source-count">{{ source.count.toLocaleString() }}</span>
                </div>
              </div>
            </div>
            <div class="stats-section">
              <h4 class="stats-section-title">Recent Activity</h4>
              <div class="activity-stats">
                <div class="activity-item">
                  <span class="activity-value">{{ statsStore.jobsLast24h }}</span>
                  <span class="activity-label">Last 24h</span>
                </div>
                <div class="activity-item">
                  <span class="activity-value">{{ statsStore.jobsLast7d }}</span>
                  <span class="activity-label">Last 7d</span>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </header>
    
    <!-- Main content -->
    <div class="dashboard-content">
      <!-- Job List -->
      <main class="dashboard-main">
        <JobList
          :jobs="jobsStore.filteredJobs"
          :loading="jobsStore.isLoading"
          :total="jobsStore.total"
          :total-unfiltered="jobsStore.allJobs.length"
          :selected-job-id="selectedJobId"
          :is-viewed="viewedStore.isViewed"
          :has-company="companiesStore.selectedCompanyId !== null || companiesStore.companies.length > 0"
          :has-filters="jobsStore.activeFilterCount > 0"
          @favorite="handleFavorite"
          @hide="handleHide"
          @apply="handleApply"
          @mark-unread="handleMarkUnread"
          @job-click="handleJobClick"
        />
      </main>
      
      <!-- Filter Panel (right side) -->
      <Transition name="slide">
        <FilterPanel
          v-if="uiStore.isFilterPanelOpen"
          id="filter-panel"
          :model-value="jobsStore.filters"
          @update:model-value="handleFilterChange"
          @clear="handleClearFilters"
        />
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.dashboard-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--bg-primary);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* Company management bar */
.company-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.company-bar-name {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.company-bar-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.company-rename-input {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-tertiary);
  border: 1px solid var(--accent-primary);
  border-radius: var(--radius-sm);
  padding: 2px var(--space-2);
  outline: none;
  width: 260px;
}

.company-bar-rating {
  font-size: var(--text-sm);
  font-weight: 600;
  color: #d4900a;
  flex-shrink: 0;
  text-decoration: none;
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}

a.company-bar-rating:hover {
  background: rgba(212, 144, 10, 0.1);
  text-decoration: underline;
}

.company-bar-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.btn-danger {
  color: var(--accent-error, #ef4444);
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: var(--accent-error, #ef4444);
}

.btn-restore {
  color: #22c55e;
}

.btn-restore:hover {
  background: rgba(34, 197, 94, 0.1);
  border-color: #22c55e;
}

.company-bar-title--removed {
  color: var(--text-muted);
  font-style: italic;
}

.sync-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  transition: color var(--transition-fast);
}

.sync-btn .sync-icon {
  display: inline-block;
  font-size: 1rem;
}

.sync-btn .sync-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.header-top {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.dashboard-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.dashboard-search {
  flex: 1;
  min-width: 280px;
  max-width: 500px;
}

.dashboard-controls {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-left: auto;
}

.filter-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-tertiary);
  transition: all var(--transition-fast);
}

.filter-toggle:hover {
  border-color: var(--border-focus);
  background: var(--bg-hover);
}

.filter-toggle:focus-visible {
  outline: 2px solid var(--accent-primary);
  outline-offset: 2px;
}

.filter-icon {
  font-size: var(--text-base);
}

.filter-text {
  font-weight: 500;
}

.filter-count {
  background: var(--accent-primary);
  color: white;
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}

.toggle-indicator {
  font-size: var(--text-xs);
  color: var(--text-muted);
  transition: transform var(--transition-fast);
}

.toggle-indicator.open {
  transform: rotate(180deg);
}

/* Stats Bar */
.stats-bar {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
}

.stats-summary {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  cursor: pointer;
  user-select: none;
}

.stat-item {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
}

.stat-value {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.stat-divider {
  color: var(--border-color);
}

.stats-toggle {
  margin-left: auto;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: var(--space-1);
  font-size: var(--text-xs);
  transition: transform var(--transition-fast);
}

.stats-toggle.expanded {
  transform: rotate(180deg);
}

.stats-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  padding-top: var(--space-3);
  margin-top: var(--space-3);
  border-top: 1px solid var(--border-color);
}

.stats-section-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 var(--space-2) 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.source-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--text-sm);
}

.source-name {
  color: var(--text-secondary);
  text-transform: capitalize;
}

.source-count {
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.activity-stats {
  display: flex;
  gap: var(--space-4);
}

.activity-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.activity-value {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.activity-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

/* Expand transition */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  margin-top: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 200px;
}

.dashboard-content {
  display: flex;
  flex: 1;
  min-height: 0; /* Allow flex shrinking */
}

.dashboard-main {
  flex: 1;
  padding: var(--space-5);
  min-width: 0; /* Prevent content overflow */
}

.dashboard-content > :deep(.filter-panel) {
  position: sticky;
  top: 140px; /* Below sticky header */
  width: 210px;
  min-width: 210px;
  max-height: calc(100vh - 160px);
  overflow-y: auto;
  border-left: 1px solid var(--border-color);
  border-right: none;
  border-radius: 0;
  align-self: flex-start;
}

/* Slide transition for filter panel (from right) */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
