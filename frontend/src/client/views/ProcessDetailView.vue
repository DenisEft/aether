<script setup lang="ts">
/**
 * ProcessDetailView — interactive process card with fields and transitions.
 *
 * Reads from Aether GET /api/v1/processes/{id}?include_definition=true
 * Posts field updates and transitions via REST.
 * Subscribes to WS for live updates.
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '@/shared/composables/useApi'
import { useAuth } from '@/shared/composables/useAuth'
import { useTenant } from '@/shared/composables/useTenant'

const route = useRoute()
const router = useRouter()
const api = useApi()
const auth = useAuth()
const tenant = useTenant()

// ── State ─────────────────────────────────────────────────────

interface Transition {
  to_block: string
  label: string | null
  condition: string | null
}

interface ProcessBlock {
  key: string
  block_type: string
  label: string
  description?: string
  config?: Record<string, any>
  stages?: Array<{
    name: string
    slug: string
    is_terminal: boolean
    color: string
  }>
}

interface ProcessDetail {
  id: string
  process_name: string
  state: string
  current_block_key: string | null
  current_block_label: string | null
  field_values: Record<string, Record<string, any>>
  execution_log: Array<Record<string, any>>
  available_transitions: Transition[] | null
  process_definition: {
    blocks: ProcessBlock[]
    connections: Array<{ source: string; target: string }>
  } | null
  started_at: string
  completed_at: string | null
}

const instance = ref<ProcessDetail | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const currentBlock = ref<ProcessBlock | null>(null)
const fieldValues = ref<Record<string, any>>({})
const transitionComment = ref('')
const transitioning = ref(false)
const ws = ref<WebSocket | null>(null)

// ── Computed ──────────────────────────────────────────────────

const blocks = computed(() => instance.value?.process_definition?.blocks || [])
const timeline = computed(() => instance.value?.execution_log || [])

const pipelineStages = computed(() => {
  const pipelineBlock = blocks.value.find(b => b.block_type === 'pipeline')
  return pipelineBlock?.stages || []
})

// ── Methods ───────────────────────────────────────────────────

async function loadInstance() {
  loading.value = true
  error.value = null
  try {
    const id = route.params.instanceId as string
    const result = await api.get(`/api/v1/processes/${id}`, { include_definition: 'true' })
    instance.value = result
    fieldValues.value = Object.assign({}, result.field_values)

    // Find current block
    if (result.current_block_key) {
      currentBlock.value = blocks.value.find(b => b.key === result.current_block_key) || null
    }
  } catch (e: any) {
    error.value = e.message || 'Failed to load process'
  } finally {
    loading.value = false
  }
}

async function saveField(blockKey: string, fieldKey: string, value: any) {
  if (!instance.value) return
  try {
    await api.post(`/api/v1/processes/${instance.value.id}/field`, {
      block_key: blockKey,
      values: { [fieldKey]: value },
    })
  } catch (e: any) {
    console.error('Field save error:', e)
  }
}

async function doTransition(targetBlock: string, label: string) {
  if (!instance.value || transitioning.value) return
  transitioning.value = true
  try {
    const result = await api.post(`/api/v1/processes/${instance.value.id}/transition`, {
      to_block: targetBlock,
      label: label,
      triggered_by: auth.user?.email || 'user',
      comment: transitionComment.value || undefined,
    })
    instance.value = result
    fieldValues.value = Object.assign({}, result.field_values)
    currentBlock.value = blocks.value.find(b => b.key === result.current_block_key) || null
    transitionComment.value = ''
  } catch (e: any) {
    alert(e.message || 'Transition failed')
  } finally {
    transitioning.value = false
  }
}

function connectWs() {
  const token = auth.token
  if (!token || !tenant.currentId) return

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = location.host
  const url = `${protocol}//${host}/ws/processes/${tenant.currentId}?token=${encodeURIComponent(token)}`

  ws.value = new WebSocket(url)
  ws.value.onopen = () => console.log('[ProcessDetail] WS connected')

  ws.value.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'ping') {
        ws.value?.send(JSON.stringify({ type: 'pong' }))
        return
      }
      if (msg.data?.instance_id === instance.value?.id) {
        loadInstance() // Refresh on any event for this instance
      }
    } catch { /* ignore */ }
  }

  ws.value.onclose = () => {
    setTimeout(connectWs, 5000)
  }
}

