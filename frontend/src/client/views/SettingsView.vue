<template>
  <div class="settings">
    <header class="settings-header">
      <h1>Settings</h1>
      <p>{{ tenantName }}</p>
    </header>

    <div class="settings-sections">
      <!-- ── PROFILE ── -->
      <section class="settings-section">
        <button
          class="section-toggle"
          :class="{ open: openSection === 'profile' }"
          @click="toggleSection('profile')"
        >
          <span class="section-icon">👤</span>
          <span class="section-label">Profile</span>
          <span class="section-arrow">▾</span>
        </button>
        <div v-if="openSection === 'profile'" class="section-body">
          <div class="field-row">
            <label class="field-label">Email</label>
            <div class="field-value" @click="startEdit('profile', 'email')">
              <span v-if="editingField !== 'profile.email'">{{ user?.email || '—' }}</span>
              <input
                v-else
                v-model="profileForm.email"
                class="inline-input"
                @blur="saveField('profile', 'email')"
                @keydown.enter="saveField('profile', 'email')"
                @keydown.escape="cancelEdit"
                ref="emailInput"
              />
            </div>
          </div>
          <div class="field-row">
            <label class="field-label">Display Name</label>
            <div class="field-value" @click="startEdit('profile', 'display_name')">
              <span v-if="editingField !== 'profile.display_name'">{{ user?.display_name || '—' }}</span>
              <input
                v-else
                v-model="profileForm.display_name"
                class="inline-input"
                @blur="saveField('profile', 'display_name')"
                @keydown.enter="saveField('profile', 'display_name')"
                @keydown.escape="cancelEdit"
                ref="nameInput"
              />
            </div>
          </div>
          <div class="field-row">
            <label class="field-label">Avatar</label>
            <div class="field-value avatar-field">
              <div class="avatar-preview" :style="{ background: avatarColor }">
                {{ userInitials }}
              </div>
              <input
                type="file"
                accept="image/*"
                @change="onAvatarChange"
                class="hidden-input"
                ref="avatarInput"
              />
              <button
                class="btn-secondary"
                @click="triggerAvatarUpload"
              >
                Upload Avatar
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- ── CHANNELS ── -->
      <section class="settings-section">
        <button
          class="section-toggle"
          :class="{ open: openSection === 'channels' }"
          @click="toggleSection('channels')"
        >
          <span class="section-icon">📡</span>
          <span class="section-label">Channels</span>
          <span class="section-badge">{{ channels.length }}</span>
          <span class="section-arrow">▾</span>
        </button>
        <div v-if="openSection === 'channels'" class="section-body">
          <div v-if="channels.length === 0" class="empty-row">
            No channels connected yet.
          </div>
          <div
            v-for="channel in channels"
            :key="channel.id"
            class="channel-row"
          >
            <div class="channel-info">
              <span class="channel-type-icon">{{ channelIcon(channel.channel_type) }}</span>
              <div>
                <div class="channel-name">{{ channel.display_name }}</div>
                <div class="channel-type-label">{{ channel.channel_type }}</div>
              </div>
            </div>
            <div class="channel-status-row">
              <span class="status-dot" :class="{ active: channel.is_active }" />
              <span class="status-text">{{ channel.is_active ? 'Connected' : 'Disconnected' }}</span>
            </div>
            <button
              class="btn-sm"
              :class="channel.is_active ? 'btn-danger-ghost' : 'btn-primary-ghost'"
              @click="toggleChannel(channel.id)"
            >
              {{ channel.is_active ? 'Disconnect' : 'Connect' }}
            </button>
          </div>
          <button class="btn-add-channel" disabled title="Coming soon">
            + Add Channel
          </button>
        </div>
      </section>

      <!-- ── AI MODELS ── -->
      <section class="settings-section">
        <button
          class="section-toggle"
          :class="{ open: openSection === 'ai' }"
          @click="toggleSection('ai')"
        >
          <span class="section-icon">🧠</span>
          <span class="section-label">AI Models</span>
          <span class="section-badge">{{ models.length }}</span>
          <span class="section-arrow">▾</span>
        </button>
        <div v-if="openSection === 'ai'" class="section-body">
          <div v-if="models.length === 0" class="empty-row">
            No AI models configured.
          </div>
          <div v-for="model in models" :key="model.id" class="model-row">
            <div class="model-info">
              <span class="model-name">{{ model.display_name }}</span>
              <span class="model-provider">{{ model.provider }}</span>
            </div>
            <div class="model-capabilities">
              <span v-for="cap in model.capabilities.slice(0, 3)" :key="cap" class="cap-tag">{{ cap }}</span>
              <span v-if="model.capabilities.length > 3" class="cap-tag cap-more">+{{ model.capabilities.length - 3 }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- ── TEAM ── -->
      <section class="settings-section">
        <button
          class="section-toggle"
          :class="{ open: openSection === 'team' }"
          @click="toggleSection('team')"
        >
          <span class="section-icon">👥</span>
          <span class="section-label">Team</span>
          <span class="section-badge">{{ members.length }}</span>
          <span class="section-arrow">▾</span>
        </button>
        <div v-if="openSection === 'team'" class="section-body">
          <!-- Owner/self is always there -->
          <div v-if="user" class="member-row">
            <div class="member-avatar" :style="{ background: avatarColor }">
              {{ userInitials }}
            </div>
            <div class="member-info">
              <span class="member-name">{{ user.display_name || user.email }} <span class="member-you">(you)</span></span>
              <span class="member-email">{{ user.email }}</span>
            </div>
            <span class="member-role role-owner">Owner</span>
          </div>
          <div v-for="member in members" :key="member.user_id" class="member-row">
            <div class="member-avatar" :style="{ background: memberAvatarColor(member.full_name) }">
              {{ (member.full_name || member.email || '?')[0].toUpperCase() }}
            </div>
            <div class="member-info">
              <span class="member-name">{{ member.full_name }}</span>
              <span class="member-email">{{ member.email }}</span>
            </div>
            <span class="member-role" :class="`role-${member.role.toLowerCase()}`">{{ member.role }}</span>
          </div>
          <div v-if="members.length === 0 && !user" class="empty-row">
            No team members.
          </div>
          <button class="btn-add-member" disabled title="Coming soon">
            + Invite Member
          </button>
        </div>
      </section>

      <!-- ── BILLING ── -->
      <section class="settings-section">
        <button
          class="section-toggle"
          :class="{ open: openSection === 'billing' }"
          @click="toggleSection('billing')"
        >
          <span class="section-icon">💳</span>
          <span class="section-label">Billing</span>
          <span class="section-arrow">▾</span>
        </button>
        <div v-if="openSection === 'billing'" class="section-body">
          <div class="billing-card">
            <div class="billing-plan">
              <span class="plan-name">Current Plan</span>
              <span class="plan-value">{{ planName || 'Free' }}</span>
            </div>
            <div class="billing-stat">
              <span class="stat-label">Status</span>
              <span class="stat-value" :class="subscriptionStatus">
                <span class="status-dot-sm" :class="subscriptionStatus" />
                {{ subStatusLabel }}
              </span>
            </div>
            <div class="billing-stat" v-if="subscriptionEnd">
              <span class="stat-label">Renews / Expires</span>
              <span class="stat-value">{{ subscriptionEnd }}</span>
            </div>
            <div class="billing-stat">
              <span class="stat-label">API Calls (this month)</span>
              <span class="stat-value">{{ usageStats.apiCalls.toLocaleString() }}</span>
            </div>
            <button class="btn-upgrade" disabled title="Coming soon">
              Upgrade Plan
            </button>
          </div>
        </div>
      </section>

      <!-- ── DANGER ZONE ── -->
      <section class="settings-section danger">
        <button
          class="section-toggle"
          :class="{ open: openSection === 'danger' }"
          @click="toggleSection('danger')"
        >
          <span class="section-icon">⚠️</span>
          <span class="section-label">Danger Zone</span>
          <span class="section-arrow">▾</span>
        </button>
        <div v-if="openSection === 'danger'" class="section-body">
          <p class="danger-warning">
            Once you delete your account, there is no going back. Please be certain.
          </p>
          <button class="btn-delete" @click="showDeleteConfirm = true">
            Delete Account
          </button>

          <!-- Confirm Dialog -->
          <div v-if="showDeleteConfirm" class="confirm-overlay" @click.self="showDeleteConfirm = false">
            <div class="confirm-dialog">
              <h3>Delete Account?</h3>
              <p>This action is permanent and cannot be undone. All your data will be permanently removed.</p>
              <div class="confirm-actions">
                <button class="btn-cancel" @click="showDeleteConfirm = false">Cancel</button>
                <button class="btn-confirm-delete" @click="deleteAccount">Delete Forever</button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from '../../shared/composables/useAuth'
import { useTenant } from '../../shared/composables/useTenant'
import { useWorkspaceStore } from '../../stores/workspace'
import { useAdminStore } from '../../stores/admin'
import type { ChannelType } from '../../shared/types/common'
import type { OrganisationMember } from '../../shared/types/client'

const route = useRoute()
const { currentUser: user } = useAuth()
const { currentTenant } = useTenant()
const workspaceStore = useWorkspaceStore()
const adminStore = useAdminStore()

// ── Computed ──
const tenantName = computed(() => currentTenant.value?.name || 'Workspace')
const userInitials = computed(() => {
  const name = user.value?.display_name || user.value?.email || 'U'
  return name.substring(0, 2).toUpperCase()
})
const avatarColor = computed(() => {
  const colors = ['#1a73e8', '#34a853', '#ea4335', '#fbbc04', '#8e24aa', '#00acc1']
  const name = user.value?.display_name || user.value?.email || '?'
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
})

// ── Accordion ──
const openSection = ref<string | null>(null)

function toggleSection(section: string) {
  openSection.value = openSection.value === section ? null : section
}

// ── Profile editing ──
const editingField = ref<string | null>(null)
const profileForm = ref({ email: '', display_name: '' })
const emailInput = ref<HTMLInputElement | null>(null)
const nameInput = ref<HTMLInputElement | null>(null)

function startEdit(section: string, field: string) {
  const key = `${section}.${field}`
  if (field === 'email') profileForm.value.email = user.value?.email || ''
  if (field === 'display_name') profileForm.value.display_name = user.value?.display_name || ''
  editingField.value = key
  nextTick(() => {
    if (field === 'email') emailInput.value?.focus()
    if (field === 'display_name') nameInput.value?.focus()
  })
}

async function saveField(section: string, field: string) {
  const api = useApi()
  try {
    const body: Record<string, string> = {}
    if (field === 'email') body.email = profileForm.value.email
    if (field === 'display_name') body.display_name = profileForm.value.display_name
    await api.patch('/api/v1/users/me', body)
    // Update local user state
    if (user.value) {
      if (field === 'email') user.value.email = profileForm.value.email
      if (field === 'display_name') user.value.display_name = profileForm.value.display_name
    }
    // Show success message
    showToast('Profile updated successfully', 'success')
  } catch (e: any) {
    if (e.response?.status === 401 || e.response?.status === 403) {
      // Handle unauthorized access
      const auth = useAuthStore()
      auth.clearAuth()
      window.location.href = '/login'
      return
    }
    console.error('Failed to save profile', e)
    showToast('Failed to update profile', 'error')
  }
  editingField.value = null
}

const avatarInput = ref<HTMLInputElement | null>(null)

function triggerAvatarUpload() {
  avatarInput.value?.click()
}

async function onAvatarChange(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files || input.files.length === 0) return

  const file = input.files[0]
  const api = useApi()
  try {
    const formData = new FormData()
    formData.append('avatar', file)
    const { data } = await api.post('/api/v1/users/me/avatar', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    // Update user state with new avatar
    if (user.value) {
      user.value = data
    }
    showToast('Avatar updated successfully', 'success')
  } catch (e: any) {
    if (e.response?.status === 401 || e.response?.status === 403) {
      // Handle unauthorized access
      const auth = useAuthStore()
      auth.clearAuth()
      window.location.href = '/login'
      return
    }
    console.error('Failed to upload avatar', e)
    showToast('Failed to upload avatar', 'error')
  }
}

function cancelEdit() {
  editingField.value = null
}

// ── Channels ──
const channels = computed(() => workspaceStore.channels)

function channelIcon(type: ChannelType): string {
  const map: Record<ChannelType, string> = { telegram: '📱', whatsapp: '💬', email: '✉️', web_widget: '🌐', sms: '📩' }
  return map[type] || '📡'
}

async function toggleChannel(id: string) {
  const api = useApi()
  try {
    const channel = channels.value.find(c => c.id === id)
    if (!channel) return
    await api.put(`/channels/${id}`, { is_enabled: !channel.is_enabled })
    await workspaceStore.loadChannels()
    console.log('Channel toggled:', id)
  } catch (e) {
    console.error('Failed to toggle channel', e)
  }
}

// ── AI Models ──
const models = computed(() => adminStore.models)

// ── Team ──
const members = ref<OrganisationMember[]>([])

function memberAvatarColor(name: string): string {
  const colors = ['#34a853', '#ea4335', '#fbbc04', '#8e24aa', '#00acc1', '#d81b60']
  let hash = 0
  for (let i = 0; i < (name || '?').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
}

// ── Billing ──
const planName = ref('Free')
const subscriptionStatus = ref<'active' | 'trial' | 'expired'>('active')
const subscriptionEnd = ref<string | null>(null)

const subStatusLabel = computed(() => {
  const map = { active: 'Active', trial: 'Trial', expired: 'Expired' }
  return map[subscriptionStatus.value] || 'Unknown'
})

const usageStats = ref({ apiCalls: 0 })

// ── Danger Zone ──
const showDeleteConfirm = ref(false)

async function deleteAccount() {
  showDeleteConfirm.value = false
  const api = useApi()
  try {
    await api.delete('/api/v1/users/me')
    // Clear auth and redirect to login
    const auth = useAuthStore()
    auth.clearAuth()
    localStorage.clear()
    window.location.href = '/login'
    showToast('Account deleted successfully', 'success')
  } catch (e: any) {
    if (e.response?.status === 401 || e.response?.status === 403) {
      // Handle unauthorized access
      const auth = useAuthStore()
      auth.clearAuth()
      window.location.href = '/login'
      return
    }
    console.error('Failed to delete account', e)
    showToast('Failed to delete account', 'error')
  }
}

// ── Lifecycle ──
onMounted(async () => {
  await workspaceStore.loadChannels()
  await adminStore.loadModels()
})
</script>

<style scoped>
.settings {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 24px 48px;
}

.settings-header {
  margin-bottom: 24px;
}
.settings-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #202124;
  margin-bottom: 4px;
}
.settings-header p {
  font-size: 13px;
  color: #5f6368;
}

/* ── Sections ── */
.settings-sections {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.settings-section {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}
.settings-section.danger {
  border-color: #fce8e6;
}

.section-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  text-align: left;
  transition: background 0.15s;
}
.section-toggle:hover {
  background: #f8f9fa;
}
.section-toggle.open {
  background: #f8f9fa;
}
.section-icon {
  font-size: 18px;
  flex-shrink: 0;
}
.section-label {
  flex: 1;
}
.section-badge {
  font-size: 11px;
  font-weight: 600;
  color: #5f6368;
  background: #e8eaed;
  padding: 1px 8px;
  border-radius: 10px;
}
.section-arrow {
  font-size: 12px;
  color: #80868b;
  transition: transform 0.2s;
}
.section-toggle.open .section-arrow {
  transform: rotate(180deg);
}

.section-body {
  padding: 0 16px 16px;
  border-top: 1px solid #f1f3f4;
}

/* ── Field Rows ── */
.field-row {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f1f3f4;
}
.field-row:last-child {
  border-bottom: none;
}
.field-label {
  width: 140px;
  font-size: 13px;
  font-weight: 500;
  color: #5f6368;
  flex-shrink: 0;
}
.field-value {
  flex: 1;
  font-size: 13px;
  color: #202124;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
  min-height: 28px;
  display: flex;
  align-items: center;
}
.field-value:hover {
  background: #f1f3f4;
}

.inline-input {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid #1a73e8;
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
}

.avatar-field {
  gap: 10px;
}
.avatar-preview {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.avatar-placeholder-text {
  font-size: 12px;
  color: #80868b;
  font-style: italic;
}

/* ── Channel Rows ── */
.channel-row {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f1f3f4;
  gap: 12px;
}
.channel-row:last-of-type {
  border-bottom: none;
}
.channel-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}
.channel-type-icon {
  font-size: 20px;
  flex-shrink: 0;
}
.channel-name {
  font-size: 13px;
  font-weight: 500;
  color: #202124;
}
.channel-type-label {
  font-size: 11px;
  color: #80868b;
  text-transform: capitalize;
}
.channel-status-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #dadce0;
}
.status-dot.active {
  background: #34a853;
}
.status-text {
  font-size: 12px;
  color: #5f6368;
}

