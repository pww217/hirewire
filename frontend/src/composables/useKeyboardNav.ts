import { ref, onMounted, onUnmounted, computed } from 'vue'
import type { JobWithDescription } from '@/types/api'

/**
 * Keyboard navigation for job list
 * 
 * Shortcuts:
 * - j/↓: Move to next job
 * - k/↑: Move to previous job  
 * - f: Toggle favorite on selected job
 * - h: Hide selected job
 * - enter: Open selected job detail
 * - /: Focus search input
 * - esc: Close panels/clear selection
 */
export function useKeyboardNav(options: {
  jobs: () => JobWithDescription[]
  onFavorite: (jobId: number) => void
  onHide: (jobId: number) => void
  onOpenJob: (jobId: number) => void
  onClosePanel?: () => void
  searchInputRef?: () => HTMLInputElement | null
}) {
  const selectedIndex = ref(-1)
  const isEnabled = ref(true)

  const jobs = computed<JobWithDescription[]>(() => options.jobs())
  
  const selectedJob = computed(() => {
    if (selectedIndex.value >= 0 && selectedIndex.value < jobs.value.length) {
      return jobs.value[selectedIndex.value]
    }
    return null
  })

  const selectedJobId = computed(() => selectedJob.value?.id ?? null)

  function selectNext() {
    if (jobs.value.length === 0) return
    selectedIndex.value = Math.min(selectedIndex.value + 1, jobs.value.length - 1)
    scrollToSelected()
  }

  function selectPrev() {
    if (jobs.value.length === 0) return
    selectedIndex.value = Math.max(selectedIndex.value - 1, 0)
    scrollToSelected()
  }

  function selectFirst() {
    if (jobs.value.length === 0) return
    selectedIndex.value = 0
    scrollToSelected()
  }

  function clearSelection() {
    selectedIndex.value = -1
  }

  function scrollToSelected() {
    // Find the job card element and scroll it into view
    const jobCards = document.querySelectorAll('.job-card')
    if (jobCards[selectedIndex.value]) {
      jobCards[selectedIndex.value].scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      })
      // Also set focus for screen readers
      ;(jobCards[selectedIndex.value] as HTMLElement).focus()
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!isEnabled.value) return

    // Don't handle if user is typing in an input
    const target = event.target as HTMLElement
    if (
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.tagName === 'SELECT' ||
      target.isContentEditable
    ) {
      // Only handle Escape in inputs
      if (event.key === 'Escape') {
        target.blur()
        event.preventDefault()
      }
      return
    }

    switch (event.key) {
      case 'j':
      case 'ArrowDown':
        event.preventDefault()
        selectNext()
        break

      case 'k':
      case 'ArrowUp':
        event.preventDefault()
        selectPrev()
        break

      case 'f':
        event.preventDefault()
        if (selectedJob.value) {
          options.onFavorite(selectedJob.value.id)
        }
        break

      case 'h':
        event.preventDefault()
        if (selectedJob.value) {
          options.onHide(selectedJob.value.id)
          // After hiding, try to keep same position or go to prev
          if (selectedIndex.value >= jobs.value.length - 1) {
            selectPrev()
          }
        }
        break

      case 'Enter':
        event.preventDefault()
        if (selectedJob.value) {
          options.onOpenJob(selectedJob.value.id)
        }
        break

      case '/':
        event.preventDefault()
        options.searchInputRef?.()?.focus()
        break

      case 'Escape':
        event.preventDefault()
        if (selectedIndex.value >= 0) {
          clearSelection()
        } else {
          options.onClosePanel?.()
        }
        break

      case 'g':
        // gg to go to first job (vim style)
        if (event.repeat) return
        // Wait briefly for potential second 'g'
        break
    }
  }

  function enable() {
    isEnabled.value = true
  }

  function disable() {
    isEnabled.value = false
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown)
  })

  return {
    selectedIndex,
    selectedJobId,
    selectedJob,
    isEnabled,
    selectNext,
    selectPrev,
    selectFirst,
    clearSelection,
    enable,
    disable,
  }
}
