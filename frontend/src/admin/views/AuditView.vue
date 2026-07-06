<template>
  <div class="audit">
    <div class="page-header">
      <h1>Audit Log</h1>
    </div>

    <!-- Filters -->
    <div class="filters-bar">
      <div class="search-wrap">
        <span class="search-icon">🔍</span>
        <input
          v-model="filters.tenant"
          class="search-input"
          placeholder="Filter by tenant..."
          @input="onFilterChange"
        >
      </div>
      <select
        v-model="filters.eventType"
        class="filter-select"
        @change="onFilterChange"
      >
        <option value="">
          All Events
        </option>
        <option value="tenant_created">
          Tenant Created
        </option>
        <option value="tenant_deleted">
          Tenant Deleted
        </option>
        <option value="user_invited">
          User Invited
        </option>
        <option value="subscription_updated">
          Subscription Updated
        </option>
        <option value="driver_added">
          Driver Added
        </option>
        <option value="channel_connected">
          Channel Connected
        </option>
        <option value="billing_invoice">
          Billing Invoice
        </option>
        <option value="system_alert">
          System Alert
        </option>
        <option value="login">
          Login
        </option>
      </select>
      <input
        v-model="filters.dateFrom"
        type="date"
        class="filter-date"
        @change="onFilterChange"
      >
      <span class="date-sep">to</span>
      <input
        v-model="filters.dateTo"
        type="date"
        class="filter-date"
        @change="onFilterChange"
      >
    </div>

    <!-- Loading -->
    <div
      v-if="loading"
      class="table-skeleton"
    >
      <div
        v-for="n in 10"
        :key="n"
        class="skeleton-row"
        :style="{ animationDelay: `${n * 60}ms` }"
      />
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="error-state"
    >
      <p>{{ error }}</p>
      <button
        class="btn btn-primary"
        @click="loadEntries"
      >
        Retry
      </button>
    </div>

    <!-- Empty -->
    <div
      v-else-if="entries.length === 0"
      class="empty-state"
    >
      <span class="empty-icon">📋</span>
      <h3>No audit entries found</h3>
      <p v-if="hasFilters">
        Try adjusting your filters
      </p>
      <p v-else>
        Events will appear here as they occur
      </p>
    </div>

    <!-- Table -->
    <template v-else>
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Event Type</th>
              <th>Tenant</th>
              <th>User</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in entries"
              :key="entry.id"
            >
              <td class="date-cell">
                {{ formatTimestamp(entry.created_at) }}
              </td>
              <td>
                <span
                  class="event-badge"
                  :class="`event-${eventStyle(entry.event_type)}`"
                >
                  {{ entry.event_type }}
                </span>
              </td>
              <td>{{ entry.tenant_name || entry.tenant_id || 'System' }}</td>
              <td>{{ entry.user_email || entry.user_id || '—' }}</td>
              <td>
                <button
                  class="details-toggle"
                  @click="toggleDetails(entry.id)"
                >
                  {{ expanded.has(entry.id) ? 'Hide' : 'View' }} Details
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Expanded rows -->
      <div
        v-for="entry in entries"
        :key="'details-' + entry.id"
      >
        <div
          v-if="expanded.has(entry.id)"
          class="details-panel"
        >
          <pre class="details-json">{{ formatJSON(entry.details || entry) }}</pre>
        </div>
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
        <span class="page-info">Page {{ page }} of {{ totalPages }} ({{ total }} entries)</span>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useApi } from '../../shared/composables/useApi'

const api = useApi()

const loading = ref(true)
const error = ref('')
const entries = ref<any[]>([])
const expanded = ref(new Set<string>())
const page = ref(1)
const total = ref(0)
const pageSize = 50

const filters = reactive({
  tenant: '',
  eventType: '',
  dateFrom: '',
  dateTo: '',
})

let filterTimer: ReturnType<typeof setTimeout> | null = null

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const hasFilters = computed(() => filters.tenant !== '' || filters.eventType !== '' || filters.dateFrom !== '' || filters.dateTo !== '')

