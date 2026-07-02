<template>
  <div class="tenant-detail">
    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="skeleton-header" />
      <div class="skeleton-tabs" />
      <div class="skeleton-content" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="btn btn-primary" @click="loadTenant">Retry</button>
    </div>

    <!-- Content -->
    <template v-else-if="tenant">
      <!-- Header -->
      <div class="detail-header">
        <div class="header-left">
          <button class="btn btn-ghost btn-sm back-btn" @click="$router.push('/admin/tenants')">
            ← Back
          </button>
          <div class="header-info">
            <div class="org-avatar">{{ tenant.name.charAt(0).toUpperCase() }}</div>
            <div>
              <h1>{{ tenant.name }}</h1>
              <span class="org-slug">@{{ tenant.slug }}</span>
            </div>
          </div>
        </div>
        <div class="header-right">
          <span class="status-badge" :class="`status-${tenant.is_active ? 'active' : 'suspended'}`">
            {{ tenant.is_active ? 'Active' : 'Suspended' }}
          </span>
          <span class="plan-badge" v-if="tenant.plan">{{ tenant.plan }}</span>
          <button
            class="btn"
            :class="tenant.is_active ? 'btn-warning' : 'btn-success'"
            @click="toggleStatus"
          >
            {{ tenant.is_active ? 'Suspend' : 'Activate' }}
          </button>
          <button class="btn btn-danger" @click="confirmDelete">Delete</button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-btn"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">
        <!-- Overview -->
        <div v-if="activeTab === 'overview'" class="tab-panel">
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-label">Users</span>
              <span class="stat-value">{{ overview.users }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Channels</span>
              <span class="stat-value">{{ overview.channels }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">AI Requests (30d)</span>
              <span class="stat-value">{{ overview.aiRequests.toLocaleString() }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Storage Used</span>
              <span class="stat-value">{{ overview.storage }}</span>
            </div>
          </div>
        </div>

        <!-- Users -->
        <div v-if="activeTab === 'users'" class="tab-panel">
          <div v-if="usersLoading" class="skeleton-list">
            <div v-for="n in 5" :key="n" class="skeleton-row" />
          </div>
          <div v-else-if="users.length === 0" class="empty-state">
            <p>No users in this tenant</p>
          </div>
          <table v-else class="data-table">
            <thead>
              <tr><th>User</th><th>Email</th><th>Role</th><th>Joined</th></tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id">
                <td class="user-cell">
                  <div class="user-avatar">{{ u.name?.charAt(0)?.toUpperCase() || '?' }}</div>
                  {{ u.name || 'Unknown' }}
                </td>
                <td>{{ u.email }}</td>
                <td><span class="role-badge">{{ u.role }}</span></td>
                <td class="date-cell">{{ formatDate(u.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Channels -->
        <div v-if="activeTab === 'channels'" class="tab-panel">
          <div v-if="channelsLoading" class="skeleton-list">
            <div v-for="n in 4" :key="n" class="skeleton-row" />
          </div>
          <div v-else-if="channels.length === 0" class="empty-state">
            <p>No channels configured</p>
          </div>
          <table v-else class="data-table">
            <thead>
              <tr><th>Type</th><th>Name</th><th>Status</th><th>Connected</th></tr>
            </thead>
            <tbody>
              <tr v-for="ch in channels" :key="ch.id">
                <td><span class="channel-type">{{ ch.type }}</span></td>
                <td>{{ ch.name }}</td>
                <td>
                  <span class="status-dot" :class="ch.is_active ? 'dot-on' : 'dot-off'" />
                  {{ ch.is_active ? 'Active' : 'Inactive' }}
                </td>
                <td class="date-cell">{{ formatDate(ch.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Billing -->
        <div v-if="activeTab === 'billing'" class="tab-panel">
          <h3 class="section-title">Invoices</h3>
          <div v-if="invoicesLoading" class="skeleton-list">
            <div v-for="n in 3" :key="n" class="skeleton-row" />
          </div>
          <div v-else-if="invoices.length === 0" class="empty-state">
            <p>No invoices</p>
          </div>
          <table v-else class="data-table">
            <thead>
              <tr><th>Amount</th><th>Status</th><th>Due Date</th><th>Paid</th></tr>
            </thead>
            <tbody>
              <tr v-for="inv in invoices" :key="inv.id">
                <td class="mono">${{ inv.amount_usd?.toFixed(2) }}</td>
                <td>
                  <span class="status-badge" :class="`status-${inv.status}`">{{ inv.status }}</span>
                </td>
                <td class="date-cell">{{ formatDate(inv.due_date) }}</td>
                <td class="date-cell">{{ inv.paid_at ? formatDate(inv.paid_at) : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Settings -->
        <div v-if="activeTab === 'settings'" class="tab-panel">
          <div class="settings-form">
            <div class="form-group">
              <label>Organisation Name</label>
              <input v-model="form.name" class="form-input" />
            </div>
            <div class="form-group">
              <label>Slug</label>
              <input v-model="form.slug" class="form-input" disabled />
            </div>
            <div class="form-group">
              <label>Domain</label>
              <input v-model="form.domain" class="form-input" placeholder="example.com" />
            </div>
            <div class="form-group">
              <label>Primary Color</label>
              <div class="color-row">
                <input v-model="form.primary_color" type="color" class="color-picker" />
                <span class="mono">{{ form.primary_color }}</span>
              </div>
            </div>
            <button class="btn btn-primary" :disabled="saving" @click="saveSettings">
              {{ saving ? 'Saving...' : 'Save Settings' }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../../shared/composables/useApi'

const route = useRoute()
const router = useRouter()
const api = useApi()

const tenantId = computed(() => route.params.id as string)

interface Tab {
  key: string
  label: string
}

const tabs: Tab[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'users', label: 'Users' },
  { key: 'channels', label: 'Channels' },
  { key: 'billing', label: 'Billing' },
  { key: 'settings', label: 'Settings' },
]

const loading = ref(true)
const error = ref('')
const activeTab = ref('overview')
const saving = ref(false)
const tenant = ref<any>(null)

const overview = reactive({ users: 0, channels: 0, aiRequests: 0, storage: '0 MB' })
const users = ref<any[]>([])
const channels = ref<any[]>([])
const invoices = ref<any[]>([])
const usersLoading = ref(false)
const channelsLoading = ref(false)
const invoicesLoading = ref(false)

const form = reactive({ name: '', slug: '', domain: '', primary_color: '#1a73e8' })

function formatDate(date: string): string {
  return new Date(date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

async function loadTenant() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get(`/tenants/${tenantId.value}`)
    tenant.value = data
    form.name = data.name
    form.slug = data.slug
    form.domain = data.domain || ''
    form.primary_color = data.primary_color || '#1a73e8'
    overview.users = data.users_count || 0
    overview.channels = data.channels_count || 0
    overview.aiRequests = data.ai_requests_30d || 0
    overview.storage = data.storage_used || '0 MB'
  } catch (e: any) {
    error.value = e?.message || 'Failed to load tenant'
  } finally {
    loading.value = false
  }
}

async function loadUsers() {
  usersLoading.value = true
  try {
    const { data } = await api.get(`/tenants/${tenantId.value}/users`)
    users.value = data.items || data || []
  } catch (e: unknown) {
    console.error('[TenantDetailView] Failed to load tenant users', tenantId.value, e)
    users.value = []
  }
  finally { usersLoading.value = false }
}

async function loadChannels() {
  channelsLoading.value = true
  try {
    const { data } = await api.get(`/tenants/${tenantId.value}/channels`)
    channels.value = data.items || data || []
  } catch (e: unknown) {
    console.error('[TenantDetailView] Failed to load tenant channels', tenantId.value, e)
    channels.value = []
  }
  finally { channelsLoading.value = false }
}

async function loadInvoices() {
  invoicesLoading.value = true
  try {
    const { data } = await api.get(`/billing/invoices?tenant_id=${tenantId.value}`)
    invoices.value = data.items || data || []
  } catch (e: unknown) {
    console.error('[TenantDetailView] Failed to load tenant invoices', tenantId.value, e)
    invoices.value = []
  }
  finally { invoicesLoading.value = false }
}

async function toggleStatus() {
  try {
    const action = tenant.value.is_active ? 'suspend' : 'activate'
    await api.post(`/tenants/${tenantId.value}/${action}`)
    tenant.value.is_active = !tenant.value.is_active
  } catch (e: unknown) {
    console.error('[TenantDetailView] Tenant status toggle failed', tenantId.value, e)
  }
}

async function confirmDelete() {
  if (!confirm(`Delete tenant "${tenant.value.name}"? This action cannot be undone.`)) return
  try {
    await api.delete(`/tenants/${tenantId.value}`)
    router.push('/admin/tenants')
  } catch (e: unknown) {
    console.error('[TenantDetailView] Failed to delete tenant', tenantId.value, e)
  }
}

async function saveSettings() {
  saving.value = true
  try {
    await api.patch(`/tenants/${tenantId.value}`, {
      name: form.name,
      domain: form.domain || null,
      primary_color: form.primary_color,
    })
    tenant.value.name = form.name
  } catch (e: unknown) {
    console.error('[TenantDetailView] Failed to save tenant settings', tenantId.value, e)
  } finally { saving.value = false }
}

watch(activeTab, (tab) => {
  if (tab === 'users' && users.value.length === 0) loadUsers()
  if (tab === 'channels' && channels.value.length === 0) loadChannels()
  if (tab === 'billing' && invoices.value.length === 0) loadInvoices()
})

onMounted(loadTenant)
</script>

<style scoped>
.tenant-detail { display: flex; flex-direction: column; gap: var(--space-lg); }

.detail-header { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: var(--space-md); }
.header-left { display: flex; flex-direction: column; gap: var(--space-sm); }
.header-info { display: flex; align-items: center; gap: var(--space-md); }
.org-avatar { width: 48px; height: 48px; border-radius: var(--radius-md); background: var(--color-primary); color: #fff; display: flex; align-items: center; justify-content: center; font-size: var(--font-xl); font-weight: 700; }
.org-slug { font-size: var(--font-sm); color: var(--color-on-surface-variant); font-family: var(--mono); }
.header-right { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }

.btn {
  display: inline-flex; align-items: center; gap: var(--space-xs);
  padding: 6px 16px; border: none; border-radius: var(--radius-sm);
  font-size: var(--font-sm); font-weight: 500; cursor: pointer;
}
.btn-primary { background: var(--color-primary); color: #fff; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-ghost { background: transparent; color: var(--color-on-surface-variant); }
.btn-ghost:hover { background: var(--color-primary-light); }
.btn-sm { padding: 4px 12px; font-size: var(--font-xs); }
.btn-warning { background: var(--color-warning); color: #202124; }
.btn-success { background: var(--color-success); color: #fff; }
.btn-danger { background: var(--color-error); color: #fff; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.back-btn { align-self: flex-start; }

.status-badge, .plan-badge {
  display: inline-block; padding: 2px 10px; border-radius: var(--radius-full);
  font-size: var(--font-xs); font-weight: 600;
}
.status-active { background: var(--color-success-light); color: var(--color-success); }
.status-suspended { background: var(--color-warning-light); color: var(--color-warning); }
.plan-badge { background: var(--color-info-light); color: var(--color-info); }

.tabs { display: flex; gap: var(--space-xs); border-bottom: 2px solid var(--color-outline); }
.tab-btn {
  padding: var(--space-sm) var(--space-lg); border: none; background: none;
  font-size: var(--font-md); font-weight: 500; color: var(--color-on-surface-variant);
  cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px;
  transition: all 0.15s;
}
.tab-btn:hover { color: var(--color-on-surface); }
.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }

.tab-content { min-height: 200px; }
.tab-panel { padding-top: var(--space-lg); }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-md); }
.stat-card {
  background: var(--color-surface); border: 1px solid var(--color-outline);
  border-radius: var(--radius-md); padding: var(--space-lg); text-align: center;
}
.stat-label { display: block; font-size: var(--font-sm); color: var(--color-on-surface-variant); margin-bottom: var(--space-xs); }
.stat-value { display: block; font-size: var(--font-2xl); font-weight: 700; color: var(--color-on-surface); }

.section-title { font-size: var(--font-lg); font-weight: 600; margin-bottom: var(--space-md); }

.data-table { width: 100%; border-collapse: collapse; font-size: var(--font-md); background: var(--color-surface); border: 1px solid var(--color-outline); border-radius: var(--radius-md); overflow: hidden; }
.data-table th { text-align: left; padding: var(--space-sm) var(--space-lg); font-weight: 600; font-size: var(--font-xs); text-transform: uppercase; letter-spacing: 0.5px; color: var(--color-on-surface-variant); border-bottom: 1px solid var(--color-outline); background: var(--color-surface-variant); }
.data-table td { padding: var(--space-sm) var(--space-lg); border-bottom: 1px solid var(--color-outline); }
.data-table tbody tr:last-child td { border-bottom: none; }

.user-cell { display: flex; align-items: center; gap: var(--space-sm); }
.user-avatar { width: 28px; height: 28px; border-radius: 50%; background: var(--color-primary-light); color: var(--color-primary); display: flex; align-items: center; justify-content: center; font-size: var(--font-xs); font-weight: 600; }
.role-badge { font-size: var(--font-xs); padding: 1px 8px; border-radius: var(--radius-full); background: var(--color-surface-variant); color: var(--color-on-surface-variant); }
.channel-type { text-transform: capitalize; font-weight: 500; }
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }
.dot-on { background: var(--color-success); }
.dot-off { background: var(--color-outline); }

.date-cell { white-space: nowrap; color: var(--color-on-surface-variant); font-size: var(--font-sm); }
.mono { font-family: var(--mono); font-size: var(--font-sm); }

/* Settings */
.settings-form { max-width: 480px; display: flex; flex-direction: column; gap: var(--space-md); }
.form-group { display: flex; flex-direction: column; gap: var(--space-xs); }
.form-group label { font-size: var(--font-sm); font-weight: 500; color: var(--color-on-surface-variant); }
.form-input { padding: 8px 12px; border: 1px solid var(--color-outline); border-radius: var(--radius-sm); font-size: var(--font-md); outline: none; color: var(--color-on-surface); background: var(--color-surface); }
.form-input:focus { border-color: var(--color-primary); }
.form-input:disabled { background: var(--color-surface-variant); color: var(--color-on-surface-variant); }
.color-row { display: flex; align-items: center; gap: var(--space-sm); }
.color-picker { width: 36px; height: 36px; border: 1px solid var(--color-outline); border-radius: var(--radius-sm); cursor: pointer; padding: 2px; }

/* Skeleton */
.skeleton-header { height: 80px; background: var(--color-surface); border-radius: var(--radius-md); animation: pulse 1.5s ease-in-out infinite; }
.skeleton-tabs { height: 44px; background: var(--color-surface); border-radius: var(--radius-sm); margin-top: var(--space-md); animation: pulse 1.5s ease-in-out infinite; animation-delay: 0.1s; }
.skeleton-content { height: 300px; background: var(--color-surface); border-radius: var(--radius-md); margin-top: var(--space-md); animation: pulse 1.5s ease-in-out infinite; animation-delay: 0.2s; }
.skeleton-list { display: flex; flex-direction: column; gap: var(--space-sm); }
.skeleton-row { height: 40px; background: var(--color-surface); border-radius: var(--radius-sm); animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.loading-state { display: flex; flex-direction: column; gap: var(--space-md); }
.empty-state { display: flex; align-items: center; justify-content: center; padding: var(--space-3xl); color: var(--color-on-surface-variant); }
.error-state { display: flex; flex-direction: column; align-items: center; gap: var(--space-md); padding: var(--space-3xl); color: var(--color-error); }

@media (max-width: 1024px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .detail-header { flex-direction: column; }
  .header-right { width: 100%; }
  .stats-grid { grid-template-columns: 1fr; }
}
</style>