.btn-sm {
  padding: 4px 12px;
  border-radius: 4px;
  border: none;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary-ghost {
  background: #e8f0fe;
  color: #1a73e8;
}
.btn-primary-ghost:hover {
  background: #d2e3fc;
}
.btn-danger-ghost {
  background: #fce8e6;
  color: #ea4335;
}
.btn-danger-ghost:hover {
  background: #f8d7da;
}

.btn-add-channel,
.btn-add-member {
  margin-top: 12px;
  padding: 8px 16px;
  border: 1px dashed #dadce0;
  border-radius: 6px;
  background: transparent;
  color: #5f6368;
  font-size: 13px;
  cursor: pointer;
  width: 100%;
  transition: all 0.15s;
}
.btn-add-channel:hover,
.btn-add-member:hover {
  border-color: #1a73e8;
  color: #1a73e8;
}

/* ── Model Rows ── */
.model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #f1f3f4;
  gap: 12px;
}
.model-row:last-of-type {
  border-bottom: none;
}
.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.model-name {
  font-size: 13px;
  font-weight: 500;
  color: #202124;
}
.model-provider {
  font-size: 11px;
  color: #80868b;
}
.model-capabilities {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.cap-tag {
  font-size: 10px;
  padding: 2px 6px;
  background: #e8f0fe;
  color: #1a73e8;
  border-radius: 4px;
  font-weight: 500;
}
.cap-more {
  background: #f1f3f4;
  color: #80868b;
}

/* ── Member Rows ── */
.member-row {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f1f3f4;
  gap: 10px;
}
.member-row:last-of-type {
  border-bottom: none;
}
.member-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.member-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.member-name {
  font-size: 13px;
  font-weight: 500;
  color: #202124;
}
.member-you {
  font-weight: 400;
  color: #80868b;
  font-size: 12px;
}
.member-email {
  font-size: 11px;
  color: #80868b;
}
.member-role {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: capitalize;
  flex-shrink: 0;
}
.role-owner { background: #e8f0fe; color: #1a73e8; }
.role-admin { background: #e6f4ea; color: #137333; }
.role-member { background: #f1f3f4; color: #5f6368; }
.role-viewer { background: #fef7e0; color: #b06000; }

/* ── Billing ── */
.billing-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}
.billing-plan {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.plan-name {
  font-size: 13px;
  color: #5f6368;
}
.plan-value {
  font-size: 16px;
  font-weight: 700;
  color: #202124;
}
.billing-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.stat-label {
  font-size: 13px;
  color: #5f6368;
}
.stat-value {
  font-size: 13px;
  color: #202124;
  display: flex;
  align-items: center;
  gap: 6px;
}
.stat-value.active { color: #137333; }
.stat-value.trial { color: #1a73e8; }
.stat-value.expired { color: #ea4335; }
.status-dot-sm {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.status-dot-sm.active { background: #34a853; }
.status-dot-sm.trial { background: #1a73e8; }
.status-dot-sm.expired { background: #ea4335; }

.btn-upgrade {
  margin-top: 4px;
  padding: 8px 16px;
  background: #1a73e8;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-upgrade:hover {
  background: #1557b0;
}

/* ── Danger Zone ── */
.danger-warning {
  font-size: 13px;
  color: #5f6368;
  margin-bottom: 12px;
  line-height: 1.5;
}
.btn-delete {
  padding: 8px 16px;
  background: #fff;
  color: #ea4335;
  border: 1px solid #ea4335;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-delete:hover {
  background: #fce8e6;
}

/* Confirm Dialog */
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.confirm-dialog {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}
.confirm-dialog h3 {
  font-size: 18px;
  font-weight: 600;
  color: #202124;
  margin-bottom: 8px;
}
.confirm-dialog p {
  font-size: 13px;
  color: #5f6368;
  line-height: 1.5;
  margin-bottom: 20px;
}
.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.btn-cancel {
  padding: 8px 16px;
  background: #f1f3f4;
  color: #3c4043;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.btn-cancel:hover {
  background: #e8eaed;
}
.btn-confirm-delete {
  padding: 8px 16px;
  background: #ea4335;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.btn-confirm-delete:hover {
  background: #c5221f;
}

.hidden-input {
  display: none;
}

/* ── Shared ── */
.empty-row {
  padding: 16px 0;
  font-size: 13px;
  color: #80868b;
  font-style: italic;
  text-align: center;
}
</style>
