<script setup lang="ts">
/**
 * JobDetail - Full job detail view with description
 */
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useJobsStore } from '@/stores/jobs'
import { useFavoritesStore } from '@/stores/favorites'
import BaseBadge from '@/components/common/BaseBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

interface Props {
  jobId: number
}

const props = defineProps<Props>()

const router = useRouter()
const jobsStore = useJobsStore()
const favoritesStore = useFavoritesStore()

onMounted(() => {
  jobsStore.fetchJobDetail(props.jobId)
})

const job = computed(() => jobsStore.currentJob)
const isFavorite = computed(() => job.value ? favoritesStore.isFavorite(job.value.id) : false)

/**
 * Process description to handle both HTML and plain text formats.
 * JobSpy returns HTML from some sources (Indeed, Glassdoor) and plain text from others.
 */
const processedDescription = computed(() => {
  if (!job.value?.description) return null
  const desc = job.value.description
  
  // Check if content already contains HTML tags
  const hasHtmlTags = /<[a-z][\s\S]*>/i.test(desc)
  
  if (hasHtmlTags) {
    // Already HTML, return as-is
    return desc
  }
  
  // Plain text - convert to HTML
  let html = desc
    // Escape HTML entities first
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Convert double newlines to paragraph breaks
    .replace(/\n\n+/g, '</p><p>')
    // Convert single newlines to line breaks
    .replace(/\n/g, '<br>')
    // Linkify URLs
    .replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener">$1</a>'
    )
  
  // Wrap in paragraph tags
  return `<p>${html}</p>`
})

const formattedSalary = computed(() => {
  if (!job.value) return null
  const { salary_min, salary_max, salary_interval } = job.value
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
      yearly: '/year',
      monthly: '/month',
      hourly: '/hour',
    }
    salary += ` ${intervals[salary_interval] || ''}`
  }
  
  return salary
})

const postedDate = computed(() => {
  if (!job.value?.date_posted) return 'Recently'
  return new Date(job.value.date_posted).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
})

const firstSeenDate = computed(() => {
  if (!job.value?.first_seen) return null
  return new Date(job.value.first_seen).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
})

async function toggleFavorite() {
  if (job.value) {
    await favoritesStore.toggleFavorite(job.value.id)
  }
}

function goBack() {
  router.back()
}

function openJobUrl() {
  if (job.value) {
    window.open(job.value.job_url, '_blank', 'noopener')
  }
}
</script>

