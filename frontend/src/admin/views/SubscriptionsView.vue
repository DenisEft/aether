<template>
  <div class="subscriptions">
    <div class="page-header">
      <h1>Subscription Plans</h1>
      <button
        v-if="!showForm"
        class="btn btn-primary"
        @click="showForm = true"
      >
        <span class="btn-icon">+</span> Create Plan
      </button>
    </div>

    <!-- Inline Create Form -->
    <div
      v-if="showForm"
      class="card create-form"
    >
      <h3 class="card-title">
        New Plan
      </h3>
      <div class="form-grid">
        <div class="form-group">
          <label>Plan Name</label>
          <input
            v-model="form.name"
            class="form-input"
            placeholder="Pro"
          >
        </div>
        <div class="form-group">
          <label>Slug</label>
          <input
            v-model="form.slug"
            class="form-input"
            placeholder="pro"
          >
        </div>
        <div class="form-group">
          <label>Monthly Price (USD)</label>
          <input
            v-model.number="form.priceMonthly"
            type="number"
            class="form-input"
            min="0"
            step="0.01"
          >
        </div>
        <div class="form-group">
          <label>Yearly Price (USD)</label>
          <input
            v-model.number="form.priceYearly"
            type="number"
            class="form-input"
            min="0"
            step="0.01"
          >
        </div>
        <div class="form-group">
          <label>Tier</label>
          <input
            v-model.number="form.tier"
            type="number"
            class="form-input"
            min="1"
          >
        </div>
        <div class="form-group">
          <label>Features (comma-separated)</label>
          <input
            v-model="form.features"
            class="form-input"
            placeholder="Unlimited channels, AI analytics, Priority support"
          >
        </div>
        <div class="form-group checkbox-group">
          <label class="checkbox-label">
            <input
              v-model="form.isPublic"
              type="checkbox"
            >
            Public plan
          </label>
        </div>
      </div>
      <div class="form-actions">
        <button
          class="btn btn-ghost"
          @click="showForm = false"
        >
          Cancel
        </button>
        <button
          class="btn btn-primary"
          :disabled="!form.name || !form.slug || saving"
          @click="createPlan"
        >
          {{ saving ? 'Saving...' : 'Create Plan' }}
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div
      v-if="loading"
      class="plans-grid"
    >
      <div
        v-for="n in 4"
        :key="n"
        class="skeleton-card"
        :style="{ animationDelay: `${n * 100}ms` }"
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
        @click="loadPlans"
      >
        Retry
      </button>
    </div>

    <!-- Empty -->
    <div
      v-else-if="plans.length === 0"
      class="empty-state"
    >
      <span class="empty-icon">📦</span>
      <h3>No subscription plans</h3>
      <p>Create your first plan to get started</p>
    </div>

    <!-- Plans grid -->
    <div
      v-else
      class="plans-grid"
    >
      <div
        v-for="plan in plans"
        :key="plan.id"
        class="plan-card"
      >
        <div class="plan-header">
          <h3 class="plan-name">
            {{ plan.name }}
          </h3>
          <span class="plan-tier">Tier {{ plan.tier }}</span>
        </div>
        <div class="plan-price">
          <span class="price-amount">${{ plan.price_monthly_usd }}</span>
          <span class="price-period">/month</span>
        </div>
        <ul class="plan-features">
          <li
            v-for="(feat, i) in planFeatures(plan)"
            :key="i"
            class="feature-item"
          >
            <span class="feature-check">✓</span> {{ feat }}
          </li>
        </ul>
        <div class="plan-stats">
          <span class="active-count">
            <strong>{{ plan.active_tenants ?? 0 }}</strong> active tenants
          </span>
          <span
            v-if="!plan.is_public"
            class="private-badge"
          >Private</span>
        </div>
        <div class="plan-actions">
          <button
            class="btn btn-ghost btn-sm"
            @click="editPlan(plan)"
          >
            Edit
          </button>
          <button
            class="btn btn-ghost btn-sm btn-danger-text"
            @click="archivePlan(plan)"
          >
            {{ plan.is_archived ? 'Restore' : 'Archive' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Edit Modal -->
    <Teleport to="body">
      <div
        v-if="editingPlan"
        class="modal-backdrop"
        @click.self="editingPlan = null"
      >
        <div class="modal">
          <div class="modal-header">
            <h2>Edit Plan</h2>
            <button
              class="modal-close"
              @click="editingPlan = null"
            >
              ✕
            </button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>Plan Name</label>
              <input
                v-model="editForm.name"
                class="form-input"
              >
            </div>
            <div class="form-group">
              <label>Monthly Price (USD)</label>
              <input
                v-model.number="editForm.priceMonthly"
                type="number"
                class="form-input"
                min="0"
                step="0.01"
              >
            </div>
            <div class="form-group">
              <label>Yearly Price (USD)</label>
              <input
                v-model.number="editForm.priceYearly"
                type="number"
                class="form-input"
                min="0"
                step="0.01"
              >
            </div>
            <div class="form-group">
              <label>Features (comma-separated)</label>
              <input
                v-model="editForm.features"
                class="form-input"
              >
            </div>
            <div class="form-group checkbox-group">
              <label class="checkbox-label">
                <input
                  v-model="editForm.isPublic"
                  type="checkbox"
                >
                Public plan
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button
              class="btn btn-ghost"
              @click="editingPlan = null"
            >
              Cancel
            </button>
            <button
              class="btn btn-primary"
              :disabled="savingEdit"
              @click="saveEdit"
            >
              {{ savingEdit ? 'Saving...' : 'Save' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useApi } from '../../shared/composables/useApi'

const api = useApi()

const loading = ref(true)
const error = ref('')
const plans = ref<any[]>([])
const showForm = ref(false)
const saving = ref(false)
const savingEdit = ref(false)
const editingPlan = ref<any>(null)

const form = reactive({
  name: '',
  slug: '',
  priceMonthly: 0,
  priceYearly: 0,
  tier: 1,
  features: '',
  isPublic: true,
})

const editForm = reactive({
  name: '',
  priceMonthly: 0,
  priceYearly: 0,
  features: '',
  isPublic: true,
})

function planFeatures(plan: any): string[] {
  if (Array.isArray(plan.features)) return plan.features
  if (typeof plan.features === 'string') return plan.features.split(',').map((s: string) => s.trim()).filter(Boolean)
  if (plan.features && typeof plan.features === 'object') return Object.values(plan.features) as string[]
  return []
}

async function loadPlans() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/billing/plans')
    plans.value = data.items || data || []
  } catch (e: any) {
    error.value = e?.message || 'Failed to load plans'
  } finally {
    loading.value = false
  }
}

async function createPlan() {
  saving.value = true
  try {
    const features = form.features.split(',').map(s => s.trim()).filter(Boolean)
    await api.post('/billing/plans', {
      name: form.name,
      slug: form.slug,
      price_monthly_usd: form.priceMonthly,
      price_yearly_usd: form.priceYearly,
      tier: form.tier,
      features,
      is_public: form.isPublic,
    })
    showForm.value = false
    form.name = ''; form.slug = ''; form.priceMonthly = 0; form.priceYearly = 0
    form.tier = 1; form.features = ''; form.isPublic = true
    await loadPlans()
  } catch (e: unknown) {
    console.error('[SubscriptionsView] Failed to create subscription plan', e)
  } finally { saving.value = false }
}

function editPlan(plan: any) {
  editingPlan.value = plan
  editForm.name = plan.name
  editForm.priceMonthly = plan.price_monthly_usd
  editForm.priceYearly = plan.price_yearly_usd
  editForm.features = Array.isArray(plan.features) ? plan.features.join(', ') : (plan.features || '')
  editForm.isPublic = plan.is_public
}

async function saveEdit() {
  if (!editingPlan.value) return
  savingEdit.value = true
  try {
    const features = editForm.features.split(',').map(s => s.trim()).filter(Boolean)
    await api.patch(`/billing/plans/${editingPlan.value.id}`, {
      name: editForm.name,
      price_monthly_usd: editForm.priceMonthly,
      price_yearly_usd: editForm.priceYearly,
      features,
      is_public: editForm.isPublic,
    })
    editingPlan.value = null
    await loadPlans()
  } catch (e: unknown) {
    console.error('[SubscriptionsView] Failed to save subscription plan edit', editingPlan.value?.id, e)
  } finally { savingEdit.value = false }
}

async function archivePlan(plan: any) {
  const action = plan.is_archived ? 'restore' : 'archive'
  try {
    await api.post(`/billing/plans/${plan.id}/${action}`)
    await loadPlans()
  } catch (e: unknown) {
    console.error('[SubscriptionsView] Failed to archive/restore subscription plan', plan.id, e)
  }
}

onMounted(loadPlans)
</script>

<style scoped>
.subscriptions { display: flex; flex-direction: column; gap: var(--space-lg); }

.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-header h1 { font-size: var(--font-2xl); font-weight: 700; color: var(--color-on-surface); }

.btn { display: inline-flex; align-items: center; gap: var(--space-xs); padding: 6px 16px; border: none; border-radius: var(--radius-sm); font-size: var(--font-sm); font-weight: 500; cursor: pointer; }
.btn-primary { background: var(--color-primary); color: #fff; }
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-ghost { background: transparent; color: var(--color-on-surface-variant); }
.btn-ghost:hover { background: var(--color-primary-light); }
.btn-sm { padding: 4px 12px; font-size: var(--font-xs); }
.btn-icon { font-size: 18px; line-height: 1; }
.btn-danger-text { color: var(--color-error); }
.btn-danger-text:hover { background: var(--color-error-light); }

.card {
  background: var(--color-surface); border: 1px solid var(--color-outline);
  border-radius: var(--radius-md); padding: var(--space-lg); box-shadow: var(--shadow-sm);
}
.card-title { font-size: var(--font-lg); font-weight: 600; margin-bottom: var(--space-md); color: var(--color-on-surface); }

/* Create form */
.create-form { margin-bottom: var(--space-md); }
.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-md); }
.form-group { display: flex; flex-direction: column; gap: var(--space-xs); }
.form-group label { font-size: var(--font-sm); font-weight: 500; color: var(--color-on-surface-variant); }
.form-input { padding: 8px 12px; border: 1px solid var(--color-outline); border-radius: var(--radius-sm); font-size: var(--font-md); outline: none; color: var(--color-on-surface); background: var(--color-surface); }
.form-input:focus { border-color: var(--color-primary); }
.checkbox-group { align-self: flex-end; justify-content: center; }
.checkbox-label { display: flex; align-items: center; gap: var(--space-sm); cursor: pointer; font-size: var(--font-md); }
.form-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: var(--space-sm); margin-top: var(--space-sm); }

