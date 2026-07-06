<template>
  <div class="tenant-detail">
    <!-- Loading state -->
    <div v-if="loading" class="loading-state">
      <LoadingSpinner text="Loading tenant..." />
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
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.name"
          class="tab"
          :class="{ active: activeTab === tab.name }"
          @click="activeTab = tab.name"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">
        <!-- Details Tab -->
        <div v-if="activeTab === 'details'" class="tab-pane">
          <div class="section">
            <h2 class="section-title">Tenant Details</h2>
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">Tenant ID</span>
                <span class="detail-value">{{ tenant.id }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Created</span>
                <span class="detail-value">{{ formatDate(tenant.created_at) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Plan</span>
                <span class="detail-value">{{ tenant.plan || 'None' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Users</span>
                <span class="detail-value">{{ tenant.users ?? '0' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Channels</span>
                <span class="detail-value">{{ tenant.channels ?? '0' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Status</span>
                <span class="detail-value">{{ tenant.is_active ? 'Active' : 'Suspended' }}</span>
              </div>
            </div>
          </div>

          <div class="section">
            <h2 class="section-title">Billing Information</h2>
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">Subscription Status</span>
                <span class="detail-value">{{ tenant.subscription_status || 'None' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Billing Cycle</span>
                <span class="detail-value">{{ tenant.billing_cycle || 'Monthly' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">Next Billing Date</span>
                <span class="detail-value">{{ tenant.next_billing_date || 'N/A' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Users Tab -->
        <div v-else-if="activeTab === 'users'" class="tab-pane">
          <div class="section">
            <h2 class="section-title">Users</h2>
            <p>No users found for this tenant.</p>
          </div>
        </div>

        <!-- Activity Tab -->
        <div v-else-if="activeTab === 'activity'" class="tab-pane">
          <div class="section">
            <h2 class="section-title">Activity</h2>
            <p>No activity found for this tenant.</p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useApi } from '../../shared/composables/useApi'
import LoadingSpinner from '../../shared/components/LoadingSpinner.vue'

const route = useRoute()
const api = useApi()

const loading = ref(true)
const error = ref('')
const tenant = ref<any>(null)
const activeTab = ref('details')

const tabs = [
  { name: 'details', label: 'Details' },
  { name: 'users', label: 'Users' },
  { name: 'activity', label: 'Activity' },
]

function formatDate(date: string): string {
  return new Date(date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

async function loadTenant() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get(`/tenants/${route.params.id}`)
    tenant.value = data
  } catch (e: any) {
    error.value = e?.message || 'Failed to load tenant'
  } finally {
    loading.value = false
  }
}

onMounted(loadTenant)
</script>

<style scoped>
.tenant-detail { display: flex; flex-direction: column; gap: var(--space-lg); }

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-md);
}

.header-left {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
}

.header-info {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.org-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-lg);
  background: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: var(--font-xl);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.back-btn {
  padding: 4px 12px;
  font-size: var(--font-sm);
  background: transparent;
  color: var(--color-on-surface-variant);
}

.status-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: var(--radius-full);
  font-size: var(--font-sm);
  font-weight: 600;
}

.status-active {
  background: var(--color-success-light);
  color: var(--color-success);
}

.status-suspended {
  background: var(--color-warning-light);
  color: var(--color-warning);
}

.tabs {
  display: flex;
  gap: var(--space-sm);
  border-bottom: 1px solid var(--color-outline);
  padding-bottom: var(--space-sm);
}

.tab {
  padding: 8px 16px;
  border: none;
  background: transparent;
  color: var(--color-on-surface-variant);
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}

.tab.active {
  color: var(--color-primary);
  border-bottom: 2px solid var(--color-primary);
}

.tab-content { margin-top: var(--space-lg); }

.tab-pane {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.section {
  background: var(--color-surface);
  border: 1px solid var(--color-outline);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
  box-shadow: var(--shadow-sm);
}

.section-title {
  font-size: var(--font-lg);
  font-weight: 600;
  margin-bottom: var(--space-md);
  color: var(--color-on-surface);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--space-lg);
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.detail-label {
  font-size: var(--font-sm);
  color: var(--color-on-surface-variant);
}

.detail-value {
  font-size: var(--font-md);
  font-weight: 500;
  color: var(--color-on-surface);
}

.loading-state { display: flex; align-items: center; justify-content: center; min-height: 300px; }

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-md;
  padding: var(--space-3xl);
  color: var(--color-error);
}

@media (max-width: 768px) {
  .detail-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-right {
    align-self: flex-start;
  }
}
</style>
