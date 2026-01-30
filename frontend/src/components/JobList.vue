<script setup lang="ts">
/**
 * JobList - Container for job cards with pagination
 */
import type { Job } from '@/types/api'
import JobCard from './JobCard.vue'
import JobCardSkeleton from './JobCardSkeleton.vue'
import PaginationControls from '@/components/common/PaginationControls.vue'
import EmptyState from '@/components/common/EmptyState.vue'

interface Props {
  jobs: Job[]
  loading?: boolean
  total?: number
  page?: number
  totalPages?: number
  selectedJobId?: number | null
  isViewed?: (jobId: number) => boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  total: 0,
  page: 1,
  totalPages: 1,
  selectedJobId: null,
  isViewed: () => false,
})

const emit = defineEmits<{
  'page-change': [page: number]
  favorite: [jobId: number]
  hide: [jobId: number]
  'job-click': [jobId: number]
}>()
</script>

<template>
  <div class="job-list">
    <!-- Header with count -->
    <div class="job-list-header">
      <span class="job-count">
        {{ total.toLocaleString() }} jobs found
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
        @click="emit('job-click', $event)"
      />
    </div>
    
    <!-- Empty state -->
    <EmptyState
      v-else
      icon="🔍"
      title="No jobs found"
      description="Try adjusting your filters or search terms"
    />
    
    <!-- Pagination -->
    <PaginationControls
      v-if="totalPages > 1 && !loading"
      :page="page"
      :total-pages="totalPages"
      @change="emit('page-change', $event)"
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

.job-list-items {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
