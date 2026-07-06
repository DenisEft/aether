<script setup lang="ts">
/**
 * ProcessListView — shows all process instances for the current tenant.
 *
 * Reads from Aether GET /api/v1/processes/
 * Subscribes to WS /ws/processes/{tenant_id} for live updates.
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/shared/composables/useApi'
import { useAuth } from '@/shared/composables/useAuth'
import { useTenant } from '@/shared/composables/useTenant'

const router = useRouter()
const api = useApi()
const auth = useAuth()
const tenant = useTenant()

// ── State ─────────────────────────────────────────────────────

interface ProcessItem {
  id: string
  process_name: string
  state: 'active' | 'paused' | 'completed' | 'failed' | 'cancelled'
  current_block_key: string | null
  current_block_label: string | null
  started_at: string
  completed_at: string | null
  service_instance_id: string | null
}

const instances = ref<ProcessItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const stateFilter = ref<string>('active')
const ws = ref<WebSocket | null>(null)

// ── Methods ───────────────────────────────────────────────────

async function loadInstances() {
  loading.value = true
  error.value = null
  try {
    const params: Record<string, string> = { limit: '50' }
    if (stateFilter.value && stateFilter.value !== 'all') {
      params.state = stateFilter.value
    }
    instances.value = await api.get('/api/v1/processes/', params)
  } catch (e: any) {
    error.value = e.message || 'Failed to load processes'
  } finally {
    loading.value = false
  }
}

function connectWs() {
  const token = auth.token
  if (!token || !tenant.currentId) return

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = location.host
  const url = `${protocol}//${host}/ws/processes/${tenant.currentId}?token=${encodeURIComponent(token)}`

  ws.value = new WebSocket(url)

  ws.value.onopen = () => {
    console.log('[ProcessList] WS connected')
  }

  ws.value.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'ping') {
        ws.value?.send(JSON.stringify({ type: 'pong' }))
        return
      }

      switch (msg.type) {
        case 'process.started':
        case 'process.completed':
        case 'process.cancelled':
          // Refresh the list on state changes
          loadInstances()
          break

        case 'process.transitioned':
          // Update in-place if instance is already visible
          const data = msg.data
          const idx = instances.value.findIndex(i => i.id === data.instance_id)
          if (idx >= 0) {
            instances.value[idx].current_block_key = data.to_block
            instances.value[idx].state = data.state
          }
          break
      }
    } catch { /* ignore */ }
  }

  ws.value.onclose = () => {
    console.log('[ProcessList] WS disconnected, reconnecting in 5s...')
    setTimeout(connectWs, 5000)
  }
}

function viewInstance(id: string) {
  router.push(`/${tenant.slug}/processes/${id}`)
}

function stateClass(state: string) {
  return `state-${state}`
}

function stateLabel(state: string) {
  const labels: Record<string, string> = {
    active: 'Active',
    paused: 'Paused',
    completed: 'Done',
    failed: 'Failed',
    cancelled: 'Cancelled',
  }
  return labels[state] || state
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  loadInstances()
  connectWs()
})

onUnmounted(() => {
  ws.value?.close()
})
</script>

<template>
  <div class="process-list">
    <header class="pl-header">
      <h2>⚙️ Processes</h2>
      <div class="pl-filters">
        <button
          v-for="s in ['active', 'paused', 'completed', 'all']"
          :key="s"
          class="filter-btn"
          :class="{ active: stateFilter === s }"
          @click="stateFilter = s; loadInstances()"
        >
          {{ s === 'all' ? 'All' : stateLabel(s) }}
        </button>
      </div>
    </header>

    <div
      v-if="loading"
      class="pl-loading"
    >
      Loading processes...
    </div>
    <div
      v-else-if="error"
      class="pl-error"
    >
      {{ error }}
    </div>
    <div
      v-else-if="instances.length === 0"
      class="pl-empty"
    >
      <span class="empty-icon">📭</span>
      <p>No process instances found</p>
    </div>

    <div
      v-else
      class="pl-table"
    >
      <div
        v-for="inst in instances"
        :key="inst.id"
        class="pl-row"
        @click="viewInstance(inst.id)"
      >
        <div class="pl-name">
          <span class="pl-process-name">{{ inst.process_name || 'Process' }}</span>
          <span class="pl-block">{{ inst.current_block_label || inst.current_block_key || '—' }}</span>
        </div>
        <div class="pl-meta">
          <span
            class="pl-state"
            :class="stateClass(inst.state)"
          >
            {{ stateLabel(inst.state) }}
          </span>
          <span class="pl-date">{{ formatDate(inst.started_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.process-list {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

.pl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.pl-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0;
}

.pl-filters {
  display: flex;
  gap: 6px;
}

.filter-btn {
  padding: 4px 12px;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 6px;
  background: var(--bg-secondary, #fff);
  color: var(--text-secondary, #64748b);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
}

.filter-btn.active {
  background: var(--primary, #3b82f6);
  color: #fff;
  border-color: var(--primary, #3b82f6);
}

.pl-loading, .pl-error, .pl-empty {
  text-align: center;
  padding: 48px 0;
  color: var(--text-secondary, #94a3b8);
}

.empty-icon { font-size: 2rem; display: block; margin-bottom: 8px; }

.pl-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.pl-row:hover {
  background: var(--bg-hover, #f8fafc);
}

.pl-name {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pl-process-name {
  font-weight: 500;
}

.pl-block {
  font-size: 0.8rem;
  color: var(--text-secondary, #64748b);
}

.pl-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pl-state {
  font-size: 0.75rem;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 12px;
  text-transform: uppercase;
}

.state-active { background: #dbeafe; color: #1d4ed8; }
.state-paused { background: #fef3c7; color: #b45309; }
.state-completed { background: #d1fae5; color: #065f46; }
.state-failed { background: #fee2e2; color: #991b1b; }
.state-cancelled { background: #f3f4f6; color: #6b7280; }

.pl-date {
  font-size: 0.75rem;
  color: var(--text-secondary, #94a3b8);
}
</style>