<template>
  <div class="job-detail">
    <!-- Loading State -->
    <div v-if="jobsStore.isLoading" class="job-detail-loading">
      <LoadingSpinner size="lg" />
    </div>
    
    <!-- Error State -->
    <div v-else-if="jobsStore.error" class="job-detail-error">
      <p>{{ jobsStore.error }}</p>
      <button class="btn btn-secondary" @click="goBack">← Go Back</button>
    </div>
    
    <!-- Job Content -->
    <template v-else-if="job">
      <!-- Header -->
      <div class="job-detail-header">
        <button class="back-btn" @click="goBack">← Back</button>
        
        <div class="job-detail-actions">
          <button 
            class="btn"
            :class="isFavorite ? 'btn-favorite' : 'btn-secondary'"
            @click="toggleFavorite"
          >
            {{ isFavorite ? '★ Saved' : '☆ Save' }}
          </button>
          <button class="btn btn-primary" @click="openJobUrl">
            Apply Now →
          </button>
        </div>
      </div>
      
      <!-- Title Section -->
      <div class="job-detail-title-section">
        <div class="job-detail-badges">
          <BaseBadge v-if="job.is_remote" variant="remote">Remote</BaseBadge>
          <BaseBadge v-if="job.company_size" variant="default">{{ job.company_size }} employees</BaseBadge>
          <BaseBadge v-for="source in job.sources" :key="source" variant="source">{{ source }}</BaseBadge>
        </div>
        
        <h1 class="job-detail-title">{{ job.title }}</h1>
        
        <div class="job-detail-company">
          <a 
            v-if="job.company_url" 
            :href="job.company_url" 
            target="_blank" 
            rel="noopener"
            class="company-link"
          >
            {{ job.company }}
          </a>
          <span v-else>{{ job.company }}</span>
          <span v-if="job.company_industry" class="company-industry">
            • {{ job.company_industry }}
          </span>
        </div>
        
        <div class="job-detail-meta">
          <span v-if="job.location_raw" class="meta-item">
            📍 {{ job.location_raw }}
          </span>
          <span v-if="formattedSalary" class="meta-item salary">
            💰 {{ formattedSalary }}
          </span>
          <span v-if="job.job_type" class="meta-item">
            💼 {{ job.job_type.replace('_', ' ') }}
          </span>
        </div>
      </div>
      
      <!-- Info Cards -->
      <div class="job-detail-info">
        <div class="info-card">
          <div class="info-label">Posted</div>
          <div class="info-value">{{ postedDate }}</div>
        </div>
        <div v-if="firstSeenDate" class="info-card">
          <div class="info-label">First Seen</div>
          <div class="info-value">{{ firstSeenDate }}</div>
        </div>
        <div v-if="job.location_city || job.location_country" class="info-card">
          <div class="info-label">Location</div>
          <div class="info-value">
            {{ [job.location_city, job.location_state, job.location_country].filter(Boolean).join(', ') }}
          </div>
        </div>
      </div>
      
      <!-- Description -->
      <div class="job-detail-description">
        <h2 class="description-title">Job Description</h2>
        <div 
          v-if="processedDescription" 
          class="description-content"
          v-html="processedDescription"
        ></div>
        <p v-else class="description-empty">
          No description available. Click "Apply Now" to view the full listing.
        </p>
      </div>
      
      <!-- Footer Actions -->
      <div class="job-detail-footer">
        <button class="btn btn-primary btn-lg" @click="openJobUrl">
          Apply Now →
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.job-detail {
  max-width: 800px;
  margin: 0 auto;
  padding: var(--space-6);
}

.job-detail-loading,
.job-detail-error {
  text-align: center;
  padding: var(--space-8);
}

.job-detail-error p {
  color: var(--accent-error);
  margin-bottom: var(--space-4);
}

.job-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-6);
}

.back-btn {
  padding: var(--space-2) var(--space-3);
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: color var(--transition-fast);
}

.back-btn:hover {
  color: var(--text-primary);
}

.job-detail-actions {
  display: flex;
  gap: var(--space-2);
}

.btn-favorite {
  background: rgba(245, 158, 11, 0.15);
  color: var(--status-favorite);
  border: 1px solid var(--status-favorite);
}

.job-detail-title-section {
  margin-bottom: var(--space-6);
}

.job-detail-badges {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.job-detail-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--space-2) 0;
}

.job-detail-company {
  font-size: var(--text-lg);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}

.company-link {
  color: var(--accent-primary);
}

.company-link:hover {
  color: var(--accent-primary-hover);
}

.company-industry {
  color: var(--text-muted);
}

.job-detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.meta-item {
  font-size: var(--text-base);
  color: var(--text-secondary);
}

.meta-item.salary {
  color: var(--accent-success);
  font-weight: 500;
}

.job-detail-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-6);
}

.info-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}

.info-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-1);
}

.info-value {
  font-size: var(--text-sm);
  color: var(--text-primary);
}

.job-detail-description {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  margin-bottom: var(--space-6);
}

.description-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-4) 0;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-color);
}

.description-content {
  font-size: var(--text-base);
  line-height: 1.7;
  color: var(--text-secondary);
}

.description-content :deep(h1),
.description-content :deep(h2),
.description-content :deep(h3) {
  color: var(--text-primary);
  margin-top: var(--space-4);
  margin-bottom: var(--space-2);
}

.description-content :deep(ul),
.description-content :deep(ol) {
  padding-left: var(--space-5);
  margin: var(--space-3) 0;
}

.description-content :deep(li) {
  margin-bottom: var(--space-2);
}

.description-content :deep(a) {
  color: var(--accent-primary);
}

.description-content :deep(p) {
  margin-bottom: var(--space-3);
}

.description-empty {
  color: var(--text-muted);
  font-style: italic;
}

.job-detail-footer {
  text-align: center;
}

.btn-lg {
  padding: var(--space-3) var(--space-6);
  font-size: var(--text-lg);
}
</style>