function formatTimestamp(ts: string): string {
  const d = new Date(ts)
  return d.toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function formatJSON(obj: any): string {
  try {
    return JSON.stringify(obj, null, 2)
  } catch (e) {
    console.error('AuditView: JSON stringify failed', e)
    return String(obj)
  }
}

function eventStyle(event: string): string {
  if (!event) return 'default'
  if (event.includes('tenant')) return 'tenant'
  if (event.includes('user')) return 'user'
  if (event.includes('subscription') || event.includes('billing')) return 'billing'
  if (event.includes('driver')) return 'driver'
  if (event.includes('channel')) return 'channel'
  if (event.includes('login')) return 'login'
  if (event.includes('alert') || event.includes('error')) return 'alert'
  return 'default'
}

function toggleDetails(id: string) {
  if (expanded.value.has(id)) {
    expanded.value.delete(id)
  } else {
    expanded.value.add(id)
  }
  // Force reactivity
  expanded.value = new Set(expanded.value)
}

function onFilterChange() {
  if (filterTimer) clearTimeout(filterTimer)
  filterTimer = setTimeout(() => { page.value = 1; loadEntries() }, 300)
}

function changePage(p: number) {
  page.value = p
  loadEntries()
}

async function loadEntries() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize,
    }
    if (filters.tenant) params['tenant'] = filters.tenant
    if (filters.eventType) params['event_type'] = filters.eventType
    if (filters.dateFrom) params['date_from'] = filters.dateFrom
    if (filters.dateTo) params['date_to'] = filters.dateTo

    const { data } = await api.get('/admin/audit', { params })
    entries.value = data.items || []
    total.value = data.total || 0
  } catch (e: unknown) {
    error.value = (e as { message?: string })?.message || 'Failed to load audit entries'
    console.error('[AuditView] Failed to load audit entries', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadEntries)
</script>

<style scoped>
.audit { display: flex; flex-direction: column; gap: var(--space-lg); }

.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-header h1 { font-size: var(--font-2xl); font-weight: 700; color: var(--color-on-surface); }

.filters-bar { display: flex; gap: var(--space-sm); flex-wrap: wrap; align-items: center; }
.search-wrap { display: flex; align-items: center; background: var(--color-surface); border: 1px solid var(--color-outline); border-radius: var(--radius-sm); padding: 0 var(--space-sm); flex: 1; min-width: 180px; }
.search-icon { font-size: 14px; color: var(--color-on-surface-variant); }
.search-input { border: none; background: transparent; padding: 8px 8px; font-size: var(--font-md); flex: 1; outline: none; color: var(--color-on-surface); }
.filter-select { padding: 8px 12px; border: 1px solid var(--color-outline); border-radius: var(--radius-sm); background: var(--color-surface); font-size: var(--font-md); color: var(--color-on-surface); cursor: pointer; }
.filter-date { padding: 7px 12px; border: 1px solid var(--color-outline); border-radius: var(--radius-sm); background: var(--color-surface); font-size: var(--font-md); color: var(--color-on-surface); }
.date-sep { color: var(--color-on-surface-variant); font-size: var(--font-sm); }

.table-wrapper { overflow-x: auto; border: 1px solid var(--color-outline); border-radius: var(--radius-md); background: var(--color-surface); }
.data-table { width: 100%; border-collapse: collapse; font-size: var(--font-sm); }
.data-table th { text-align: left; padding: var(--space-sm) var(--space-md); font-weight: 600; font-size: var(--font-xs); text-transform: uppercase; letter-spacing: 0.5px; color: var(--color-on-surface-variant); border-bottom: 1px solid var(--color-outline); background: var(--color-surface-variant); white-space: nowrap; }
.data-table td { padding: var(--space-sm) var(--space-md); border-bottom: 1px solid var(--color-outline); color: var(--color-on-surface); }
.data-table tbody tr:last-child td { border-bottom: none; }
.data-table tbody tr:hover { background: var(--color-surface-variant); }

.date-cell { white-space: nowrap; color: var(--color-on-surface-variant); font-family: var(--mono); font-size: var(--font-xs); }

.event-badge { display: inline-block; padding: 2px 8px; border-radius: var(--radius-full); font-size: var(--font-xs); font-weight: 600; text-transform: capitalize; white-space: nowrap; }
.event-tenant { background: var(--color-info-light); color: var(--color-info); }
.event-user { background: var(--color-primary-light); color: var(--color-primary); }
.event-billing { background: var(--color-success-light); color: var(--color-success); }
.event-driver { background: var(--color-surface-variant); color: var(--color-on-surface-variant); }
.event-channel { background: var(--color-warning-light); color: var(--color-warning); }
.event-login { background: var(--color-primary-light); color: var(--color-primary); }
.event-alert { background: var(--color-error-light); color: var(--color-error); }
.event-default { background: var(--color-surface-variant); color: var(--color-on-surface-variant); }

.details-toggle {
  background: none; border: 1px solid var(--color-outline); padding: 2px 10px;
  border-radius: var(--radius-sm); font-size: var(--font-xs); cursor: pointer;
  color: var(--color-primary); font-weight: 500;
}
.details-toggle:hover { background: var(--color-primary-light); }

.details-panel {
  background: var(--color-surface-variant);
  border: 1px solid var(--color-outline);
  border-top: none; border-radius: 0 0 var(--radius-md) var(--radius-md);
  padding: var(--space-md);
  margin-top: -1px;
}
.details-json {
  font-family: var(--mono); font-size: var(--font-xs); white-space: pre-wrap;
  word-break: break-all; color: var(--color-on-surface);
  max-height: 300px; overflow-y: auto; margin: 0;
}

.pagination { display: flex; align-items: center; justify-content: center; gap: var(--space-md); padding: var(--space-md) 0; }
.page-info { font-size: var(--font-sm); color: var(--color-on-surface-variant); }

.btn { display: inline-flex; align-items: center; gap: var(--space-xs); padding: 6px 16px; border: none; border-radius: var(--radius-sm); font-size: var(--font-sm); font-weight: 500; cursor: pointer; }
.btn-primary { background: var(--color-primary); color: #fff; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-ghost { background: transparent; color: var(--color-on-surface-variant); }
.btn-ghost:hover:not(:disabled) { background: var(--color-primary-light); }
.btn-sm { padding: 4px 12px; font-size: var(--font-xs); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }

.table-skeleton { display: flex; flex-direction: column; gap: var(--space-xs); }
.skeleton-row { height: 40px; background: var(--color-surface); border-radius: var(--radius-sm); animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.empty-state { display: flex; flex-direction: column; align-items: center; padding: var(--space-3xl); gap: var(--space-sm); color: var(--color-on-surface-variant); }
.empty-icon { font-size: 48px; }
.empty-state h3 { font-size: var(--font-lg); color: var(--color-on-surface); }

.error-state { display: flex; flex-direction: column; align-items: center; gap: var(--space-md); padding: var(--space-3xl); color: var(--color-error); }
</style>
