<script setup lang="ts">
/**
 * Main application component
 * Layout: Sidebar + Main content area
 */
import { onMounted, onUnmounted } from 'vue'
import { useJobsStore } from '@/stores/jobs'
import Sidebar from '@/components/Sidebar.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'

const jobsStore = useJobsStore()

onMounted(() => {
  // Initial fetch is handled by each view
})

onUnmounted(() => {
  jobsStore.stopAutoRefresh()
})
</script>

<template>
  <div class="app-container">
    <Sidebar />
    <main class="main-content">
      <RouterView />
    </main>
    <ToastContainer />
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  min-height: 100vh;
  background: var(--bg-primary);
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
