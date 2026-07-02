<template>
  <div class="analytics-page">
    <header class="analytics-header">
      <h1>Analytics</h1>
      <div class="period-picker">
        <button v-for="p in periods" :key="p.value" :class="{ active: period === p.value }" @click="period = p.value">
          {{ p.label }}
        </button>
      </div>
    </header>

    <!-- Stats Overview -->
    <div v-if="loading" class="loading-grid">
      <div v-for="i in 4" :key="i" class="stat-skeleton" />
    </div>

    <div v-else-if="error" class="error-card">
      <p>{{ error }}</p>
      <button class="btn-retry" @click="loadAnalytics">Retry</button>
    </div>

    <div v-else class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Conversations</div>
        <div class="stat-value">{{ stats.total_conversations }}</div>
        <div class="stat-change" :class="stats.conversations_change >= 0 ? 'up' : 'down'">
          {{ stats.conversations_change >= 0 ? '↑' : '↓' }} {{ Math.abs(stats.conversations_change) }}%
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Messages</div>
        <div class="stat-value">{{ formatNumber(stats.total_messages) }}</div>
        <div class="stat-change" :class="stats.messages_change >= 0 ? 'up' : 'down'">
          {{ stats.messages_change >= 0 ? '↑' : '↓' }} {{ Math.abs(stats.messages_change) }}%
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Response Time</div>
        <div class="stat-value">{{ stats.avg_response_ms }}ms</div>
        <div class="stat-change" :class="stats.response_change <= 0 ? 'up' : 'down'">
          {{ stats.response_change > 0 ? '↑' : '↓' }} {{ Math.abs(stats.response_change) }}%
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Resolved</div>
        <div class="stat-value">{{ stats.resolved_count }}</div>
        <div class="stat-change" :class="stats.resolved_change >= 0 ? 'up' : 'down'">
          {{ stats.resolved_change >= 0 ? '↑' : '↓' }} {{ Math.abs(stats.resolved_change) }}%
        </div>
      </div>
    </div>

    <!-- Chart Placeholder -->
    <div class="chart-card">
      <h3>Messages by Day</h3>
      <div v-if="!stats.daily_data?.length" class="chart-empty">No data for this period</div>
      <div v-else class="bar-chart">
        <div v-for="d in stats.daily_data" :key="d.date" class="bar-col">
          <div class="bar" :style="{ height: `${barHeight(d.count)}%` }" :title="`${d.date}: ${d.count}`" />
          <span class="bar-label">{{ formatDate(d.date) }}</span>
        </div>
      </div>
    </div>

    <!-- Channel Breakdown -->
    <div class="chart-card">
      <h3>By Channel</h3>
      <div v-if="!stats.channel_breakdown?.length" class="chart-empty">No channel data</div>
      <div v-else class="channel-list">
        <div v-for="c in stats.channel_breakdown" :key="c.channel_type" class="channel-row">
          <span class="ch-icon">{{ channelIcon(c.channel_type) }}</span>
          <span class="ch-name">{{ c.channel_type }}</span>
          <div class="ch-bar-bg">
            <div class="ch-bar-fill" :style="{ width: `${(c.count / maxChannelCount) * 100}%` }" />
          </div>
          <span class="ch-count">{{ c.count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApi } from '../../shared/composables/useApi'

interface AnalyticsStats {
  total_conversations: number
  total_messages: number
  avg_response_ms: number
  resolved_count: number
  conversations_change: number
  messages_change: number
  response_change: number
  resolved_change: number
  daily_data: { date: string; count: number }[]
  channel_breakdown: { channel_type: string; count: number }[]
}

const loading = ref(true)
const error = ref('')
const period = ref('7d')
const periods = [
  { label: '7d', value: '7d' },
  { label: '30d', value: '30d' },
  { label: '90d', value: '90d' },
]

const stats = ref<AnalyticsStats>({
  total_conversations: 0, total_messages: 0, avg_response_ms: 0, resolved_count: 0,
  conversations_change: 0, messages_change: 0, response_change: 0, resolved_change: 0,
  daily_data: [], channel_breakdown: [],
})

const maxChannelCount = computed(() =>
  Math.max(...(stats.value.channel_breakdown?.map((c) => c.count) || [0]), 1)
)

function barHeight(count: number) {
  const max = Math.max(...(stats.value.daily_data?.map((d) => d.count) || [1]), 1)
  return (count / max) * 100
}

function formatNumber(n: number) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

function formatDate(date: string) {
  return new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function channelIcon(type: string) {
  const icons: Record<string, string> = { telegram: '📱', email: '📧', web_widget: '💬', whatsapp: '📲' }
  return icons[type] || '📡'
}

async function loadAnalytics() {
  loading.value = true
  error.value = ''
  try {
    const api = useApi()
    const { data } = await api.get<AnalyticsStats>(`/analytics?period=${period.value}`)
    stats.value = data
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to load analytics'
  } finally {
    loading.value = false
  }
}

onMounted(loadAnalytics)
</script>

<style scoped>
.analytics-page { padding: 24px; max-width: 960px; margin: 0 auto; }
.analytics-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.analytics-header h1 { font-size: 24px; font-weight: 700; color: #202124; }

.period-picker { display: flex; gap: 4px; background: #f1f3f4; border-radius: 8px; padding: 4px; }
.period-picker button {
  padding: 6px 12px; border: none; background: transparent; border-radius: 6px;
  font-size: 13px; font-weight: 500; color: #5f6368; cursor: pointer; transition: all 0.15s;
}
.period-picker button.active { background: #fff; color: #1a73e8; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
@media (max-width: 768px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }

.stat-card {
  background: #fff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px;
}
.stat-label { font-size: 12px; color: #5f6368; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
.stat-value { font-size: 28px; font-weight: 700; color: #202124; }
.stat-change { font-size: 12px; font-weight: 600; margin-top: 4px; }
.stat-change.up { color: #34a853; }
.stat-change.down { color: #ea4335; }

.chart-card {
  background: #fff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 20px; margin-bottom: 16px;
}
.chart-card h3 { font-size: 14px; font-weight: 600; color: #202124; margin-bottom: 16px; }
.chart-empty { color: #9aa0a6; font-size: 13px; padding: 24px 0; text-align: center; }

.bar-chart { display: flex; align-items: flex-end; gap: 8px; height: 160px; padding-top: 8px; }
.bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; height: 100%; justify-content: flex-end; }
.bar { width: 100%; max-width: 32px; background: linear-gradient(to top, #1a73e8, #8ab4f8); border-radius: 4px 4px 0 0; min-height: 2px; transition: height 0.3s; }
.bar-label { font-size: 10px; color: #9aa0a6; white-space: nowrap; }

.channel-list { display: flex; flex-direction: column; gap: 10px; }
.channel-row { display: flex; align-items: center; gap: 10px; }
.ch-icon { font-size: 18px; }
.ch-name { width: 100px; font-size: 13px; color: #5f6368; text-transform: capitalize; }
.ch-bar-bg { flex: 1; height: 8px; background: #f1f3f4; border-radius: 4px; overflow: hidden; }
.ch-bar-fill { height: 100%; background: #1a73e8; border-radius: 4px; transition: width 0.3s; }
.ch-count { width: 40px; font-size: 13px; font-weight: 600; color: #202124; text-align: right; }

.loading-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-skeleton { height: 104px; background: linear-gradient(90deg, #f1f3f4 25%, #e0e0e0 50%, #f1f3f4 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 12px; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

.error-card { text-align: center; padding: 48px 24px; color: #ea4335; }
.btn-retry { margin-top: 12px; padding: 8px 16px; background: #1a73e8; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; }
</style>
