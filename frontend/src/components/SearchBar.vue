<script setup lang="ts">
/**
 * SearchBar - Main search input with debouncing
 */
import { ref, watch } from 'vue'
import { useDebounce } from '@/composables/useDebounce'

interface Props {
  modelValue: string
  placeholder?: string
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: 'Search jobs by title or company...',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: [value: string]
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const localValue = ref(props.modelValue)
const debouncedValue = useDebounce(localValue, 300)

// Sync external changes
watch(() => props.modelValue, (newValue) => {
  localValue.value = newValue
})

// Emit debounced search
watch(debouncedValue, (value) => {
  emit('update:modelValue', value)
  emit('search', value)
})

function handleInput(e: Event) {
  localValue.value = (e.target as HTMLInputElement).value
}

function handleClear() {
  localValue.value = ''
  emit('update:modelValue', '')
  emit('search', '')
  inputRef.value?.focus()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    handleClear()
  }
}

// Expose input element for external focus (keyboard shortcuts)
function focus() {
  inputRef.value?.focus()
}

defineExpose({
  focus,
  inputRef,
})
</script>

<template>
  <div class="search-bar">
    <span class="search-icon">🔍</span>
    <input
      ref="inputRef"
      type="text"
      class="search-input"
      :value="localValue"
      :placeholder="placeholder"
      @input="handleInput"
      @keydown="handleKeydown"
    />
    <button 
      v-if="localValue"
      class="search-clear"
      type="button"
      @click="handleClear"
    >
      ×
    </button>
  </div>
</template>

<style scoped>
.search-bar {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: var(--space-3);
  font-size: var(--text-base);
  pointer-events: none;
  opacity: 0.5;
}

.search-input {
  width: 100%;
  padding: var(--space-3) var(--space-6);
  padding-left: 40px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-primary);
  font-family: inherit;
  font-size: var(--text-base);
  transition: all var(--transition-fast);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.search-input:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.search-clear {
  position: absolute;
  right: var(--space-3);
  padding: var(--space-1);
  background: var(--bg-hover);
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-size: var(--text-base);
  line-height: 1;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.search-clear:hover {
  background: var(--border-color);
  color: var(--text-primary);
}
</style>
