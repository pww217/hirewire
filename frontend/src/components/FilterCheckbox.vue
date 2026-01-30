<script setup lang="ts">
/**
 * FilterCheckbox - Styled checkbox for filter options
 */
interface Props {
  checked: boolean
  label: string
  disabled?: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  change: []
}>()
</script>

<template>
  <label class="filter-checkbox" :class="{ disabled }">
    <input 
      type="checkbox"
      :checked="checked"
      :disabled="disabled"
      @change="emit('change')"
    />
    <span class="checkbox-box">
      <span v-if="checked" class="checkbox-check">✓</span>
    </span>
    <span class="checkbox-label">{{ label }}</span>
  </label>
</template>

<style scoped>
.filter-checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  user-select: none;
}

.filter-checkbox.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.filter-checkbox input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.checkbox-box {
  width: 18px;
  height: 18px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.filter-checkbox:hover:not(.disabled) .checkbox-box {
  border-color: var(--border-focus);
}

.filter-checkbox input:checked + .checkbox-box {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
}

.checkbox-check {
  color: white;
  font-size: 11px;
  font-weight: 600;
}

.checkbox-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.filter-checkbox:hover:not(.disabled) .checkbox-label {
  color: var(--text-primary);
}
</style>
