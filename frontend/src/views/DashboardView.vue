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
import { onMounted, watch, watchEffect, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useJobsStore } from '@/stores/jobs'
import { useFavoritesStore } from '@/stores/favorites'
import { useUIStore } from '@/stores/ui'
import { useStatsStore } from '@/stores/stats'
import { useViewedStore } from '@/stores/viewed'
import { useCompaniesStore } from '@/stores/companies'
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

const showStatsDetails = ref(false)
const searchBarRef = ref<{ focus: () => void } | null>(null)

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

onMounted(() => {
  jobsStore.fetchAllJobs()
  jobsStore.startAutoRefresh()
  statsStore.fetchStats()
})

watchEffect(() => {
  const label = companiesStore.selectedCompany?.name ?? 'All Jobs'
  const count = jobsStore.total
  document.title = count > 0 ? `(${count}) ${label} | HireWire` : `${label} | HireWire`
})

// Sync favorites from all loaded jobs when they change
watch(() => jobsStore.allJobs, (jobs) => {
  favoritesStore.syncFromJobs(jobs)
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
      <div class="header-top">
        <h1 class="dashboard-title">
          <span v-if="companiesStore.selectedCompany">
            {{ companiesStore.selectedCompany.name }}
          </span>
          <span v-else>All Jobs</span>
        </h1>
        <div class="dashboard-search">
          <SearchBar 
            ref="searchBarRef"
            :model-value="jobsStore.filters.q"
            @search="handleSearch"
          />
        </div>
        <div class="dashboard-controls">
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
          :selected-job-id="selectedJobId"
          :is-viewed="viewedStore.isViewed"
          :has-company="companiesStore.selectedCompanyId !== null || companiesStore.companies.length > 0"
          :has-filters="jobsStore.activeFilterCount > 0"
          @favorite="handleFavorite"
          @hide="handleHide"
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
  width: 280px;
  min-width: 280px;
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