/* Plans grid */
.plans-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--space-lg); }
.plan-card {
  background: var(--color-surface); border: 1px solid var(--color-outline);
  border-radius: var(--radius-md); padding: var(--space-lg);
  display: flex; flex-direction: column; gap: var(--space-md);
  box-shadow: var(--shadow-sm); transition: box-shadow 0.15s;
}
.plan-card:hover { box-shadow: var(--shadow-md); }
.plan-header { display: flex; align-items: center; justify-content: space-between; }
.plan-name { font-size: var(--font-lg); font-weight: 700; color: var(--color-on-surface); }
.plan-tier { font-size: var(--font-xs); padding: 2px 8px; border-radius: var(--radius-full); background: var(--color-primary-light); color: var(--color-primary); font-weight: 600; }
.plan-price { display: flex; align-items: baseline; gap: 2px; }
.price-amount { font-size: var(--font-3xl); font-weight: 700; color: var(--color-on-surface); }
.price-period { font-size: var(--font-sm); color: var(--color-on-surface-variant); }
.plan-features { list-style: none; padding: 0; display: flex; flex-direction: column; gap: var(--space-sm); flex: 1; }
.feature-item { display: flex; align-items: center; gap: var(--space-sm); font-size: var(--font-sm); color: var(--color-on-surface); }
.feature-check { color: var(--color-success); font-weight: 700; }
.plan-stats { display: flex; align-items: center; justify-content: space-between; font-size: var(--font-sm); color: var(--color-on-surface-variant); }
.private-badge { font-size: var(--font-xs); padding: 1px 8px; border-radius: var(--radius-full); background: var(--color-surface-variant); color: var(--color-on-surface-variant); }
.plan-actions { display: flex; gap: var(--space-xs); padding-top: var(--space-sm); border-top: 1px solid var(--color-outline); }

