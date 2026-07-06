<template>
  <div
    class="input-group"
    :class="{ error: !!error }"
  >
    <label
      v-if="label"
      class="input-label"
    >{{ label }}</label>
    <input
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      class="input-field"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    >
    <span
      v-if="error"
      class="input-error"
    >{{ error }}</span>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  modelValue: string
  label?: string
  type?: string
  placeholder?: string
  disabled?: boolean
  error?: string
}>(), {
  type: 'text',
})

defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<style scoped>
.input-group { display: flex; flex-direction: column; gap: 4px; }
.input-label { font-size: 12px; font-weight: 500; color: #5f6368; }
.input-field { padding: 8px 12px; border: 1px solid #dadce0; border-radius: 6px; font-size: 14px; outline: none; transition: border 0.15s; }
.input-field:focus { border-color: #1a73e8; }
.error .input-field { border-color: #ea4335; }
.error .input-label { color: #ea4335; }
.input-error { font-size: 11px; color: #ea4335; }
.input-field:disabled { background: #f1f3f4; }
</style>
