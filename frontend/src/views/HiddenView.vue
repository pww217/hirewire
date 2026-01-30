<script setup lang="ts">
/**
 * HiddenView - Manage hidden jobs
 */
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Job, JobListResponse } from '@/types/api'
import { useApi } from '@/composables/useApi'
import { useUIStore } from '@/stores/ui'
import { useJobsStore } from '@/stores/jobs'
import JobCard from '@/components/JobCard.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const router = useRouter()
const api = useApi()
const uiStore = useUIStore()
const jobsStore = useJobsStore()

const hiddenJobs = ref<Job[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

const hiddenCount = computed(() => hiddenJobs.value.length)

onMounted(async () => {
  await fetchHiddenJobs()
})

async function fetchHiddenJobs() {
  isLoading.value = true
  error.value = null

  try {
    const response = await api.get<JobListResponse>('/api/jobs', {
      include_hidden: true,
      per_page: 100,
    })
    // Filter to only hidden jobs
    // The API returns all jobs when include_hidden is true
    // We need to filter client-side for is_hidden = true
    hiddenJobs.value = response.jobs.filter(job => job.is_hidden)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load hidden jobs'
    console.error('Failed to fetch hidden jobs:', e)
  } finally {
    isLoading.value = false
  }
}

async function unhideJob(jobId: number) {
  try {
    await api.delete(`/api/jobs/${jobId}/hide`)
    hiddenJobs.value = hiddenJobs.value.filter(j => j.id !== jobId)
    uiStore.showSuccess('Job unhidden')
    // Refresh main job list
    jobsStore.fetchJobs()
  } catch (e) {
    uiStore.showError('Failed to unhide job')
  }
}

async function unhideAll() {
  if (!confirm(`Unhide all ${hiddenCount.value} jobs?`)) {
    return
  }

  try {
    // Unhide each job
    for (const job of hiddenJobs.value) {
      await api.delete(`/api/jobs/${job.id}/hide`)
    }
    hiddenJobs.value = []
    uiStore.showSuccess('All jobs unhidden')
    jobsStore.fetchJobs()
  } catch (e) {
    uiStore.showError('Failed to unhide all jobs')
    // Refresh to get accurate state
    await fetchHiddenJobs()
  }
}

function handleJobClick(jobId: number) {
  router.push({ name: 'job-detail', params: { id: jobId } })
}
</script>

<template>
  <div class="hidden-view">
    <header class="hidden-header">
      <div class="header-content">
        <h1 class="hidden-title">Hidden Jobs</h1>
        <p class="hidden-subtitle">{{ hiddenCount }} job{{ hiddenCount !== 1 ? 's' : '' }} hidden</p>
      </div>
      <button 
        v-if="hiddenCount > 0"
        class="btn btn-secondary"
        @click="unhideAll"
      >
        Unhide All
      </button>
    </header>
    
    <main class="hidden-content">
      <!-- Loading state -->
      <div v-if="isLoading" class="loading-state">
        <LoadingSpinner />
        <p>Loading hidden jobs...</p>
      </div>
      
      <!-- Error state -->
      <div v-else-if="error" class="error-state">
        <p>{{ error }}</p>
        <button class="btn btn-primary" @click="fetchHiddenJobs">
          Retry
        </button>
      </div>
      
      <!-- Empty state -->
      <EmptyState 
        v-else-if="hiddenJobs.length === 0"
        icon="👁️"
        title="No Hidden Jobs"
        description="Jobs you hide will appear here. You can unhide them at any time."
      />
      
      <!-- Hidden jobs list -->
      <div v-else class="hidden-jobs-list">
        <div 
          v-for="job in hiddenJobs" 
          :key="job.id"
          class="hidden-job-item"
        >
          <div class="job-card-wrapper" @click="handleJobClick(job.id)">
            <div class="job-info">
              <h3 class="job-title">{{ job.title }}</h3>
              <p class="job-company">{{ job.company }}</p>
              <p class="job-location">{{ job.location_raw || 'Location not specified' }}</p>
            </div>
          </div>
          <button 
            class="btn btn-outline unhide-btn"
            @click.stop="unhideJob(job.id)"
          >
            Unhide
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.hidden-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.hidden-header {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.hidden-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.hidden-subtitle {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin: 0;
}

.hidden-content {
  flex: 1;
  padding: var(--space-5);
  overflow-y: auto;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  padding: var(--space-8);
  color: var(--text-muted);
}

.hidden-jobs-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.hidden-job-item {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.hidden-job-item:hover {
  border-color: var(--border-focus);
}

.job-card-wrapper {
  flex: 1;
  cursor: pointer;
}

.job-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.job-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.job-company {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: 0;
}

.job-location {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin: 0;
}

.unhide-btn {
  flex-shrink: 0;
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

.btn-primary {
  background: var(--accent-primary);
  color: white;
}

.btn-primary:hover {
  background: var(--accent-primary-hover, #2563eb);
}

.btn-secondary {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background: var(--bg-hover);
}

.btn-outline {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.btn-outline:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
</style>