/* Modal */
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: var(--color-surface); border-radius: var(--radius-lg); width: 90%; max-width: 480px; box-shadow: var(--shadow-xl); }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: var(--space-lg); border-bottom: 1px solid var(--color-outline); }
.modal-header h2 { font-size: var(--font-lg); font-weight: 600; }
.modal-close { background: none; border: none; font-size: 18px; cursor: pointer; color: var(--color-on-surface-variant); padding: 4px 8px; border-radius: var(--radius-sm); }
.modal-close:hover { background: var(--color-surface-variant); }
.modal-body { padding: var(--space-lg); display: flex; flex-direction: column; gap: var(--space-md); }
.modal-footer { display: flex; justify-content: flex-end; gap: var(--space-sm); padding: var(--space-lg); border-top: 1px solid var(--color-outline); }

/* Skeleton */
.skeleton-card { background: var(--color-surface); border: 1px solid var(--color-outline); border-radius: var(--radius-md); height: 260px; animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

.empty-state { display: flex; flex-direction: column; align-items: center; padding: var(--space-3xl); gap: var(--space-sm); color: var(--color-on-surface-variant); }
.empty-icon { font-size: 48px; }
.empty-state h3 { font-size: var(--font-lg); color: var(--color-on-surface); }

.error-state { display: flex; flex-direction: column; align-items: center; gap: var(--space-md); padding: var(--space-3xl); color: var(--color-error); }

@media (max-width: 640px) {
  .form-grid { grid-template-columns: 1fr; }
  .plans-grid { grid-template-columns: 1fr; }
}
</style>
