<script setup lang="ts">
/**
 * Main application component
 * Layout: Sidebar + Main content area
 */
import { onMounted, onUnmounted } from 'vue'
import { useJobsStore } from '@/stores/jobs'
import { useSettingsStore } from '@/stores/settings'
import Sidebar from '@/components/Sidebar.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'

const jobsStore = useJobsStore()
const settingsStore = useSettingsStore()

onMounted(async () => {
  // Load user settings so exclusions are available for job fetching
  await settingsStore.fetchSettings()
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
  /* Allow content to scroll naturally - no overflow:hidden to avoid nested scroll issues */
  min-width: 0; /* Prevent flex item overflow */
}
</style>
