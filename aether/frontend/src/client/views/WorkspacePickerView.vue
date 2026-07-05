<template>
  <div class="picker">
    <div class="picker-container">
      <header class="picker-header">
        <div class="picker-logo">Aether</div>
        <h1>Select Workspace</h1>
        <p>Choose a workspace to continue</p>
      </header>

      <!-- Loading -->
      <div v-if="loading" class="picker-grid">
        <div v-for="i in 4" :key="i" class="ws-card-skeleton">
          <div class="skel-line w-70" />
          <div class="skel-line w-40" />
          <div class="skel-line w-50" />
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="picker-error">
        <span class="error-icon">⚠️</span>
        <p>{{ error }}</p>
        <button class="btn-retry" @click="loadWorkspaces">Try Again</button>
      </div>

      <!-- Empty -->
      <div v-else-if="workspaceList.length === 0" class="picker-empty">
        <div class="empty-illustration">🏢</div>
        <h2>No workspaces found</h2>
        <p>Create your first workspace to get started.</p>
        <router-link to="/signup" class="btn-create">Create Workspace</router-link>
      </div>

      <!-- Grid -->
      <div v-else class="picker-grid">
        <div
          v-for="ws in workspaceList"
          :key="ws.id"
          class="ws-card"
          @click="navigateTo(ws.slug)"
          @keydown.enter="navigateTo(ws.slug)"
          tabindex="0"
        >
          <div class="ws-card-header">
            <div class="ws-logo" :style="{ background: cardColor(ws.name) }">
              {{ ws.name.substring(0, 2).toUpperCase() }}
            </div>
            <span class="ws-role-badge" :class="roleClass(ws)">Owner</span>
          </div>
          <div class="ws-card-body">
            <h3 class="ws-name">{{ ws.name }}</h3>
            <div class="ws-slug">{{ ws.slug }}</div>
          </div>
          <div class="ws-card-footer">
            <span class="ws-members">👥 {{ ws.memberCount || 1 }} member{{ (ws.memberCount || 1) !== 1 ? 's' : '' }}</span>
            <span class="ws-arrow">→</span>
          </div>
        </div>

        <!-- Create New Card -->
        <router-link to="/signup" class="ws-card ws-card-new">
          <div class="new-card-content">
            <div class="new-icon">+</div>
            <h3>Create New Workspace</h3>
            <p>Set up a new organisation</p>
          </div>
        </router-link>
      </div>

      <!-- Footer -->
      <footer class="picker-footer">
        <button class="btn-logout" @click="handleLogout">Sign Out</button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../../shared/composables/useAuth'
import { useTenant } from '../../shared/composables/useTenant'
import type { Tenant } from '../../shared/types/admin'

const router = useRouter()
const { currentUser, logout } = useAuth()
const { tenants, loadTenants } = useTenant()

const loading = ref(true)
const error = ref<string | null>(null)
const workspaceList = ref<(Tenant & { memberCount?: number })[]>([])

function cardColor(name: string): string {
  const colors = ['#1a73e8', '#34a853', '#ea4335', '#fbbc04', '#8e24aa', '#00acc1', '#d81b60', '#e37400']
  let hash = 0
  for (let i = 0; i < (name || '?').length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return colors[Math.abs(hash) % colors.length]
}

function roleClass(_ws: Tenant): string {
  // TODO: derive from actual membership
  return 'role-owner'
}

function navigateTo(slug: string) {
  router.push(`/${slug}`)
}

async function loadWorkspaces() {
  loading.value = true
  error.value = null
  try {
    await loadTenants()
    workspaceList.value = tenants.value.map(t => ({
      ...t,
      memberCount: 1, // TODO: from API
    }))
  } catch (e: unknown) {
    console.error('[WorkspacePickerView] Failed to load workspaces', e)
    error.value = 'Failed to load workspaces. Please try again.'
  } finally {
    loading.value = false
  }
}

async function handleLogout() {
  await logout()
  router.push('/login')
}

onMounted(loadWorkspaces)
</script>

<style scoped>
.picker {
  min-height: 100vh;
  background: #f8f9fa;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.picker-container {
  width: 100%;
  max-width: 680px;
}

/* ── Header ── */
.picker-header {
  text-align: center;
  margin-bottom: 32px;
}
.picker-logo {
  font-size: 28px;
  font-weight: 800;
  color: #1a73e8;
  margin-bottom: 16px;
  letter-spacing: -0.5px;
}
.picker-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #202124;
  margin-bottom: 4px;
}
.picker-header p {
  font-size: 14px;
  color: #5f6368;
}