function stateColor(state: string) {
  return {
    active: '#3b82f6',
    paused: '#f59e0b',
    completed: '#10b981',
    failed: '#ef4444',
    cancelled: '#6b7280',
  }[state] || '#94a3b8'
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU')
}

onMounted(() => {
  loadInstance()
  connectWs()
})

onUnmounted(() => {
  ws.value?.close()
})
</script>

<template>
  <div
    v-if="instance"
    class="process-detail"
  >
    <!-- Header -->
    <header class="pd-header">
      <button
        class="pd-back"
        @click="router.back()"
      >
        ← Back
      </button>
      <div>
        <h2>{{ instance.process_name }}</h2>
        <span
          class="pd-state"
          :style="{ background: stateColor(instance.state) }"
        >
          {{ instance.state }}
        </span>
      </div>
    </header>

    <!-- Pipeline -->
    <section
      v-if="pipelineStages.length > 0"
      class="pd-pipeline"
    >
      <div class="pipeline-track">
        <div
          v-for="stage in pipelineStages"
          :key="stage.slug"
          class="pipeline-stage"
          :class="{
            active: instance.current_block_key && blocks.find(b => b.key === instance.current_block_key)?.stages?.some((s: any) => s.slug === stage.slug),
            terminal: stage.is_terminal,
          }"
          :style="{ borderColor: stage.color }"
        >
          <div
            class="stage-dot"
            :style="{ background: stage.color }"
          />
          <span class="stage-name">{{ stage.name }}</span>
        </div>
      </div>
    </section>

    <!-- Current Block / Form -->
    <section
      v-if="currentBlock && instance.state === 'active'"
      class="pd-current"
    >
      <h3>{{ currentBlock.label }}</h3>
      <p
        v-if="currentBlock.description"
        class="block-desc"
      >
        {{ currentBlock.description }}
      </p>

      <!-- Fields -->
      <div
        v-if="currentBlock.config?.fields"
        class="pd-fields"
      >
        <div
          v-for="field in currentBlock.config.fields"
          :key="field.key"
          class="field-row"
        >
          <label>{{ field.label }}</label>
          <input
            v-if="field.type === 'text' || field.type === 'string'"
            type="text"
            :value="fieldValues[currentBlock.key]?.[field.key] || ''"
            class="field-input"
            @change="(e: Event) => saveField(currentBlock!.key, field.key, (e.target as HTMLInputElement).value)"
          >
          <input
            v-else-if="field.type === 'number'"
            type="number"
            :value="fieldValues[currentBlock.key]?.[field.key] || 0"
            class="field-input"
            @change="(e: Event) => saveField(currentBlock!.key, field.key, Number((e.target as HTMLInputElement).value))"
          >
          <textarea
            v-else-if="field.type === 'textarea'"
            :value="fieldValues[currentBlock.key]?.[field.key] || ''"
            class="field-input field-textarea"
            @change="(e: Event) => saveField(currentBlock!.key, field.key, (e.target as HTMLTextAreaElement).value)"
          />
        </div>
      </div>

      <!-- Transitions -->
      <div
        v-if="instance.available_transitions?.length"
        class="pd-transitions"
      >
        <h4>Available Actions</h4>
        <div class="transition-list">
          <div
            v-for="t in instance.available_transitions"
            :key="t.to_block"
            class="transition-item"
          >
            <button
              class="transition-btn"
              :disabled="transitioning"
              @click="doTransition(t.to_block, t.label || '')"
            >
              {{ t.label || 'Continue' }}
            </button>
            <input
              v-model="transitionComment"
              type="text"
              placeholder="Comment (optional)"
              class="transition-comment"
            >
          </div>
        </div>
      </div>
    </section>

    <!-- Completed message -->
    <section
      v-else-if="instance.state === 'completed'"
      class="pd-completed"
    >
      <span class="done-icon">✅</span>
      <p>Process completed {{ formatDate(instance.completed_at) }}</p>
    </section>

    <!-- Timeline -->
    <section class="pd-timeline">
      <h4>📋 Activity Log</h4>
      <div class="timeline-list">
        <div
          v-for="(entry, i) in timeline"
          :key="i"
          class="timeline-entry"
        >
          <span class="tl-action">{{ entry.action }}</span>
          <span class="tl-block">Block: {{ entry.block_key }}</span>
          <span class="tl-time">{{ entry.timestamp }}</span>
          <span v-if="entry.user">by {{ entry.user }}</span>
        </div>
      </div>
    </section>
  </div>

  <!-- States -->
  <div
    v-else-if="loading"
    class="pd-loading"
  >
    Loading process...
  </div>
  <div
    v-else-if="error"
    class="pd-error"
  >
    {{ error }}
  </div>
