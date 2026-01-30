<script setup lang="ts">
/**
 * JobCardSkeleton - Loading skeleton for job cards
 */
</script>

<template>
  <div class="job-card-skeleton">
    <div class="skeleton-header">
      <div class="skeleton skeleton-title"></div>
      <div class="skeleton skeleton-badge"></div>
    </div>
    <div class="skeleton-meta">
      <div class="skeleton skeleton-company"></div>
      <div class="skeleton skeleton-location"></div>
    </div>
    <div class="skeleton skeleton-salary"></div>
    <div class="skeleton-footer">
      <div class="skeleton skeleton-date"></div>
      <div class="skeleton skeleton-button"></div>
    </div>
  </div>
</template>

<style scoped>
.job-card-skeleton {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
}

.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 25%,
    var(--bg-hover) 50%,
    var(--bg-tertiary) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: var(--radius-sm);
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.skeleton-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.skeleton-title {
  height: 20px;
  width: 60%;
}

.skeleton-badge {
  height: 18px;
  width: 40px;
}

.skeleton-meta {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.skeleton-company {
  height: 16px;
  width: 120px;
}

.skeleton-location {
  height: 16px;
  width: 150px;
}

.skeleton-salary {
  height: 16px;
  width: 100px;
  margin-bottom: var(--space-3);
}

.skeleton-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.skeleton-date {
  height: 14px;
  width: 80px;
}

.skeleton-button {
  height: 28px;
  width: 70px;
}
</style>
