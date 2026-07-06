<template>
  <div class="invite-page">
    <div class="invite-card">
      <div
        v-if="state === 'loading'"
        class="invite-loading"
      >
        <div class="spinner" />
        <h1>Loading invitation...</h1>
      </div>

      <div
        v-else-if="state === 'valid'"
        class="invite-valid"
      >
        <div class="org-preview">
          <div class="org-avatar">
            {{ orgInitials }}
          </div>
          <h1>{{ invite.organisation_name }}</h1>
          <p class="org-slug">
            {{ invite.organisation_slug }}
          </p>
        </div>
        <p class="invite-text">
          You've been invited to join <strong>{{ invite.organisation_name }}</strong>
          as <span class="role-badge">{{ roleLabel(invite.role) }}</span>
        </p>

        <div
          v-if="needsAuth"
          class="auth-section"
        >
          <p class="auth-note">
            Create an account or sign in to accept.
          </p>
          <router-link
            :to="`/signup?invite=${token}`"
            class="btn-primary btn-full"
          >
            Create Account
          </router-link>
          <router-link
            :to="`/login?invite=${token}&redirect=/invite/${token}`"
            class="btn-secondary btn-full"
          >
            Sign In
          </router-link>
        </div>
        <button
          v-else
          class="btn-primary btn-full"
          :disabled="accepting"
          @click="acceptInvite"
        >
          <span
            v-if="accepting"
            class="spinner-sm"
          />
          <span v-else>Accept Invitation</span>
        </button>

        <p
          v-if="error"
          class="error-msg"
        >
          {{ error }}
        </p>
      </div>

      <div
        v-else-if="state === 'expired'"
        class="invite-expired"
      >
        <div class="error-icon">
          ⏰
        </div>
        <h1>Invitation expired</h1>
        <p>This invitation link has expired. Please ask the organisation admin to send a new one.</p>
        <router-link
          to="/login"
          class="btn-primary"
        >
          Go to Sign In
        </router-link>
      </div>

      <div
        v-else-if="state === 'accepted'"
        class="invite-accepted"
      >
        <div class="success-icon">
          🎉
        </div>
        <h1>Welcome aboard!</h1>
        <p>Redirecting to your new workspace...</p>
      </div>

      <div
        v-else
        class="invite-error"
      >
        <div class="error-icon">
          ❌
        </div>
        <h1>Invalid invitation</h1>
        <p>{{ error || 'This invitation link is invalid or has already been used.' }}</p>
        <router-link
          to="/login"
          class="btn-primary"
        >
          Go to Sign In
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../../shared/composables/useAuth'
import { useApi } from '../../shared/composables/useApi'

type State = 'loading' | 'valid' | 'expired' | 'invalid' | 'accepted' | 'error'

const route = useRoute()
const router = useRouter()
const { isAuthenticated } = useAuth()
const state = ref<State>('loading')
const error = ref('')
const accepting = ref(false)
const invite = ref({
  organisation_name: '',
  organisation_slug: '',
  role: 'member',
  email: '',
})

const token = computed(() => route.params.token as string)
const needsAuth = computed(() => !isAuthenticated.value)
const orgInitials = computed(() =>
  invite.value.organisation_name
    .split(' ')
    .map((w) => w[0]?.toUpperCase())
    .join('')
    .slice(0, 2)
)

function roleLabel(role: string) {
  const labels: Record<string, string> = {
    owner: 'Owner',
    admin: 'Administrator',
    member: 'Member',
    viewer: 'Viewer',
  }
  return labels[role] || role
}

async function loadInvitation() {
  try {
    const api = useApi()
    const { data } = await api.get(`/invitations/${token.value}`)
    invite.value = data
    state.value = 'valid'
  } catch (e: any) {
    const status = e.response?.status
    if (status === 410) state.value = 'expired'
    else if (status === 404) state.value = 'invalid'
    else {
      state.value = 'error'
      error.value = e.response?.data?.detail || 'Failed to load invitation'
    }
  }
}

async function acceptInvite() {
  accepting.value = true
  error.value = ''
  try {
    const api = useApi()
    await api.post(`/invitations/${token.value}/accept`)
    state.value = 'accepted'
    setTimeout(() => {
      router.push(`/${invite.value.organisation_slug}`)
    }, 1500)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to accept invitation'
  } finally {
    accepting.value = false
  }
}

onMounted(loadInvitation)
</script>

<style scoped>
.invite-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 24px;
}

.invite-card {
  background: #fff;
  border-radius: 12px;
  padding: 48px 40px;
  max-width: 480px;
  width: 100%;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.org-preview { margin-bottom: 20px; }
.org-avatar {
  width: 64px;
  height: 64px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border-radius: 16px;
  font-size: 24px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
}
.org-preview h1 { font-size: 22px; font-weight: 700; color: #202124; margin: 0 0 4px; }
.org-slug { font-size: 13px; color: #9aa0a6; }

.invite-text { font-size: 14px; color: #5f6368; margin-bottom: 24px; line-height: 1.5; }
.role-badge {
  display: inline-block;
  padding: 2px 10px;
  background: #e8f0fe;
  color: #1a73e8;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.auth-section { margin-bottom: 16px; }
.auth-note { font-size: 13px; color: #5f6368; margin-bottom: 16px; }

.btn-primary, .btn-secondary {
  display: inline-block;
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  border: none;
  transition: opacity 0.15s;
  margin-bottom: 10px;
}

.btn-primary { background: #1a73e8; color: #fff; }
.btn-primary:hover { opacity: 0.9; }
.btn-secondary { background: #e8eaed; color: #3c4043; }
.btn-secondary:hover { background: #d2d4d7; }
.btn-full { display: block; }
button.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.error-msg { color: #ea4335; font-size: 13px; margin-top: 12px; }
.spinner { width: 40px; height: 40px; border: 4px solid #dadce0; border-top-color: #1a73e8; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 24px; }
.spinner-sm { width: 14px; height: 14px; border: 2px solid transparent; border-top-color: currentColor; border-radius: 50%; animation: spin 0.6s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }

.success-icon, .error-icon { font-size: 48px; margin-bottom: 16px; }
.invite-card h1 { font-size: 24px; font-weight: 700; color: #202124; margin: 0 0 8px; }
.invite-card p { font-size: 14px; color: #5f6368; }
</style>
