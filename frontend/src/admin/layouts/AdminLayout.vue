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
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.admin-layout { display: flex; height: 100vh; }
.sidebar { width: 220px; background: #1a1a2e; color: #fff; border-right: 1px solid #2a2a4e; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.logo { font-size: 18px; font-weight: 700; color: #4fc3f7; margin-bottom: 16px; }
nav { display: flex; flex-direction: column; gap: 4px; }
nav a { padding: 8px 12px; border-radius: 6px; color: #b0bec5; font-weight: 500; font-size: 13px; }
nav a:hover, nav a.router-link-active { background: #2a2a4e; color: #4fc3f7; text-decoration: none; }
.content { flex: 1; overflow-y: auto; background: #f8f9fa; padding: 24px; }
</style>
