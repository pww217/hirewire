<script setup lang="ts">
/**
 * Main application component
 * Layout: Sidebar + Main content area
 */
import { ref, onUnmounted } from 'vue'
import { useJobsStore } from '@/stores/jobs'
import Sidebar from '@/components/Sidebar.vue'
import AddCompanyModal from '@/components/AddCompanyModal.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'

const jobsStore = useJobsStore()

const showAddCompany = ref(false)

onUnmounted(() => jobsStore.stopAutoRefresh())
</script>

<template>
  <div class="app-container">
    <Sidebar @open-add-company="showAddCompany = true" />
    <main class="main-content">
      <RouterView />
    </main>
    <ToastContainer />
    <AddCompanyModal
      v-if="showAddCompany"
      @close="showAddCompany = false"
      @created="showAddCompany = false"
    />
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
