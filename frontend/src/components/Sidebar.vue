<script setup lang="ts">
/**
 * Sidebar - Main navigation sidebar
 */
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useJobsStore } from '@/stores/jobs'
import { useFavoritesStore } from '@/stores/favorites'
import { useUIStore } from '@/stores/ui'
import { useApi } from '@/composables/useApi'

const route = useRoute()
const jobsStore = useJobsStore()
const favoritesStore = useFavoritesStore()
const uiStore = useUIStore()
const api = useApi()

const isSyncing = ref(false)

interface NavItem {
  path: string
  icon: string
  label: string
  name: string
  badge?: number
}

const navItems = computed<NavItem[]>(() => [
  { path: '/', icon: '📋', label: 'Dashboard', name: 'dashboard' },
  { 
    path: '/favorites', 
    icon: '⭐', 
    label: 'Favorites', 
    name: 'favorites',
    badge: favoritesStore.favoriteCount
  },
  { path: '/hidden', icon: '👁️', label: 'Hidden', name: 'hidden' },
  { path: '/settings', icon: '⚙️', label: 'Settings', name: 'settings' },
])

interface SyncSiteResult {
  site: string
  success: boolean
  count: number
  error: string | null
}

interface SyncResponse {
  status: string
  message: string
  new_jobs: number
  updated_jobs: number
  duration_ms: number
  site_results: SyncSiteResult[]
}

async function syncJobs() {
  if (isSyncing.value) return
  
  isSyncing.value = true
  try {
    const response = await api.post<SyncResponse>('/api/sync')
    
    if (!response) {
      uiStore.showError('No response from server')
      return
    }

    // Refresh job list after sync
    jobsStore.fetchJobs()

    // Handle different response statuses
    if (response.status === 'success') {
      const jobText = response.new_jobs === 1 ? 'job' : 'jobs'
      uiStore.showSuccess(`Synced ${response.new_jobs} new ${jobText}`)
    } else if (response.status === 'partial') {
      // Some sites failed - show warning with details
      const failures = response.site_results.filter(s => !s.success)
      const failedSites = failures.map(f => f.site).join(', ')
      uiStore.showWarning(`Sync completed but ${failedSites} failed`)
    } else {
      // Full failure
      uiStore.showError(response.message || 'Sync failed')
    }
  } catch (e) {
    uiStore.showError('Failed to sync jobs')
  } finally {
    isSyncing.value = false
  }
}
</script>

<template>
  <nav class="sidebar">
    <div class="sidebar-header">
      <RouterLink to="/" class="sidebar-brand">
        <span class="sidebar-logo">💼</span>
        <span class="sidebar-title">HireWire</span>
      </RouterLink>
    </div>
    
    <div class="sidebar-nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-link"
        :class="{ active: route.name === item.name }"
      >
        <span class="nav-link-icon">{{ item.icon }}</span>
        <span class="nav-link-label">{{ item.label }}</span>
        
        <!-- Badge for favorites count -->
        <span 
          v-if="item.badge && item.badge > 0"
          class="nav-link-badge"
        >
          {{ item.badge }}
        </span>
      </RouterLink>
    </div>
    
    <!-- Stats -->
    <div class="sidebar-stats">
      <div class="stat">
        <span class="stat-value">{{ jobsStore.total.toLocaleString() }}</span>
        <span class="stat-label">Total Jobs</span>
      </div>
      <div class="stat">
        <span class="stat-value">{{ favoritesStore.favoriteCount }}</span>
        <span class="stat-label">Favorites</span>
      </div>
    </div>
    
    <!-- Sync button -->
    <div class="sidebar-sync">
      <button 
        class="sync-btn"
        :class="{ syncing: isSyncing }"
        :disabled="isSyncing"
        @click="syncJobs"
      >
        <span class="sync-icon" :class="{ spinning: isSyncing }">🔄</span>
        <span class="sync-text">{{ isSyncing ? 'Syncing...' : 'Sync Jobs' }}</span>
      </button>
    </div>
    
    <!-- Auto-refresh status -->
    <div class="sidebar-footer">
      <div class="refresh-status">
        <span class="refresh-indicator" :class="{ active: jobsStore.autoRefreshEnabled }"></span>
        <span class="refresh-text">
          {{ jobsStore.autoRefreshEnabled ? 'Auto-refresh on' : 'Auto-refresh off' }}
        </span>
      </div>
      <button 
        class="refresh-toggle"
        @click="jobsStore.toggleAutoRefresh()"
      >
        {{ jobsStore.autoRefreshEnabled ? 'Pause' : 'Resume' }}
      </button>
    </div>
  </nav>
</template>

<style scoped>
.sidebar {
  width: 240px;
  min-width: 240px;
  height: 100vh;
  position: sticky;
  top: 0;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  flex-shrink: 0; /* Prevent sidebar from shrinking */
}

.sidebar-header {
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-color);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  text-decoration: none;
}

.sidebar-logo {
  font-size: var(--text-2xl);
}

.sidebar-title {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
}

.sidebar-nav {
  flex: 1;
  padding: var(--space-3);
  overflow-y: auto;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
  transition: all var(--transition-fast);
  margin-bottom: var(--space-1);
}

.nav-link:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-link.active {
  background: var(--bg-active);
  color: var(--accent-primary);
}

.nav-link-icon {
  font-size: var(--text-xl);
  width: 24px;
  text-align: center;
  flex-shrink: 0;
}

.nav-link-label {
  flex: 1;
}

.nav-link-badge {
  padding: 2px 8px;
  background: var(--accent-primary);
  color: white;
  font-size: var(--text-xs);
  font-weight: 600;
  border-radius: 10px;
}

.sidebar-stats {
  padding: var(--space-4);
  border-top: 1px solid var(--border-color);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.sidebar-sync {
  padding: var(--space-3);
  border-top: 1px solid var(--border-color);
}

.sync-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.sync-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--border-focus);
}

.sync-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.sync-btn.syncing {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: white;
}

.sync-icon {
  font-size: var(--text-base);
}

.sync-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.stat {
  text-align: center;
}

.stat-value {
  display: block;
  font-family: var(--font-mono);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sidebar-footer {
  padding: var(--space-3);
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.refresh-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.refresh-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}

.refresh-indicator.active {
  background: var(--accent-success);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.refresh-text {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.refresh-toggle {
  padding: var(--space-1) var(--space-2);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.refresh-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
</style>
