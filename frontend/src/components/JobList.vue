<script setup lang="ts">
/**
 * JobList - Renders filtered jobs with IntersectionObserver-based windowed rendering.
 * Instead of mounting all DOM nodes at once, it starts with INITIAL_BATCH items and
 * appends LOAD_MORE_BATCH more whenever the sentinel at the bottom enters the viewport.
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import type { JobWithDescription } from '@/types/api'
import JobCard from './JobCard.vue'
import JobCardSkeleton from './JobCardSkeleton.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const INITIAL_BATCH = 50
const LOAD_MORE_BATCH = 50

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

const props = withDefaults(defineProps<Props>(), {
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

const visibleCount = ref(INITIAL_BATCH)
const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

const visibleJobs = computed(() => props.jobs.slice(0, visibleCount.value))
const hasMore = computed(() => visibleCount.value < props.jobs.length)

// Reset visible count whenever the job list changes (filter/sort applied)
watch(() => props.jobs, () => {
  visibleCount.value = INITIAL_BATCH
}, { flush: 'sync' })

function setupObserver() {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value) {
        visibleCount.value = Math.min(
          visibleCount.value + LOAD_MORE_BATCH,
          props.jobs.length,
        )
      }
    },
    { rootMargin: '300px' },
  )
  if (sentinelRef.value) observer.observe(sentinelRef.value)
}

onMounted(setupObserver)
onUnmounted(() => observer?.disconnect())

// Re-attach observer after sentinel mounts / unmounts with list changes
watch(sentinelRef, (el) => {
  if (el && observer) observer.observe(el)
})
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

    <!-- Job cards (windowed) -->
    <div v-else-if="jobs.length > 0" class="job-list-items">
      <JobCard
        v-for="job in visibleJobs"
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
      <!-- Sentinel: loading more or end of list -->
      <div ref="sentinelRef" class="load-more-sentinel">
        <span v-if="hasMore" class="load-more-hint">Loading more…</span>
      </div>
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

.load-more-sentinel {
  height: 1px;
  width: 100%;
}

.load-more-hint {
  display: block;
  text-align: center;
  font-size: var(--text-sm);
  color: var(--text-muted);
  padding: var(--space-3) 0;
  height: auto;
}
</style>
