<template>
  <div class="tenants-list">
    <div class="page-header">
      <h1>Tenants</h1>
      <button class="btn btn-primary" @click="openCreate">
        <span class="btn-icon">+</span> Create Tenant
      </button>
    </div>

    <!-- Filters -->
    <div class="filters-bar">
      <div class="search-wrap">
        <span class="search-icon">🔍</span>
        <input
          v-model="search"
          class="search-input"
          placeholder="Search by name or slug..."
          @input="onSearchInput"
        />
      </div>
      <select v-model="statusFilter" class="filter-select" @change="loadTenants">
        <option value="">All Statuses</option>
        <option value="active">Active</option>
        <option value="trial">Trial</option>
        <option value="suspended">Suspended</option>
        <option value="cancelled">Cancelled</option>
      </select>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-state">
      <LoadingSpinner text="Loading tenants..." />
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="btn btn-primary" @click="loadTenants">Retry</button>
    </div>

    <!-- Empty state -->
    <div v-else-if="tenants.length === 0" class="empty-state">
      <span class="empty-icon">🏢</span>
      <h3>No tenants found</h3>
      <p v-if="search || statusFilter">Try adjusting your filters</p>
      <p v-else>Create your first tenant to get started</p>
    </div>

    <!-- Table -->
    <template v-else>
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Org Name</th>
              <th>Slug</th>
              <th>Plan</th>
              <th>Users</th>
              <th>Channels</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="tenant in tenants"
              :key="tenant.id"
              class="table-row"
              @click="goToTenant(tenant.id)"
            >
              <td>
                <div class="org-cell">
                  <div class="org-avatar">{{ tenant.name.charAt(0).toUpperCase() }}</div>
                  <span class="org-name">{{ tenant.name }}</span>
                </div>
              </td>
              <td class="mono">{{ tenant.slug }}</td>
              <td>{{ tenant.plan || '—' }}</td>
              <td>{{ tenant.users ?? '—' }}</td>
              <td>{{ tenant.channels ?? '—' }}</td>
              <td>
                <span class="status-badge" :class="`status-${tenant.is_active ? 'active' : 'suspended'}`">
                  {{ tenant.is_active ? 'Active' : 'Suspended' }}
                </span>
              </td>
              <td class="date-cell">{{ formatDate(tenant.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="pagination">
        <button
          class="btn btn-ghost btn-sm"
          :disabled="page <= 1"
          @click="changePage(page - 1)"
        >
          ← Prev
        </button>
        <span class="page-info">Page {{ page }} of {{ totalPages }}</span>
        <button
          class="btn btn-ghost btn-sm"
          :disabled="page >= totalPages"
          @click="changePage(page + 1)"
        >
          Next →
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../../shared/composables/useApi'
import LoadingSpinner from '../../shared/components/LoadingSpinner.vue'

const router = useRouter()
const api = useApi()

const loading = ref(true)
const error = ref('')
const search = ref('')
const statusFilter = ref('')
const page = ref(1)
const total = ref(0)
const pageSize = 20
const tenants = ref<any[]>([])

let searchTimer: ReturnType<typeof setTimeout> | null = null

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

function formatDate(date: string): string {
  return new Date(date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

function goToTenant(id: string) {
  router.push(`/admin/tenants/${id}`)
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; loadTenants() }, 300)
}

function changePage(p: number) {
  page.value = p
  loadTenants()
}

async function loadTenants() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize }
    if (search.value) params.search = search.value
    if (statusFilter.value) params.status = statusFilter.value
    const { data } = await api.get('/tenants', { params })
    tenants.value = data.items || []
    total.value = data.total || 0
  } catch (e: any) {
    error.value = e?.message || 'Failed to load tenants'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  router.push('/admin/tenants/new')
}

onMounted(loadTenants)
</script>

<style scoped>
.tenants-list { display: flex; flex-direction: column; gap: var(--space-lg); }

.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-header h1 { font-size: var(--font-2xl); font-weight: 700; color: var(--color-on-surface); }

.btn { display: inline-flex; align-items: center; gap: var(--space-xs); padding: 8px 20px; border: none; border-radius: var(--radius-sm); font-size: var(--font-md); font-weight: 500; cursor: pointer; }
.btn-primary { background: var(--color-primary); color: #fff; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-ghost { background: transparent; color: var(--color-on-surface-variant); }
.btn-ghost:hover:not(:disabled) { background: var(--color-primary-light); }
.btn-sm { padding: 4px 12px; font-size: var(--font-sm); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-icon { font-size: 18px; line-height: 1; }

.filters-bar { display: flex; gap: var(--space-md); flex-wrap: wrap; }
.search-wrap { display: flex; align-items: center; background: var(--color-surface); border: 1px solid var(--color-outline); border-radius: var(--radius-sm); padding: 0 var(--space-sm); flex: 1; min-width: 200px; }
.search-icon { font-size: 14px; color: var(--color-on-surface-variant); }
.search-input { border: none; background: transparent; padding: 8px 8px; font-size: var(--font-md); flex: 1; outline: none; color: var(--color-on-surface); }
.filter-select { padding: 8px 12px; border: 1px solid var(--color-outline); border-radius: var(--radius-sm); background: var(--color-surface); font-size: var(--font-md); color: var(--color-on-surface); cursor: pointer; }

.table-wrapper { overflow-x: auto; border: 1px solid var(--color-outline); border-radius: var(--radius-md); background: var(--color-surface); }
.data-table { width: 100%; border-collapse: collapse; font-size: var(--font-md); }
.data-table th { text-align: left; padding: var(--space-sm) var(--space-lg); font-weight: 600; font-size: var(--font-xs); text-transform: uppercase; letter-spacing: 0.5px; color: var(--color-on-surface-variant); border-bottom: 1px solid var(--color-outline); background: var(--color-surface-variant); }
.data-table td { padding: var(--space-sm) var(--space-lg); border-bottom: 1px solid var(--color-outline); color: var(--color-on-surface); }
.data-table tbody tr:last-child td { border-bottom: none; }
.table-row { cursor: pointer; transition: background 0.1s; }
.table-row:hover { background: var(--color-primary-light); }

.org-cell { display: flex; align-items: center; gap: var(--space-sm); }
.org-avatar { width: 32px; height: 32px; border-radius: var(--radius-sm); background: var(--color-primary); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: var(--font-md); }
.org-name { font-weight: 500; }
.mono { font-family: var(--mono); font-size: var(--font-sm); }

.status-badge { display: inline-block; padding: 2px 10px; border-radius: var(--radius-full); font-size: var(--font-xs); font-weight: 600; }
.status-active { background: var(--color-success-light); color: var(--color-success); }
.status-suspended { background: var(--color-warning-light); color: var(--color-warning); }
.status-trial { background: var(--color-info-light); color: var(--color-info); }
.status-cancelled { background: var(--color-error-light); color: var(--color-error); }

.date-cell { white-space: nowrap; color: var(--color-on-surface-variant); }

.pagination { display: flex; align-items: center; justify-content: center; gap: var(--space-md); padding: var(--space-md) 0; }
.page-info { font-size: var(--font-sm); color: var(--color-on-surface-variant); }

.table-skeleton { display: flex; flex-direction: column; gap: var(--space-sm); }
.skeleton-row { height: 44px; background: var(--color-surface); border-radius: var(--radius-sm); animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.empty-state { display: flex; flex-direction: column; align-items: center; padding: var(--space-3xl); gap: var(--space-sm); color: var(--color-on-surface-variant); }
.empty-icon { font-size: 48px; }
.empty-state h3 { font-size: var(--font-lg); color: var(--color-on-surface); }

.error-state { display: flex; flex-direction: column; align-items: center; gap: var(--space-md); padding: var(--space-3xl); color: var(--color-error); }
.loading-state { display: flex; align-items: center; justify-content: center; min-height: 300px; }
</style>
