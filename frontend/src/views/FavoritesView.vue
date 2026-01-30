<script setup lang="ts">
/**
 * FavoritesView - Display favorited jobs
 */
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useFavoritesStore } from '@/stores/favorites'
import { useUIStore } from '@/stores/ui'
import JobList from '@/components/JobList.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const router = useRouter()
const favoritesStore = useFavoritesStore()
const uiStore = useUIStore()

onMounted(() => {
  favoritesStore.fetchFavorites()
})

async function handleFavorite(jobId: number) {
  try {
    await favoritesStore.removeFavorite(jobId)
    uiStore.showSuccess('Removed from favorites')
  } catch (e) {
    uiStore.showError('Failed to remove from favorites')
  }
}

function handleJobClick(jobId: number) {
  router.push({ name: 'job-detail', params: { id: jobId } })
}
</script>

<template>
  <div class="favorites-view">
    <header class="favorites-header">
      <h1 class="favorites-title">Favorites</h1>
      <span class="favorites-count">
        {{ favoritesStore.favoriteCount }} saved jobs
      </span>
    </header>
    
    <main class="favorites-content">
      <!-- Loading -->
      <LoadingSpinner v-if="favoritesStore.isLoading" size="lg" />
      
      <!-- Empty State -->
      <EmptyState
        v-else-if="favoritesStore.favorites.length === 0"
        icon="⭐"
        title="No favorites yet"
        description="Jobs you save will appear here for easy access"
      >
        <RouterLink to="/" class="btn btn-primary">
          Browse Jobs
        </RouterLink>
      </EmptyState>
      
      <!-- Favorites List -->
      <JobList
        v-else
        :jobs="favoritesStore.favorites"
        :total="favoritesStore.favoriteCount"
        :total-pages="1"
        @favorite="handleFavorite"
        @job-click="handleJobClick"
      />
    </main>
  </div>
</template>

<style scoped>
.favorites-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.favorites-header {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.favorites-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.favorites-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.favorites-content {
  flex: 1;
  padding: var(--space-5);
  overflow-y: auto;
}

.btn {
  margin-top: var(--space-4);
  text-decoration: none;
}
</style>
