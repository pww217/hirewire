<script setup lang="ts">
/**
 * JobDetailView - Job detail page wrapper
 */
import JobDetail from '@/components/JobDetail.vue'

interface Props {
  jobId: number
}

defineProps<Props>()
</script>

<template>
  <div class="job-detail-view">
    <JobDetail :job-id="jobId" />
  </div>
</template>

<style scoped>
.job-detail-view {
  height: 100%;
  overflow-y: auto;
}
</style>
