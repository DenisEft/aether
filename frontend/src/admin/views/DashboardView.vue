<template>
  <div class="dashboard">
    <!-- Loading skeleton -->
    <template v-if="loading">
      <div class="stats-row">
        <div v-for="n in 4" :key="n" class="skeleton-card" />
      </div>
      <div class="skeleton-card health-skeleton" />
      <div class="skeleton-card feed-skeleton" />
    </template>

    <!-- Error state -->
    <div v-else-if="error" class="error-state">
      <div class="error-icon">⚠️</div>
      <h2>Failed to load dashboard</h2>
      <p class="error-message">{{ error }}</p>
      <button class="btn btn-primary" @click="loadAll">Retry</button>
    </div>

    <!-- Content -->
    <template v-else>
      <!-- Stats row -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-card__icon stat-card__icon--tenants">🏢</div>
          <div class="stat-card__content">
            <span class="stat-card__label">Total Tenants</span>
            <span class="stat-card__value">{{ stats.totalTenants }}</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-card__icon stat-card__icon--users">👥</div>
          <div class="stat-card__content">
            <span class="stat-card__label">Active Users</span>
            <span class="stat-card__value">{{ stats.activeUsers }}</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-card__icon stat-card__icon--ai">🤖</div>
          <div class="stat-card__content">
            <span class="stat-card__label">AI Requests Today</span>
            <span class="stat-card__value">{{ stats.aiRequestsToday.toLocaleString() }}</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-card__icon stat-card__icon--revenue">💰</div>
          <div class="stat-card__content">
            <span class="stat-card__label">Revenue MTD</span>
            <span class="stat-card__value">${{ stats.revenueMTD.toLocaleString() }}</span>
          </div>
        </div>
      </div>

      <!-- System Health + Quick Actions row -->
      <div class="dashboard-grid">
        <div class="card health-card">
          <h3 class="card-title">System Health</h3>
          <div class="health-list">
            <div class="health-item">
              <span class="health-label">Backend</span>
              <span class="health-dot" :class="health.backend" />
            </div>
            <div class="health-item">
              <span class="health-label">Database</span>
              <span class="health-value">{{ health.dbLatencyMs }}ms</span>
              <span class="health-dot" :class="health.db" />
            </div>
            <div class="health-item">
              <span class="health-label">Redis</span>
              <span class="health-dot" :class="health.redis" />
            </div>
            <div class="health-item">
              <span class="health-label">Celery Workers</span>
              <span class="health-value">{{ health.celeryWorkers }} active</span>
              <span class="health-dot" :class="health.celery" />
            </div>
          </div>
        </div>

        <div class="card actions-card">
          <h3 class="card-title">Quick Actions</h3>
          <div class="actions-list">
            <router-link to="/admin/tenants" class="action-item">
              <span class="action-icon">🏢</span>
              <div>
                <span class="action-label">Create Tenant</span>
                <span class="action-sub">Onboard a new organisation</span>
              </div>
            </router-link>
            <router-link to="/admin/audit" class="action-item">
              <span class="action-icon">📋</span>
              <div>
                <span class="action-label">View Audit Log</span>
                <span class="action-sub">Review system activity</span>
              </div>
            </router-link>
            <router-link to="/admin/drivers" class="action-item">
              <span class="action-icon">⚙️</span>
              <div>
                <span class="action-label">Manage Drivers</span>
                <span class="action-sub">Configure AI inference drivers</span>
              </div>
            </router-link>
          </div>
        </div>
      </div>

      <!-- Recent activity -->
      <div class="card activity-card">
        <h3 class="card-title">Recent Activity</h3>
        <div v-if="activities.length === 0" class="empty-state">
          <span class="empty-icon">📭</span>
          <p>No recent activity</p>
        </div>
        <div v-else class="activity-list">
          <div v-for="act in activities" :key="act.id" class="activity-item">
            <span class="activity-icon">{{ eventIcon(act.event) }}</span>
            <div class="activity-content">
              <span class="activity-event">{{ act.event }}</span>
              <span class="activity-tenant">{{ act.tenant }}</span>
              <span class="activity-user">{{ act.user }}</span>
            </div>
            <span class="activity-time">{{ formatTime(act.timestamp) }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../shared/composables/useApi'

interface Activity {
  id: string
  event: string
  tenant: string
  user: string
  timestamp: string
}

interface Stats {
  totalTenants: number
  activeUsers: number
  aiRequestsToday: number
  revenueMTD: number
}

interface Health {
  backend: string
  db: string
  dbLatencyMs: number
  redis: string
  celery: string
  celeryWorkers: number
}

const loading = ref(true)
const error = ref('')

const stats = ref<Stats>({ totalTenants: 0, activeUsers: 0, aiRequestsToday: 0, revenueMTD: 0 })
const health = ref<Health>({ backend: 'ok', db: 'ok', dbLatencyMs: 0, redis: 'ok', celery: 'ok', celeryWorkers: 0 })
const activities = ref<Activity[]>([])

const eventIcons: Record<string, string> = {
  tenant_created: '🏢',
  user_invited: '👤',
  subscription_updated: '💳',
  driver_added: '⚙️',
  channel_connected: '🔗',
  billing_invoice: '🧾',
  system_alert: '🔔',
}

function eventIcon(event: string): string {
  return eventIcons[event] || '📌'
}

function formatTime(ts: string): string {
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`
  return d.toLocaleDateString()
}

function healthClass(status: string): string {
  if (status === 'ok') return 'health-ok'
  if (status === 'degraded') return 'health-warn'
  return 'health-err'
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const api = useApi()
    const [statsRes, healthRes, activityRes] = await Promise.all([
      api.get('/admin/stats'),
      api.get('/health'),
      api.get('/admin/activity?limit=10'),
    ])
    stats.value = statsRes.data
    health.value = {
      backend: healthRes.data.status || 'ok',
      db: healthRes.data.db?.status || 'ok',
      dbLatencyMs: healthRes.data.db?.latency_ms || 0,
      redis: healthRes.data.redis?.status || 'ok',
      celery: healthRes.data.celery?.status || 'ok',
      celeryWorkers: healthRes.data.celery?.workers || 0,
    }
    activities.value = activityRes.data.items || []
  } catch (e: any) {
    error.value = e?.message || 'Could not load dashboard data'
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: var(--space-xl); }

/* Stats row */
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-lg); }
.stat-card {
  display: flex; align-items: center; gap: var(--space-md);
  background: var(--color-surface); border: 1px solid var(--color-outline);
  border-radius: var(--radius-md); padding: var(--space-lg);
  box-shadow: var(--shadow-sm);
}
.stat-card__icon { font-size: 28px; line-height: 1; }
.stat-card__content { display: flex; flex-direction: column; }
.stat-card__label { font-size: var(--font-sm); color: var(--color-on-surface-variant); }
.stat-card__value { font-size: var(--font-2xl); font-weight: 700; color: var(--color-on-surface); }

/* Dashboard grid */
.dashboard-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-lg); }
.card {
  background: var(--color-surface); border: 1px solid var(--color-outline);
  border-radius: var(--radius-md); padding: var(--space-lg); box-shadow: var(--shadow-sm);
}
.card-title { font-size: var(--font-lg); font-weight: 600; margin-bottom: var(--space-md); color: var(--color-on-surface); }

/* Health */
.health-list { display: flex; flex-direction: column; gap: var(--space-sm); }
.health-item { display: flex; align-items: center; gap: var(--space-sm); font-size: var(--font-md); }
.health-label { flex: 1; color: var(--color-on-surface-variant); }
.health-value { font-size: var(--font-sm); color: var(--color-on-surface-variant); }
.health-dot { width: 10px; height: 10px; border-radius: 50%; }
.health-dot.ok { background: var(--color-success); }
.health-dot.degraded, .health-dot.warn { background: var(--color-warning); }
.health-dot.down, .health-dot.error, .health-dot.err { background: var(--color-error); }

/* Actions */
.actions-list { display: flex; flex-direction: column; gap: var(--space-sm); }
.action-item {
  display: flex; align-items: center; gap: var(--space-md); padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm); transition: background 0.15s; color: var(--color-on-surface); text-decoration: none;
}
.action-item:hover { background: var(--color-primary-light); text-decoration: none; }
.action-icon { font-size: 20px; }
.action-label { display: block; font-weight: 500; font-size: var(--font-md); }
.action-sub { display: block; font-size: var(--font-xs); color: var(--color-on-surface-variant); }

/* Activity */
.activity-card { margin-top: 0; }
.activity-list { display: flex; flex-direction: column; }
.activity-item { display: flex; align-items: center; gap: var(--space-md); padding: var(--space-sm) 0; border-bottom: 1px solid var(--color-outline); }
.activity-item:last-child { border-bottom: none; }
.activity-icon { font-size: 18px; flex-shrink: 0; }
.activity-content { flex: 1; display: flex; flex-wrap: wrap; gap: var(--space-xs) var(--space-sm); font-size: var(--font-sm); }
.activity-event { font-weight: 500; color: var(--color-on-surface); }
.activity-tenant, .activity-user { color: var(--color-on-surface-variant); }
.activity-time { font-size: var(--font-xs); color: var(--color-on-surface-variant); white-space: nowrap; }

/* Empty */
.empty-state { display: flex; flex-direction: column; align-items: center; padding: var(--space-2xl); color: var(--color-on-surface-variant); }
.empty-icon { font-size: 36px; margin-bottom: var(--space-sm); }

/* Error */
.error-state { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 300px; gap: var(--space-md); text-align: center; }
.error-icon { font-size: 48px; }
.error-message { color: var(--color-error); font-size: var(--font-sm); max-width: 400px; }
.btn { padding: 8px 20px; border: none; border-radius: var(--radius-sm); font-size: var(--font-md); font-weight: 500; cursor: pointer; }
.btn-primary { background: var(--color-primary); color: #fff; }
.btn-primary:hover { background: var(--color-primary-hover); }

/* Skeleton */
.skeleton-card {
  background: var(--color-surface); border: 1px solid var(--color-outline);
  border-radius: var(--radius-md); height: 88px;
  animation: pulse 1.5s ease-in-out infinite;
}
.health-skeleton { height: 200px; }
.feed-skeleton { height: 300px; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Responsive */
@media (max-width: 1024px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .dashboard-grid { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .stats-row { grid-template-columns: 1fr; }
}
</style>
