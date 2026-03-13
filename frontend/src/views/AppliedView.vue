<script setup lang="ts">
/**
 * AppliedView - Display jobs marked as applied
 */
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import { useUIStore } from '@/stores/ui'
import { useViewedStore } from '@/stores/viewed'
import JobList from '@/components/JobList.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const router = useRouter()
const applicationsStore = useApplicationsStore()
const uiStore = useUIStore()
const viewedStore = useViewedStore()

onMounted(() => {
  applicationsStore.fetchApplied()
})

async function handleApply(jobId: number) {
  try {
    await applicationsStore.unmarkApplied(jobId)
    uiStore.showSuccess('Removed from applied')
  } catch {
    uiStore.showError('Failed to update applied status')
  }
}

function handleJobClick(jobId: number) {
  viewedStore.markAsViewed(jobId)
  router.push({ name: 'job-detail', params: { id: jobId } })
}
</script>

<template>
  <div class="applied-view">
    <header class="applied-header">
      <h1 class="applied-title">Applied</h1>
      <span class="applied-count">{{ applicationsStore.appliedCount }} jobs</span>
    </header>

    <main class="applied-content">
      <LoadingSpinner v-if="applicationsStore.isLoading" size="lg" />

      <EmptyState
        v-else-if="applicationsStore.appliedJobs.length === 0"
        icon="✅"
        title="No applied jobs yet"
        description="Mark jobs as applied using the ○ button on any job card"
      >
        <RouterLink to="/" class="btn btn-primary">Browse Jobs</RouterLink>
      </EmptyState>

      <JobList
        v-else
        :jobs="applicationsStore.appliedJobs"
        :total="applicationsStore.appliedCount"
        @apply="handleApply"
        @job-click="handleJobClick"
      />
    </main>
  </div>
</template>

<style scoped>
.applied-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.applied-header {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.applied-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.applied-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.applied-content {
  flex: 1;
  padding: var(--space-5);
  overflow-y: auto;
}

.btn {
  margin-top: var(--space-4);
  text-decoration: none;
}
</style>
