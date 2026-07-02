<template>
  <div class="billing">
    <h1 class="page-title">Billing</h1>

    <!-- Loading -->
    <template v-if="loading">
      <div class="stats-row">
        <div v-for="n in 4" :key="n" class="skeleton-card" />
      </div>
      <div class="skeleton-card" style="height:200px;margin-top:var(--space-lg)" />
      <div class="skeleton-card" style="height:200px;margin-top:var(--space-lg)" />
    </template>

    <!-- Error -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="btn btn-primary" @click="loadAll">Retry</button>
    </div>

    <!-- Content -->
    <template v-else>
      <!-- Stats -->
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-label">MRR</span>
          <span class="stat-value">${{ stats.mrr.toLocaleString() }}</span>
          <span class="stat-change" :class="stats.mrrChange > 0 ? 'positive' : 'negative'">
            {{ stats.mrrChange > 0 ? '↑' : '↓' }} {{ Math.abs(stats.mrrChange) }}%
          </span>
        </div>
        <div class="stat-card">
          <span class="stat-label">ARR</span>
          <span class="stat-value">${{ stats.arr.toLocaleString() }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Active Subscriptions</span>
          <span class="stat-value">{{ stats.activeSubscriptions }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Churn Rate</span>
          <span class="stat-value">{{ stats.churnRate }}%</span>
        </div>
      </div>

      <!-- Revenue Chart (Simple CSS bar chart) -->
      <div class="card">
        <h3 class="card-title">Monthly Revenue</h3>
        <div v-if="revenueData.length === 0" class="empty-state">
          <p>No revenue data yet</p>
        </div>
        <div v-else class="bar-chart">
          <div
            v-for="bar in revenueData"
            :key="bar.month"
            class="bar-col"
          >
            <div class="bar-wrapper">
              <div
                class="bar"
                :style="{ height: bar.pct + '%' }"
                :title="`$${bar.value.toLocaleString()}`"
              />
            </div>
            <span class="bar-label">{{ bar.label }}</span>
          </div>
        </div>
      </div>

      <!-- Invoices + Subscriptions -->
      <div class="two-col">
        <!-- Invoices -->
        <div class="card">
          <h3 class="card-title">Recent Invoices</h3>
          <div v-if="invoices.length === 0" class="empty-state">
            <p>No invoices</p>
          </div>
          <table v-else class="data-table">
            <thead>
              <tr><th>Tenant</th><th>Amount</th><th>Status</th><th>Date</th></tr>
            </thead>
            <tbody>
              <tr v-for="inv in invoices" :key="inv.id">
                <td>{{ inv.tenant_name || inv.tenant_id }}</td>
                <td class="mono">${{ inv.amount_usd?.toFixed(2) }}</td>
                <td>
                  <span class="status-badge" :class="`status-${inv.status}`">{{ inv.status }}</span>
                </td>
                <td class="date-cell">{{ formatDate(inv.due_date) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Subscriptions -->
        <div class="card">
          <h3 class="card-title">Subscriptions</h3>
          <div v-if="subscriptions.length === 0" class="empty-state">
            <p>No active subscriptions</p>
          </div>
          <table v-else class="data-table">
            <thead>
              <tr><th>Tenant</th><th>Plan</th><th>Status</th><th>Next Billing</th></tr>
            </thead>
            <tbody>
              <tr v-for="sub in subscriptions" :key="sub.id">
                <td>{{ sub.tenant_name || sub.tenant_id }}</td>
                <td>{{ sub.plan_name || sub.plan_id }}</td>
                <td>
                  <span class="status-badge" :class="`status-${sub.status}`">{{ sub.status }}</span>
                </td>
                <td class="date-cell">{{ formatDate(sub.current_period_end) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../shared/composables/useApi'

const api = useApi()

const loading = ref(true)
const error = ref('')
const stats = ref({ mrr: 0, arr: 0, activeSubscriptions: 0, churnRate: 0, mrrChange: 0 })
const revenueData = ref<{ month: string; label: string; value: number; pct: number }[]>([])
const invoices = ref<any[]>([])
const subscriptions = ref<any[]>([])

function formatDate(date: string): string {
  return new Date(date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

function computeBarPcts(data: number[]): number[] {
  const max = Math.max(...data, 1)
  return data.map(v => Math.round((v / max) * 100))
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [statsRes, revenueRes, invRes, subRes] = await Promise.all([
      api.get('/admin/stats'),
      api.get('/billing/revenue?months=6'),
      api.get('/billing/invoices?limit=10'),
      api.get('/billing/subscriptions?limit=10'),
    ])
    const s = statsRes.data
    stats.value = {
      mrr: s.mrr || 0,
      arr: s.arr || 0,
      activeSubscriptions: s.active_subscriptions || 0,
      churnRate: s.churn_rate || 0,
      mrrChange: s.mrr_change || 0,
    }

    const rev = revenueRes.data || []
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const pcts = computeBarPcts(rev.map((r: any) => r.value || r.amount || 0))
    revenueData.value = rev.map((r: any, i: number) => {
      const d = new Date(r.month || r.date)
      return {
        month: r.month || r.date,
        label: months[d.getMonth()] || `M${i + 1}`,
        value: r.value || r.amount || 0,
        pct: pcts[i],
      }
    })

    invoices.value = (invRes.data.items || invRes.data || []).slice(0, 10)
    subscriptions.value = (subRes.data.items || subRes.data || []).slice(0, 10)
  } catch (e: any) {
    error.value = e?.message || 'Failed to load billing data'
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.billing { display: flex; flex-direction: column; gap: var(--space-lg); }
.page-title { font-size: var(--font-2xl); font-weight: 700; color: var(--color-on-surface); }

.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-md); }
.stat-card {
  background: var(--color-surface); border: 1px solid var(--color-outline);
  border-radius: var(--radius-md); padding: var(--space-lg);
  display: flex; flex-direction: column; gap: var(--space-xs);
  box-shadow: var(--shadow-sm);
}
.stat-label { font-size: var(--font-sm); color: var(--color-on-surface-variant); }
.stat-value { font-size: var(--font-2xl); font-weight: 700; color: var(--color-on-surface); }
.stat-change { font-size: var(--font-xs); font-weight: 500; }
.stat-change.positive { color: var(--color-success); }
.stat-change.negative { color: var(--color-error); }

.card {
  background: var(--color-surface); border: 1px solid var(--color-outline);
  border-radius: var(--radius-md); padding: var(--space-lg); box-shadow: var(--shadow-sm);
}
.card-title { font-size: var(--font-lg); font-weight: 600; margin-bottom: var(--space-md); color: var(--color-on-surface); }

/* Bar chart */
.bar-chart { display: flex; align-items: flex-end; gap: var(--space-md); height: 160px; padding-top: var(--space-lg); }
.bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: var(--space-xs); height: 100%; }
.bar-wrapper { flex: 1; width: 100%; display: flex; align-items: flex-end; justify-content: center; }
.bar {
  width: 70%; max-width: 48px; background: var(--color-primary); border-radius: var(--radius-sm) var(--radius-sm) 0 0;
  transition: height 0.3s ease; min-height: 2px;
}
.bar-label { font-size: var(--font-xs); color: var(--color-on-surface-variant); }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-lg); }

.data-table { width: 100%; border-collapse: collapse; font-size: var(--font-sm); }
.data-table th { text-align: left; padding: var(--space-xs) var(--space-sm); font-weight: 600; font-size: var(--font-xs); text-transform: uppercase; letter-spacing: 0.5px; color: var(--color-on-surface-variant); border-bottom: 1px solid var(--color-outline); }
.data-table td { padding: var(--space-xs) var(--space-sm); border-bottom: 1px solid var(--color-outline); color: var(--color-on-surface); white-space: nowrap; }
.data-table tbody tr:last-child td { border-bottom: none; }

.status-badge { display: inline-block; padding: 1px 8px; border-radius: var(--radius-full); font-size: var(--font-xs); font-weight: 600; text-transform: capitalize; }
.status-paid, .status-active { background: var(--color-success-light); color: var(--color-success); }
.status-pending, .status-trial { background: var(--color-warning-light); color: var(--color-warning); }
.status-overdue, .status-cancelled { background: var(--color-error-light); color: var(--color-error); }
.status-draft { background: var(--color-surface-variant); color: var(--color-on-surface-variant); }

.date-cell { color: var(--color-on-surface-variant); }
.mono { font-family: var(--mono); }

.btn { padding: 8px 20px; border: none; border-radius: var(--radius-sm); font-size: var(--font-md); font-weight: 500; cursor: pointer; }
.btn-primary { background: var(--color-primary); color: #fff; }
.btn-primary:hover { background: var(--color-primary-hover); }

.empty-state { display: flex; align-items: center; justify-content: center; padding: var(--space-xl); color: var(--color-on-surface-variant); }
.error-state { display: flex; flex-direction: column; align-items: center; gap: var(--space-md); padding: var(--space-3xl); color: var(--color-error); }

.skeleton-card { background: var(--color-surface); border: 1px solid var(--color-outline); border-radius: var(--radius-md); animation: pulse 1.5s ease-in-out infinite; height: 88px; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

@media (max-width: 1024px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .two-col { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .stats-row { grid-template-columns: 1fr; }
}
</style>
