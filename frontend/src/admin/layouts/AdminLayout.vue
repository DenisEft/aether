<template>
  <div class="admin-layout">
    <aside class="sidebar">
      <div class="logo">Aether Admin</div>
      <nav>
        <router-link to="/admin">Dashboard</router-link>
        <router-link to="/admin/tenants">Tenants</router-link>
        <router-link to="/admin/subscriptions">Subscriptions</router-link>
        <router-link to="/admin/drivers">Drivers</router-link>
        <router-link to="/admin/billing">Billing</router-link>
        <router-link to="/admin/audit">Audit</router-link>
      </nav>
    </aside>
    <main class="content">
      <Suspense>
        <template #default>
          <router-view />
        </template>
        <template #fallback>
          <div class="route-loading">
            <div class="spinner" />
            <p>Loading admin view...</p>
          </div>
        </template>
      </Suspense>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'

const routeError = ref<string | null>(null)

onErrorCaptured((err) => {
  routeError.value = err instanceof Error ? err.message : String(err)
  return false // prevent propagation
})
</script>

<style scoped>
.admin-layout { display: flex; height: 100vh; }
.sidebar { width: 220px; background: #1a1a2e; color: #fff; border-right: 1px solid #2a2a4e; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.logo { font-size: 18px; font-weight: 700; color: #4fc3f7; margin-bottom: 16px; }
nav { display: flex; flex-direction: column; gap: 4px; }
nav a { padding: 8px 12px; border-radius: 6px; color: #b0bec5; font-weight: 500; font-size: 13px; }
nav a:hover, nav a.router-link-active { background: #2a2a4e; color: #4fc3f7; text-decoration: none; }
.content { flex: 1; overflow-y: auto; background: #f8f9fa; padding: 24px; }

/* Route loading fallback in Suspense */
.route-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  gap: var(--space-md);
  color: var(--color-on-surface-variant);
}

.route-loading .spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--color-outline);
  border-top: 4px solid var(--color-primary);
  border-radius: 50%;
  animation: admin-spin 1s linear infinite;
}

@keyframes admin-spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