</template>

<style scoped>
.process-detail {
  padding: 24px;
  max-width: 800px;
  margin: 0 auto;
}

.pd-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.pd-back {
  padding: 6px 12px;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 6px;
  background: var(--bg-secondary, #fff);
  cursor: pointer;
  font-size: 0.85rem;
}

.pd-header h2 {
  font-size: 1.4rem;
  margin: 0 0 4px;
}

.pd-state {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  color: #fff;
  padding: 2px 10px;
  border-radius: 12px;
}

/* Pipeline */
.pd-pipeline { margin-bottom: 24px; }

.pipeline-track {
  display: flex;
  align-items: center;
  gap: 0;
  overflow-x: auto;
  padding: 12px 0;
}

.pipeline-stage {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-top: 3px solid #e2e8f0;
  border-bottom: 3px solid #e2e8f0;
  white-space: nowrap;
  opacity: 0.6;
  transition: opacity 0.2s;
}

.pipeline-stage.active {
  opacity: 1;
  font-weight: 600;
}

.stage-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.stage-name { font-size: 0.8rem; }

/* Current block */
.pd-current {
  background: var(--bg-secondary, #f8fafc);
  padding: 20px;
  border-radius: 10px;
  margin-bottom: 24px;
  border: 1px solid var(--border-color, #e2e8f0);
}

.pd-current h3 {
  font-size: 1.1rem;
  margin: 0 0 8px;
}

.block-desc {
  color: var(--text-secondary, #64748b);
  font-size: 0.85rem;
  margin-bottom: 16px;
}

/* Fields */
.pd-fields { display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px; }

.field-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-row label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-secondary, #64748b);
}

.field-input {
  padding: 8px 12px;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 6px;
  font-size: 0.9rem;
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #1e293b);
}

.field-textarea { min-height: 80px; resize: vertical; }

/* Transitions */
.pd-transitions { margin-top: 16px; }

.pd-transitions h4 { margin: 0 0 12px; font-size: 0.95rem; }

.transition-list { display: flex; flex-direction: column; gap: 12px; }

.transition-item {
  display: flex;
  gap: 12px;
  align-items: center;
}

.transition-btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  background: var(--primary, #3b82f6);
  color: #fff;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
  white-space: nowrap;
}

.transition-btn:hover { opacity: 0.9; }
.transition-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.transition-comment {
  flex: 1;
  padding: 6px 12px;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 6px;
  font-size: 0.85rem;
}

/* Completed */
.pd-completed {
  text-align: center;
  padding: 40px 0;
}

.done-icon { font-size: 2rem; }

/* Timeline */
.pd-timeline {
  margin-top: 24px;
}

.pd-timeline h4 { margin: 0 0 12px; }

.timeline-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.timeline-entry {
  display: flex;
  gap: 8px;
  font-size: 0.8rem;
  padding: 6px 10px;
  background: var(--bg-secondary, #f8fafc);
  border-radius: 6px;
  flex-wrap: wrap;
}

.tl-action {
  font-weight: 600;
  text-transform: uppercase;
  color: var(--primary, #3b82f6);
}

.tl-block { color: var(--text-secondary, #64748b); }
.tl-time { color: var(--text-tertiary, #94a3b8); margin-left: auto; }

.pd-loading, .pd-error {
  text-align: center;
  padding: 48px 0;
}
</style>
