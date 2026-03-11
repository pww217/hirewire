<script setup lang="ts">
/**
 * SettingsView - App preferences (filter settings moved to FilterPanel)
 */
</script>

<template>
  <div class="settings-view">
    <header class="settings-header">
      <h1 class="settings-title">Settings</h1>
    </header>

    <main class="settings-content">
      <section class="settings-section about-section">
        <h2 class="section-title">About HireWire</h2>
        <p class="about-text">
          HireWire tracks job listings directly from company ATS boards (Greenhouse, Lever, Ashby).
          Use the filter panel on the main view to search and filter jobs by location, work type, keywords, and more.
        </p>
        <p class="about-version">v0.2.0</p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.settings-header {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-color);
}

.settings-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.settings-content {
  flex: 1;
  padding: var(--space-5);
  overflow-y: auto;
  max-width: 800px;
}

.settings-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
}

.section-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-2) 0;
}

.about-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
  line-height: 1.6;
}

.about-version {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
}
</style>
