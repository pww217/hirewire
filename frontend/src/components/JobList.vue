<script setup lang="ts">
/**
 * JobList - Renders all filtered jobs (no pagination — all jobs loaded client-side)
 */
import type { JobWithDescription } from '@/types/api'
import JobCard from './JobCard.vue'
import JobCardSkeleton from './JobCardSkeleton.vue'
import EmptyState from '@/components/common/EmptyState.vue'

interface Props {
  jobs: JobWithDescription[]
  loading?: boolean
  total?: number
  totalUnfiltered?: number
  selectedJobId?: number | null
  isViewed?: (jobId: number) => boolean
  hasCompany?: boolean
  hasFilters?: boolean
}

withDefaults(defineProps<Props>(), {
  loading: false,
  total: 0,
  totalUnfiltered: 0,
  selectedJobId: null,
  isViewed: () => false,
  hasCompany: false,
  hasFilters: false,
})

const emit = defineEmits<{
  favorite: [jobId: number]
  hide: [jobId: number]
  apply: [jobId: number]
  'mark-unread': [jobId: number]
  'job-click': [jobId: number]
}>()
</script>

<template>
  <div class="job-list">
    <!-- Header with count -->
    <div class="job-list-header">
      <span class="job-count">
        <template v-if="totalUnfiltered > total && totalUnfiltered > 0">
          {{ total.toLocaleString() }} {{ total === 1 ? 'job' : 'jobs' }} filtered
          <span class="job-count-total">({{ totalUnfiltered.toLocaleString() }} total)</span>
        </template>
        <template v-else>
          {{ total.toLocaleString() }} {{ total === 1 ? 'job' : 'jobs' }}
        </template>
      </span>
    </div>

    <!-- Loading skeletons -->
    <div v-if="loading && jobs.length === 0" class="job-list-items">
      <JobCardSkeleton v-for="i in 5" :key="i" />
    </div>

    <!-- Job cards -->
    <div v-else-if="jobs.length > 0" class="job-list-items">
      <JobCard
        v-for="job in jobs"
        :key="job.id"
        :job="job"
        :is-selected="job.id === selectedJobId"
        :is-viewed="isViewed(job.id)"
        @favorite="emit('favorite', $event)"
        @hide="emit('hide', $event)"
        @apply="emit('apply', $event)"
        @mark-unread="emit('mark-unread', $event)"
        @click="emit('job-click', $event)"
      />
    </div>

    <!-- Empty states -->
    <EmptyState
      v-else-if="hasFilters"
      icon="🔍"
      title="No matching jobs"
      description="Try adjusting your filters or search terms"
    />
    <EmptyState
      v-else-if="hasCompany"
      icon="⏳"
      title="No jobs yet"
      description="Hit the sync button to pull the latest listings"
    />
    <EmptyState
      v-else
      icon="🏢"
      title="No companies tracked"
      description="Add a company from the sidebar to get started"
    />
  </div>
</template>

<style scoped>
.job-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.job-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.job-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.job-count-total {
  color: var(--text-muted);
  opacity: 0.7;
}

.job-list-items {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
