<script setup lang="ts">
/**
 * JobCard - Displays a single job listing
 */
import { computed, withDefaults } from 'vue'
import type { JobWithDescription } from '@/types/api'
import { useFavoritesStore } from '@/stores/favorites'
import BaseBadge from '@/components/common/BaseBadge.vue'

interface Props {
  job: JobWithDescription
  isSelected?: boolean
  isViewed?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isSelected: false,
  isViewed: false,
})

const emit = defineEmits<{
  favorite: [jobId: number]
  hide: [jobId: number]
  click: [jobId: number]
}>()

const favoritesStore = useFavoritesStore()

// Computed
const isFavorite = computed(() => favoritesStore.isFavorite(props.job.id))

const formattedSalary = computed(() => {
  const { salary_min, salary_max, salary_interval } = props.job
  if (!salary_min && !salary_max) return null
  
  const formatNum = (n: number) => {
    if (n >= 1000) return `$${Math.round(n / 1000)}K`
    return `$${n}`
  }
  
  let salary = ''
  if (salary_min && salary_max) {
    salary = `${formatNum(salary_min)} - ${formatNum(salary_max)}`
  } else if (salary_min) {
    salary = `${formatNum(salary_min)}+`
  } else if (salary_max) {
    salary = `Up to ${formatNum(salary_max)}`
  }
  
  if (salary_interval) {
    const intervals: Record<string, string> = {
      yearly: '/yr',
      monthly: '/mo',
      hourly: '/hr',
    }
    salary += intervals[salary_interval] || ''
  }
  
  return salary
})

const postedDate = computed(() => {
  if (!props.job.date_posted) return 'Recently'

  const diffDays = (Date.now() - new Date(props.job.date_posted).getTime()) / 86_400_000

  if (diffDays < 1) return 'Today'
  if (diffDays < 2) return 'Yesterday'
  if (diffDays < 7) return `${Math.floor(diffDays)}d ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`
  return `${Math.floor(diffDays / 365)}y ago`
})

const STALE_DAYS = 10

const badgeState = computed((): 'new' | 'stale' | null => {
  if (props.isViewed) return null
  if (props.job.date_posted) {
    const diffDays = (Date.now() - new Date(props.job.date_posted).getTime()) / 86_400_000
    if (diffDays > STALE_DAYS) return 'stale'
  }
  return 'new'
})

const locationDisplay = computed(() => {
  if (props.job.location_city && props.job.location_state) {
    return `${props.job.location_city}, ${props.job.location_state}`
  }
  return props.job.location_raw || 'Location not specified'
})

// Handlers
function handleFavoriteClick(e: Event) {
  e.stopPropagation()
  emit('favorite', props.job.id)
}

function handleHideClick(e: Event) {
  e.stopPropagation()
  emit('hide', props.job.id)
}

function handleCardClick() {
  emit('click', props.job.id)
}

function openJobUrl(e: Event) {
  e.stopPropagation()
  window.open(props.job.job_url, '_blank', 'noopener')
}
</script>

