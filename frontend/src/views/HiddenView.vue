<script setup lang="ts">
/**
 * HiddenView - Display hidden jobs with ability to unhide
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useJobsStore } from '@/stores/jobs'
import { useUIStore } from '@/stores/ui'
import { useViewedStore } from '@/stores/viewed'
import type { JobWithDescription, JobListResponse } from '@/types/api'
import { useApi } from '@/composables/useApi'
import JobList from '@/components/JobList.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const router = useRouter()
const jobsStore = useJobsStore()
const uiStore = useUIStore()
const viewedStore = useViewedStore()
const api = useApi()

const hiddenJobs = ref<JobWithDescription[]>([])
const isLoading = ref(false)
const total = ref(0)

async function fetchHidden() {
  isLoading.value = true
  try {
    const response = await api.get<JobListResponse>('/api/jobs', {
      hidden_only: true,
      include_hidden: true,
      per_page: 100,
    })
    hiddenJobs.value = response.jobs
    total.value = response.total
  } catch {
    uiStore.showError('Failed to load hidden jobs')
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchHidden)

async function handleHide(jobId: number) {
  // In hidden view, "hide" action = unhide
  try {
    await jobsStore.unhideJob(jobId)
    hiddenJobs.value = hiddenJobs.value.filter((j) => j.id !== jobId)
    total.value = Math.max(0, total.value - 1)
    uiStore.showSuccess('Job restored')
  } catch {
    uiStore.showError('Failed to restore job')
  }
}

function handleJobClick(jobId: number) {
  viewedStore.markAsViewed(jobId)
  router.push({ name: 'job-detail', params: { id: jobId } })
}
</script>

<template>
  <div class="hidden-view">
    <header class="hidden-header">
      <h1 class="hidden-title">Hidden</h1>
      <span class="hidden-count">{{ total }} jobs</span>
    </header>

    <main class="hidden-content">
      <LoadingSpinner v-if="isLoading" size="lg" />

      <EmptyState
        v-else-if="hiddenJobs.length === 0"
        icon="👁"
        title="No hidden jobs"
        description="Jobs you hide will appear here"
      >
        <RouterLink to="/" class="btn btn-primary">Browse Jobs</RouterLink>
      </EmptyState>

      <div v-else>
        <p class="hidden-hint">Click × on a job to restore it</p>
        <JobList
          :jobs="hiddenJobs"
          :total="total"
          :is-viewed="() => true"
          @hide="handleHide"
          @job-click="handleJobClick"
        />
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
  align-items: center;
  gap: var(--space-3);
}

.hidden-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.hidden-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.hidden-content {
  flex: 1;
  padding: var(--space-5);
  overflow-y: auto;
}

.hidden-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-bottom: var(--space-4);
}

.btn {
  margin-top: var(--space-4);
  text-decoration: none;
}
</style>
