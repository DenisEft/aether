<template>
  <div
    class="base-card"
    :class="{ padded, hover }"
  >
    <div
      v-if="title"
      class="card-header"
    >
      <h3 class="card-title">
        {{ title }}
      </h3>
      <slot name="actions" />
    </div>
    <div class="card-body">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  padded?: boolean
  hover?: boolean
}>(), {
  padded: true,
})
</script>

<style scoped>
.base-card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; }
.padded { padding: 16px; }
.hover:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.card-title { margin: 0; font-size: 14px; font-weight: 600; color: #202124; }
</style>