<template>
  <article 
    class="job-card"
    :class="{ 'is-favorite': isFavorite, 'is-selected': isSelected, 'is-viewed': isViewed }"
    role="article"
    :aria-label="`${job.title} at ${job.company}${isViewed ? ' (viewed)' : ''}`"
    :aria-selected="isSelected"
    tabindex="0"
    @click="handleCardClick"
    @keydown.enter="handleCardClick"
    @keydown.space.prevent="handleCardClick"
  >
    <!-- Header: Title + Actions -->
    <div class="job-card-header">
      <div class="job-card-title-row">
        <h3 class="job-card-title" :title="job.title">
          {{ job.title }}
        </h3>
        <BaseBadge v-if="badgeState" :variant="badgeState">{{ badgeState === 'stale' ? 'Stale' : 'New' }}</BaseBadge>
      </div>
      
      <div class="job-card-actions">
        <button 
          class="btn-icon btn-favorite"
          :class="{ active: isFavorite }"
          :title="isFavorite ? 'Remove from favorites' : 'Add to favorites'"
          :aria-label="isFavorite ? 'Remove from favorites' : 'Add to favorites'"
          :aria-pressed="isFavorite"
          @click="handleFavoriteClick"
        >
          <span class="icon-star" aria-hidden="true">{{ isFavorite ? '★' : '☆' }}</span>
        </button>
        <button 
          class="btn-icon btn-hide"
          title="Hide this job"
          aria-label="Hide this job"
          @click="handleHideClick"
        >
          <span class="icon-close" aria-hidden="true">×</span>
        </button>
      </div>
    </div>
    
    <!-- Meta: Company, Location, Badges -->
    <div class="job-card-meta">
      <span class="company">{{ job.company }}</span>
      <span v-if="job.glassdoor_rating" class="glassdoor-rating" :title="`Glassdoor: ${job.glassdoor_rating} / 5`">
        <svg class="star-icon" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
          <path d="M8 1.25l1.75 3.55 3.92.57-2.84 2.77.67 3.91L8 10.27l-3.5 1.78.67-3.91L2.33 5.37l3.92-.57z"/>
        </svg>
        <span class="rating-value">{{ job.glassdoor_rating.toFixed(1) }}</span>
      </span>
      <span v-else class="glassdoor-rating no-rating" title="No Glassdoor rating found">
        <svg class="star-icon" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
          <path d="M8 1.25l1.75 3.55 3.92.57-2.84 2.77.67 3.91L8 10.27l-3.5 1.78.67-3.91L2.33 5.37l3.92-.57z"/>
        </svg>
        <span class="rating-value">N/A</span>
      </span>
      <span class="separator">•</span>
      <span class="location">{{ locationDisplay }}</span>
      
      <div class="job-card-badges">
        <BaseBadge v-if="job.is_remote" variant="remote">Remote</BaseBadge>
        <BaseBadge v-if="job.company_size" variant="default">{{ job.company_size }}</BaseBadge>
      </div>
    </div>
    
    <!-- Salary (if available) -->
    <div v-if="formattedSalary" class="job-card-salary">
      {{ formattedSalary }}
    </div>
    
    <!-- Footer: Date, Sources, Apply -->
    <div class="job-card-footer">
      <div class="job-card-footer-left">
        <span class="posted-date">{{ postedDate }}</span>
        <div class="job-sources">
          <BaseBadge 
            v-for="source in job.sources.slice(0, 2)" 
            :key="source" 
            variant="source"
          >
            {{ source }}
          </BaseBadge>
        </div>
      </div>
      
      <button 
        class="btn btn-primary btn-sm" 
        :aria-label="`Apply for ${job.title} at ${job.company}`"
        @click="openJobUrl"
      >
        Apply →
      </button>
    </div>
  </article>
</template>

<style scoped>
.job-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.job-card:hover {
  background: var(--bg-tertiary);
  border-color: var(--border-focus);
}

.job-card:focus-visible {
  outline: 2px solid var(--accent-primary);
  outline-offset: 2px;
  border-color: var(--accent-primary);
}

.job-card.is-favorite {
  border-left: 3px solid var(--status-favorite);
}

.job-card.is-selected {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 2px var(--accent-primary);
}

.job-card.is-viewed {
  opacity: 0.7;
}

.job-card.is-viewed:hover {
  opacity: 1;
}

.job-card.is-viewed .job-card-title::after {
  content: ' ✓';
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-left: var(--space-1);
}

.job-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.job-card-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
}

.job-card-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.job-card-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.job-card-actions .btn-icon {
  /* Minimum 44px touch target for accessibility */
  min-width: 44px;
  min-height: 44px;
  padding: var(--space-2);
  background: var(--bg-tertiary);
  border: 1px solid transparent;
  color: var(--text-muted);
  font-size: var(--text-xl);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
}

.job-card-actions .btn-icon:hover {
  background: var(--bg-hover);
  border-color: var(--border-color);
  color: var(--text-primary);
}

.job-card-actions .btn-icon:focus-visible {
  outline: 2px solid var(--accent-primary);
  outline-offset: 2px;
}

.job-card-actions .btn-favorite.active {
  color: var(--status-favorite);
  background: rgba(245, 158, 11, 0.1);
}

.job-card-actions .btn-hide:hover {
  background: rgba(239, 68, 68, 0.1);
  color: var(--accent-error, #ef4444);
}

.job-card-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.job-card-meta .company {
  font-weight: 500;
}

.glassdoor-rating {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--text-primary);
  font-size: var(--text-xs);
  font-weight: 500;
  opacity: 0.85;
}

.glassdoor-rating .star-icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

.glassdoor-rating .rating-value {
  font-variant-numeric: tabular-nums;
}

.glassdoor-rating.no-rating {
  color: var(--text-muted);
  opacity: 0.5;
}

.job-card-meta .separator {
  color: var(--text-muted);
}

.job-card-badges {
  display: flex;
  gap: var(--space-1);
  margin-left: var(--space-1);
}

.job-card-salary {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--accent-success);
  margin-bottom: var(--space-3);
}

.job-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.job-card-footer-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.posted-date {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.job-sources {
  display: flex;
  gap: var(--space-1);
}

.btn-sm {
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-sm);
}
</style>
