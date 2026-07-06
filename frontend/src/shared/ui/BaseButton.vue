<template>
  <button
    :class="['base-btn', `variant-${variant}`, `size-${size}`, { loading, block }]"
    :disabled="disabled || loading"
    @click="$emit('click')"
  >
    <span
      v-if="loading"
      class="spinner"
    />
    <slot />
  </button>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  loading?: boolean
  block?: boolean
}>(), {
  variant: 'primary',
  size: 'md',
})

defineEmits<{ click: [] }>()
</script>

<style scoped>
.base-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  border: none; border-radius: 6px; cursor: pointer; font-weight: 500;
  transition: all 0.15s; white-space: nowrap;
}
.size-sm { padding: 4px 10px; font-size: 12px; }
.size-md { padding: 6px 16px; font-size: 13px; }
.size-lg { padding: 10px 24px; font-size: 15px; }
.variant-primary { background: #1a73e8; color: #fff; }
.variant-primary:hover:not(:disabled) { background: #1557b0; }
.variant-secondary { background: #e8eaed; color: #3c4043; }
.variant-secondary:hover:not(:disabled) { background: #d2d4d7; }
.variant-ghost { background: transparent; color: #5f6368; }
.variant-ghost:hover:not(:disabled) { background: #f1f3f4; }
.variant-danger { background: #ea4335; color: #fff; }
.variant-danger:hover:not(:disabled) { background: #c5221f; }
.base-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.block { width: 100%; }
.spinner { width: 14px; height: 14px; border: 2px solid transparent; border-top-color: currentColor; border-radius: 50%; animation: spin 0.6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
