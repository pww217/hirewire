import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ToastAction {
  label: string
  onClick: () => void
}

export interface Toast {
  id: number
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
  duration?: number
  action?: ToastAction
}

export const useUIStore = defineStore('ui', () => {
  // State
  const toasts = ref<Toast[]>([])
  const isMobileMenuOpen = ref(false)
  const isFilterPanelOpen = ref(true)
  
  let toastIdCounter = 0
  
  // Actions
  function showToast(
    type: Toast['type'], 
    message: string, 
    duration = 5000,
    action?: ToastAction
  ) {
    const id = ++toastIdCounter
    const toast: Toast = { id, type, message, duration, action }
    toasts.value.push(toast)
    
    if (duration > 0) {
      setTimeout(() => removeToast(id), duration)
    }
    
    return id
  }
  
  /**
   * Show a toast with an undo action
   */
  function showWithUndo(message: string, onUndo: () => void, duration = 6000) {
    return showToast('success', message, duration, {
      label: 'Undo',
      onClick: onUndo,
    })
  }
  
  function removeToast(id: number) {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index !== -1) {
      toasts.value.splice(index, 1)
    }
  }
  
  function showSuccess(message: string) {
    return showToast('success', message)
  }
  
  function showError(message: string) {
    return showToast('error', message, 8000)
  }
  
  function showInfo(message: string) {
    return showToast('info', message)
  }
  
  function showWarning(message: string) {
    return showToast('warning', message, 8000)
  }
  
  function toggleMobileMenu() {
    isMobileMenuOpen.value = !isMobileMenuOpen.value
  }
  
  function toggleFilterPanel() {
    isFilterPanelOpen.value = !isFilterPanelOpen.value
  }
  
  return {
    // State
    toasts,
    isMobileMenuOpen,
    isFilterPanelOpen,
    
    // Actions
    showToast,
    removeToast,
    showSuccess,
    showError,
    showInfo,
    showWarning,
    showWithUndo,
    toggleMobileMenu,
    toggleFilterPanel,
  }
})
