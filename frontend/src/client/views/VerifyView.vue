<template>
  <div class="verify-page">
    <div class="verify-card">
      <div
        v-if="state === 'loading'"
        class="verify-loading"
      >
        <div class="spinner" />
        <h1>Verifying your email...</h1>
        <p>This will just take a moment</p>
      </div>

      <div
        v-else-if="state === 'success'"
        class="verify-success"
      >
        <div class="success-icon">
          ✅
        </div>
        <h1>Email verified!</h1>
        <p>You're all set. Redirecting to your workspace...</p>
      </div>

      <div
        v-else-if="state === 'expired'"
        class="verify-expired"
      >
        <div class="error-icon">
          ⏰
        </div>
        <h1>Link expired</h1>
        <p>This verification link has expired. We'll send you a new one.</p>
        <button
          class="btn-primary"
          :disabled="resending"
          @click="resendVerification"
        >
          <span
            v-if="resending"
            class="spinner-sm"
          />
          <span v-else>Resend verification email</span>
        </button>
        <p
          v-if="resent"
          class="success-msg"
        >
          ✅ New verification email sent!
        </p>
      </div>

      <div
        v-else-if="state === 'invalid'"
        class="verify-error"
      >
        <div class="error-icon">
          ❌
        </div>
        <h1>Invalid link</h1>
        <p>This verification link is invalid or has already been used.</p>
        <router-link
          to="/login"
          class="btn-primary"
        >
          Back to Sign In
        </router-link>
      </div>

      <div
        v-else
        class="verify-error"
      >
        <div class="error-icon">
          ⚠️
        </div>
        <h1>Something went wrong</h1>
        <p>{{ error || 'An unexpected error occurred.' }}</p>
        <router-link
          to="/login"
          class="btn-primary"
        >
          Back to Sign In
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '../../shared/composables/useApi'

type State = 'loading' | 'success' | 'expired' | 'invalid' | 'error'

const route = useRoute()
const router = useRouter()
const state = ref<State>('loading')
const error = ref('')
const resending = ref(false)
const resent = ref(false)

async function verify() {
  const token = route.query.token as string
  if (!token) {
    state.value = 'invalid'
    return
  }
  try {
    const api = useApi()
    await api.post('/auth/verify', { token })
    state.value = 'success'
    setTimeout(() => router.push('/workspaces'), 2000)
  } catch (e: any) {
    const status = e.response?.status
    const detail = e.response?.data?.detail || ''
    if (status === 410 || detail.includes('expired')) {
      state.value = 'expired'
    } else if (status === 404 || detail.includes('invalid')) {
      state.value = 'invalid'
    } else {
      state.value = 'error'
      error.value = detail
    }
  }
}

async function resendVerification() {
  resending.value = true
  try {
    const token = route.query.token as string
    const api = useApi()
    await api.post('/auth/resend-verification', { token })
    resent.value = true
  } catch (e: unknown) {
    console.error('[VerifyView] Failed to resend verification email', e)
  } finally {
    resending.value = false
  }
}

onMounted(verify)
</script>

<style scoped>
.verify-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 24px;
}

.verify-card {
  background: #fff;
  border-radius: 12px;
  padding: 48px 40px;
  max-width: 480px;
  width: 100%;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.verify-card h1 { font-size: 24px; font-weight: 700; color: #202124; margin: 0 0 8px; }
.verify-card p { font-size: 14px; color: #5f6368; }

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #dadce0;
  border-top-color: #1a73e8;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 24px;
}

@keyframes spin { to { transform: rotate(360deg); } }

.success-icon, .error-icon { font-size: 48px; margin-bottom: 16px; }

.btn-primary {
  display: inline-block;
  margin-top: 20px;
  padding: 10px 24px;
  background: #1a73e8;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  transition: opacity 0.15s;
}

.btn-primary:hover { opacity: 0.9; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.success-msg { color: #34a853; margin-top: 12px; font-weight: 500; }

.spinner-sm {
  width: 14px; height: 14px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}
</style>
