<script setup lang="ts">
/**
 * DashboardView - Main job listing page
 */
import { onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useJobsStore } from '@/stores/jobs'
import { useFavoritesStore } from '@/stores/favorites'
import { useUIStore } from '@/stores/ui'
import SearchBar from '@/components/SearchBar.vue'
import FilterPanel from '@/components/FilterPanel.vue'
import SortControls from '@/components/SortControls.vue'
import JobList from '@/components/JobList.vue'

const router = useRouter()
const jobsStore = useJobsStore()
const favoritesStore = useFavoritesStore()
const uiStore = useUIStore()

onMounted(() => {
  jobsStore.fetchJobs()
  jobsStore.startAutoRefresh()
})

// Sync favorites from jobs when they change
watch(() => jobsStore.jobs, (jobs) => {
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

function handlePageChange(page: number) {
  jobsStore.goToPage(page)
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
    await jobsStore.hideJob(jobId)
    uiStore.showSuccess('Job hidden')
  } catch (e) {
    uiStore.showError('Failed to hide job')
  }
}

function handleJobClick(jobId: number) {
  router.push({ name: 'job-detail', params: { id: jobId } })
}
</script>

<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="dashboard-header">
      <h1 class="dashboard-title">Job Search</h1>
      <div class="dashboard-search">
        <SearchBar 
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
          @click="uiStore.toggleFilterPanel()"
        >
          {{ uiStore.isFilterPanelOpen ? '◀ Hide Filters' : '▶ Show Filters' }}
          <span v-if="jobsStore.activeFilterCount > 0" class="filter-count">
            {{ jobsStore.activeFilterCount }}
          </span>
        </button>
      </div>
    </header>
    
    <!-- Main content -->
    <div class="dashboard-content">
      <!-- Filter Panel -->
      <Transition name="slide">
        <FilterPanel
          v-if="uiStore.isFilterPanelOpen"
          :model-value="jobsStore.filters"
          @update:model-value="handleFilterChange"
          @clear="handleClearFilters"
        />
      </Transition>
      
      <!-- Job List -->
      <main class="dashboard-main">
        <JobList
          :jobs="jobsStore.jobs"
          :loading="jobsStore.isLoading"
          :total="jobsStore.total"
          :page="jobsStore.page"
          :total-pages="jobsStore.totalPages"
          @page-change="handlePageChange"
          @favorite="handleFavorite"
          @hide="handleHide"
          @job-click="handleJobClick"
        />
      </main>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.dashboard-header {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-color);
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
}

.filter-count {
  background: var(--accent-primary);
  color: white;
  font-size: var(--text-xs);
  padding: 2px 6px;
  border-radius: 10px;
}

.dashboard-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.dashboard-content > :deep(.filter-panel) {
  width: 280px;
  min-width: 280px;
  height: calc(100vh - 73px);
  overflow-y: auto;
  border-right: 1px solid var(--border-color);
  border-radius: 0;
}

.dashboard-main {
  flex: 1;
  padding: var(--space-5);
  overflow-y: auto;
}

/* Slide transition for filter panel */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(-100%);
  opacity: 0;
}
</style>
