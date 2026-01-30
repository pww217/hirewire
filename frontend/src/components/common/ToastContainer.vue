<script setup lang="ts">
/**
 * ToastContainer - Display toast notifications
 */
import { useUIStore } from '@/stores/ui'

const uiStore = useUIStore()

function getIcon(type: string) {
  switch (type) {
    case 'success': return '✓'
    case 'error': return '✕'
    case 'warning': return '⚠'
    case 'info': return 'ℹ'
    default: return ''
  }
}

function handleAction(toastId: number, onClick: () => void) {
  onClick()
  uiStore.removeToast(toastId)
}
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div 
          v-for="toast in uiStore.toasts" 
          :key="toast.id"
          class="toast"
          :class="`toast-${toast.type}`"
        >
          <span class="toast-icon">{{ getIcon(toast.type) }}</span>
          <span class="toast-message">{{ toast.message }}</span>
          <button 
            v-if="toast.action"
            class="toast-action"
            @click="handleAction(toast.id, toast.action.onClick)"
          >
            {{ toast.action.label }}
          </button>
          <button 
            class="toast-close"
            @click="uiStore.removeToast(toast.id)"
          >
            ✕
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  bottom: var(--space-4);
  right: var(--space-4);
  z-index: 1100;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.toast {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 280px;
  max-width: 400px;
  padding: var(--space-3) var(--space-4);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}

.toast-icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-sm);
  font-weight: 600;
  border-radius: 50%;
}

.toast-success .toast-icon {
  background: rgba(34, 197, 94, 0.2);
  color: var(--accent-success);
}

.toast-error .toast-icon {
  background: rgba(239, 68, 68, 0.2);
  color: var(--accent-error);
}

.toast-warning .toast-icon {
  background: rgba(245, 158, 11, 0.2);
  color: var(--accent-warning);
}

.toast-info .toast-icon {
  background: rgba(99, 102, 241, 0.2);
  color: var(--accent-primary);
}

.toast-message {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--text-primary);
}

.toast-action {
  flex-shrink: 0;
  padding: var(--space-1) var(--space-2);
  background: var(--accent-primary);
  border: none;
  border-radius: var(--radius-sm);
  color: white;
  font-size: var(--text-xs);
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.toast-action:hover {
  background: var(--accent-primary-hover, #4f46e5);
}

.toast-close {
  flex-shrink: 0;
  padding: var(--space-1);
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.toast-close:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* Transitions */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