/* ── Grid ── */
.picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

/* ── Workspace Card ── */
.ws-card {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 12px;
  outline: none;
}
.ws-card:hover {
  border-color: #1a73e8;
  box-shadow: 0 4px 12px rgba(26, 115, 232, 0.12);
  transform: translateY(-2px);
}
.ws-card:focus-visible {
  border-color: #1a73e8;
  box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.3);
}

.ws-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ws-logo {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ws-role-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.role-owner { background: #e8f0fe; color: #1a73e8; }
.role-admin { background: #e6f4ea; color: #137333; }
.role-member { background: #f1f3f4; color: #5f6368; }

.ws-card-body {
  flex: 1;
}
.ws-name {
  font-size: 15px;
  font-weight: 600;
  color: #202124;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ws-slug {
  font-size: 12px;
  color: #80868b;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.ws-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ws-members {
  font-size: 12px;
  color: #5f6368;
}
.ws-arrow {
  font-size: 16px;
  color: #1a73e8;
  opacity: 0;
  transition: opacity 0.2s;
}
.ws-card:hover .ws-arrow {
  opacity: 1;
}

/* ── Create New Card ── */
.ws-card-new {
  border-style: dashed;
  border-color: #dadce0;
  background: transparent;
  text-decoration: none;
}
.ws-card-new:hover {
  border-color: #1a73e8;
  background: #f8fbff;
}
.new-card-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 8px;
  flex: 1;
}
.new-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #e8f0fe;
  color: #1a73e8;
  font-size: 22px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.new-card-content h3 {
  font-size: 14px;
  font-weight: 600;
  color: #1a73e8;
  margin: 0;
}
.new-card-content p {
  font-size: 12px;
  color: #5f6368;
  margin: 0;
}

/* ── Skeleton ── */
.ws-card-skeleton {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.skel-line {
  height: 10px;
  background: #e8eaed;
  border-radius: 4px;
}
.w-70 { width: 70%; }
.w-40 { width: 40%; }
.w-50 { width: 50%; }

/* ── Error ── */
.picker-error {
  text-align: center;
  padding: 32px;
}
.error-icon { font-size: 32px; }
.picker-error p {
  font-size: 14px;
  color: #5f6368;
  margin: 12px 0;
}
.btn-retry {
  padding: 8px 20px;
  background: #1a73e8;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.btn-retry:hover { background: #1557b0; }

/* ── Empty ── */
.picker-empty {
  text-align: center;
  padding: 48px 24px;
}
.empty-illustration { font-size: 48px; margin-bottom: 12px; }
.picker-empty h2 {
  font-size: 18px;
  font-weight: 600;
  color: #202124;
  margin-bottom: 4px;
}
.picker-empty p {
  font-size: 13px;
  color: #5f6368;
  margin-bottom: 16px;
}
.btn-create {
  display: inline-block;
  padding: 10px 24px;
  background: #1a73e8;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  border-radius: 6px;
  text-decoration: none;
}
.btn-create:hover { background: #1557b0; }

/* ── Footer ── */
.picker-footer {
  text-align: center;
  margin-top: 32px;
}
.btn-logout {
  padding: 8px 20px;
  background: transparent;
  color: #5f6368;
  border: 1px solid #dadce0;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-logout:hover {
  background: #f1f3f4;
  color: #3c4043;
}
</style>
