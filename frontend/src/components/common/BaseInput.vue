<script setup lang="ts">
/**
 * BaseInput - Reusable input component
 */
interface Props {
  modelValue: string
  placeholder?: string
  type?: string
  disabled?: boolean
}

withDefaults(defineProps<Props>(), {
  placeholder: '',
  type: 'text',
  disabled: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

function handleInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement).value)
}
</script>

<template>
  <input
    class="input"
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    @input="handleInput"
  />
</template>

<style scoped>
.input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-family: inherit;
  font-size: var(--text-base);
  transition: border-color var(--transition-fast);
}

.input::placeholder {
  color: var(--text-muted);
}

.input:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
