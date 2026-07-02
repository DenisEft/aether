<template>
  <div class="drivers">
    <div class="page-header">
      <h1>AI Drivers</h1>
      <button class="btn btn-primary" @click="openAddModal">
        <span class="btn-icon">+</span> Add Driver
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="table-skeleton">
      <div v-for="n in 6" :key="n" class="skeleton-row" :style="{ animationDelay: `${n * 80}ms` }" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="btn btn-primary" @click="loadDrivers">Retry</button>
    </div>

    <!-- Empty -->
    <div v-else-if="drivers.length === 0" class="empty-state">
      <span class="empty-icon">⚙️</span>
      <h3>No AI drivers configured</h3>
      <p>Add your first driver to enable AI inference</p>
      <button class="btn btn-primary" @click="openAddModal">Add Driver</button>
    </div>

    <!-- Table -->
    <template v-else>
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Driver Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Models</th>
              <th>Last Check</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in drivers" :key="d.id">
              <td class="driver-name">
                <span class="driver-icon">{{ driverIcon(d.driver_type) }}</span>
                <div>
                  <span class="name-text">{{ d.name || d.driver_type }}</span>
                  <span class="name-sub">{{ d.endpoint_url }}</span>
                </div>
              </td>
              <td><span class="type-badge">{{ d.driver_type }}</span></td>
              <td>
                <span class="status-indicator" :class="`driver-${d.status}`">
                  <span class="status-dot" />
                  {{ d.status }}
                </span>
              </td>
              <td>{{ d.models_count ?? '—' }}</td>
              <td class="date-cell">{{ d.last_heartbeat ? formatTime(d.last_heartbeat) : 'Never' }}</td>
              <td>
                <div class="action-btns">
                  <button
                    class="btn btn-ghost btn-sm"
                    :disabled="checkingId === d.id"
                    @click="healthCheck(d.id)"
                  >
                    {{ checkingId === d.id ? 'Checking...' : 'Health Check' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Add Driver Modal -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-backdrop" @click.self="closeModal">
        <div class="modal">
          <div class="modal-header">
            <h2>{{ modalStep === 4 ? 'Driver Added' : 'Add Driver' }}</h2>
            <button class="modal-close" @click="closeModal">✕</button>
          </div>

          <!-- Step 1: Select Type -->
          <div v-if="modalStep === 1" class="modal-body">
            <div class="step-indicator">Step 1 of 4: Select Driver Type</div>
            <div class="type-grid">
              <button
                v-for="t in driverTypes"
                :key="t.value"
                class="type-card"
                :class="{ selected: newDriver.type === t.value }"
                @click="newDriver.type = t.value"
              >
                <span class="type-icon">{{ t.icon }}</span>
                <span class="type-label">{{ t.label }}</span>
                <span class="type-desc">{{ t.desc }}</span>
              </button>
            </div>
          </div>

          <!-- Step 2: Configure -->
          <div v-if="modalStep === 2" class="modal-body">
            <div class="step-indicator">Step 2 of 4: Configure</div>
            <div class="form-group">
              <label>Driver Name</label>
              <input v-model="newDriver.name" class="form-input" placeholder="My Ollama Server" />
            </div>
            <div class="form-group">
              <label>Endpoint URL</label>
              <input v-model="newDriver.url" class="form-input" placeholder="http://localhost:11434" />
            </div>
            <div class="form-group">
              <label>Priority</label>
              <input v-model.number="newDriver.priority" type="number" class="form-input" min="0" max="100" />
            </div>
          </div>

          <!-- Step 3: Test -->
          <div v-if="modalStep === 3" class="modal-body">
            <div class="step-indicator">Step 3 of 4: Test Connection</div>
            <div class="test-section">
              <div v-if="testLoading" class="test-status">
                <span class="spinner" />
                Testing connection to {{ newDriver.url }}...
              </div>
              <div v-else-if="testResult === 'success'" class="test-status test-success">
                ✅ Connection successful — {{ testModels }} models found
              </div>
              <div v-else-if="testResult === 'fail'" class="test-status test-fail">
                ❌ Connection failed: {{ testError }}
              </div>
              <div v-else class="test-status">
                Ready to test connection
              </div>
              <button class="btn btn-secondary" :disabled="testLoading" @click="testConnection">
                {{ testResult ? 'Retest' : 'Test Connection' }}
              </button>
            </div>
          </div>

          <!-- Step 4: Success -->
          <div v-if="modalStep === 4" class="modal-body">
            <div class="success-message">
              <span class="success-icon">✅</span>
              <p>Driver has been added successfully!</p>
            </div>
          </div>

          <!-- Modal Footer -->
          <div class="modal-footer">
            <button v-if="modalStep > 1 && modalStep < 4" class="btn btn-ghost" @click="modalStep--">
              Back
            </button>
            <button class="btn btn-ghost" @click="closeModal">Cancel</button>
            <button
              v-if="modalStep === 1"
              class="btn btn-primary"
              :disabled="!newDriver.type"
              @click="modalStep = 2"
            >
              Next
            </button>
            <button
              v-if="modalStep === 2"
              class="btn btn-primary"
              :disabled="!newDriver.name || !newDriver.url"
              @click="modalStep = 3"
            >
              Next
            </button>
            <button
              v-if="modalStep === 3"
              class="btn btn-primary"
              :disabled="testResult !== 'success'"
              @click="saveDriver"
            >
              Save Driver
            </button>
            <button v-if="modalStep === 4" class="btn btn-primary" @click="closeModal">
              Done
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../shared/composables/useApi'

const api = useApi()

const loading = ref(true)
const error = ref('')
const drivers = ref<any[]>([])
const checkingId = ref<string | null>(null)

const driverTypes = [
  { value: 'ollama', label: 'Ollama', icon: '🦙', desc: 'Local LLM inference via Ollama' },
  { value: 'llamacpp', label: 'LlamaCpp', icon: '📦', desc: 'GGUF models via llama.cpp server' },
  { value: 'openai', label: 'OpenAI', icon: '🤖', desc: 'OpenAI API-compatible endpoint' },
  { value: 'vllm', label: 'vLLM', icon: '⚡', desc: 'High-throughput vLLM server' },
  { value: 'anthropic', label: 'Anthropic', icon: '🧠', desc: 'Claude models via Anthropic API' },
  { value: 'custom', label: 'Custom', icon: '🔧', desc: 'Custom OpenAI-compatible endpoint' },
]

const showModal = ref(false)
const modalStep = ref(1)
const newDriver = ref({ type: '', name: '', url: '', priority: 0 })
const testLoading = ref(false)
const testResult = ref<'success' | 'fail' | null>(null)
const testError = ref('')
const testModels = ref(0)

function driverIcon(type: string): string {
  return driverTypes.find(t => t.value === type)?.icon || '🔌'
}

function formatTime(ts: string): string {
  const d = new Date(ts)
  const now = new Date()
  const mins = Math.floor((now.getTime() - d.getTime()) / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`
  return d.toLocaleDateString()
}

async function loadDrivers() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/ai/drivers')
    drivers.value = data.items || data || []
  } catch (e: any) {
    error.value = e?.message || 'Failed to load drivers'
  } finally {
    loading.value = false
  }
}

async function healthCheck(driverId: string) {
  checkingId.value = driverId
  try {
    await api.post(`/ai/drivers/${driverId}/health`)
    await loadDrivers()
  } catch (e: unknown) {
    console.error('[DriversView] Driver health check failed', driverId, e)
  } finally {
    checkingId.value = null
  }
}

function openAddModal() {
  showModal.value = true
  modalStep.value = 1
  newDriver.value = { type: '', name: '', url: '', priority: 0 }
  testResult.value = null
  testError.value = ''
  testModels.value = 0
}

function closeModal() {
  showModal.value = false
  loadDrivers()
}

async function testConnection() {
  testLoading.value = true
  testResult.value = null
  testError.value = ''
  try {
    const { data } = await api.post('/ai/drivers/test', {
      driver_type: newDriver.value.type,
      endpoint_url: newDriver.value.url,
    })
    testResult.value = 'success'
    testModels.value = data.models_count || 0
  } catch (e: any) {
    testResult.value = 'fail'
    testError.value = e?.response?.data?.detail || e?.message || 'Unknown error'
  } finally {
    testLoading.value = false
  }
}

async function saveDriver() {
  try {
    await api.post('/ai/drivers', {
      driver_type: newDriver.value.type,
      name: newDriver.value.name,
      endpoint_url: newDriver.value.url,
      priority: newDriver.value.priority,
    })
    modalStep.value = 4
  } catch (e: unknown) {
    console.error('[DriversView] Failed to save new driver', e)
  }
}

onMounted(loadDrivers)
</script>

<style scoped>
.drivers { display: flex; flex-direction: column; gap: var(--space-lg); }

.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-header h1 { font-size: var(--font-2xl); font-weight: 700; color: var(--color-on-surface); }

.btn { display: inline-flex; align-items: center; gap: var(--space-xs); padding: 6px 16px; border: none; border-radius: var(--radius-sm); font-size: var(--font-sm); font-weight: 500; cursor: pointer; }
.btn-primary { background: var(--color-primary); color: #fff; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-secondary { background: var(--color-surface-variant); color: var(--color-on-surface); border: 1px solid var(--color-outline); }
.btn-ghost { background: transparent; color: var(--color-on-surface-variant); }
.btn-ghost:hover:not(:disabled) { background: var(--color-primary-light); }
.btn-sm { padding: 4px 12px; font-size: var(--font-xs); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-icon { font-size: 18px; line-height: 1; }

.table-wrapper { overflow-x: auto; border: 1px solid var(--color-outline); border-radius: var(--radius-md); background: var(--color-surface); }
.data-table { width: 100%; border-collapse: collapse; font-size: var(--font-md); }
.data-table th { text-align: left; padding: var(--space-sm) var(--space-lg); font-weight: 600; font-size: var(--font-xs); text-transform: uppercase; letter-spacing: 0.5px; color: var(--color-on-surface-variant); border-bottom: 1px solid var(--color-outline); background: var(--color-surface-variant); }
.data-table td { padding: var(--space-sm) var(--space-lg); border-bottom: 1px solid var(--color-outline); color: var(--color-on-surface); }
.data-table tbody tr:last-child td { border-bottom: none; }

.driver-name { display: flex; align-items: center; gap: var(--space-sm); }
.driver-icon { font-size: 20px; }
.name-text { display: block; font-weight: 500; }
.name-sub { display: block; font-size: var(--font-xs); color: var(--color-on-surface-variant); font-family: var(--mono); }
.type-badge { font-size: var(--font-xs); padding: 2px 8px; border-radius: var(--radius-full); background: var(--color-surface-variant); color: var(--color-on-surface-variant); text-transform: capitalize; }

.status-indicator { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-sm); text-transform: capitalize; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.driver-online .status-dot { background: var(--color-success); }
.driver-online { color: var(--color-success); }
.driver-offline .status-dot { background: var(--color-outline); }
.driver-offline { color: var(--color-on-surface-variant); }
.driver-error .status-dot { background: var(--color-error); }
.driver-error { color: var(--color-error); }
.driver-degraded .status-dot { background: var(--color-warning); }
.driver-degraded { color: var(--color-warning); }

.date-cell { white-space: nowrap; color: var(--color-on-surface-variant); font-size: var(--font-sm); }
.action-btns { display: flex; gap: var(--space-xs); }

/* Modal */
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: var(--color-surface); border-radius: var(--radius-lg); width: 90%; max-width: 560px; max-height: 85vh; display: flex; flex-direction: column; box-shadow: var(--shadow-xl); }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: var(--space-lg); border-bottom: 1px solid var(--color-outline); }
.modal-header h2 { font-size: var(--font-lg); font-weight: 600; }
.modal-close { background: none; border: none; font-size: 18px; cursor: pointer; color: var(--color-on-surface-variant); padding: 4px 8px; border-radius: var(--radius-sm); }
.modal-close:hover { background: var(--color-surface-variant); }
.modal-body { padding: var(--space-lg); overflow-y: auto; flex: 1; }
.modal-footer { display: flex; justify-content: flex-end; gap: var(--space-sm); padding: var(--space-lg); border-top: 1px solid var(--color-outline); }

.step-indicator { font-size: var(--font-sm); color: var(--color-on-surface-variant); margin-bottom: var(--space-lg); }

.type-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-sm); }
.type-card { display: flex; flex-direction: column; gap: var(--space-xs); padding: var(--space-md); border: 2px solid var(--color-outline); border-radius: var(--radius-md); background: var(--color-surface); cursor: pointer; text-align: left; transition: all 0.15s; }
.type-card:hover { border-color: var(--color-primary); }
.type-card.selected { border-color: var(--color-primary); background: var(--color-primary-light); }
.type-icon { font-size: 24px; }
.type-label { font-weight: 600; font-size: var(--font-md); }
.type-desc { font-size: var(--font-xs); color: var(--color-on-surface-variant); }

.form-group { display: flex; flex-direction: column; gap: var(--space-xs); margin-bottom: var(--space-md); }
.form-group label { font-size: var(--font-sm); font-weight: 500; color: var(--color-on-surface-variant); }
.form-input { padding: 8px 12px; border: 1px solid var(--color-outline); border-radius: var(--radius-sm); font-size: var(--font-md); outline: none; color: var(--color-on-surface); background: var(--color-surface); }
.form-input:focus { border-color: var(--color-primary); }

.test-section { display: flex; flex-direction: column; align-items: center; gap: var(--space-lg); padding: var(--space-xl) 0; }
.test-status { font-size: var(--font-md); display: flex; align-items: center; gap: var(--space-sm); color: var(--color-on-surface-variant); }
.test-success { color: var(--color-success); }
.test-fail { color: var(--color-error); }

.success-message { display: flex; flex-direction: column; align-items: center; gap: var(--space-md); padding: var(--space-2xl); }
.success-icon { font-size: 48px; }

.spinner { width: 16px; height: 16px; border: 2px solid var(--color-outline); border-top-color: var(--color-primary); border-radius: 50%; animation: spin 0.6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.table-skeleton { display: flex; flex-direction: column; gap: var(--space-sm); }
.skeleton-row { height: 48px; background: var(--color-surface); border-radius: var(--radius-sm); animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.empty-state { display: flex; flex-direction: column; align-items: center; padding: var(--space-3xl); gap: var(--space-sm); color: var(--color-on-surface-variant); }
.empty-icon { font-size: 48px; }
.empty-state h3 { font-size: var(--font-lg); color: var(--color-on-surface); }

.error-state { display: flex; flex-direction: column; align-items: center; gap: var(--space-md); padding: var(--space-3xl); color: var(--color-error); }
</style>
