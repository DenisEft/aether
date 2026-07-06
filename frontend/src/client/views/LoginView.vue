<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <h1 class="brand-name">
          Aether
        </h1>
        <p class="brand-tagline">
          AI Customer Experience Platform
        </p>
      </div>

      <form
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <div
          v-if="error"
          class="form-error"
        >
          {{ error }}
        </div>

        <div class="field">
          <label for="email">Email</label>
          <input
            id="email"
            v-model="email"
            type="email"
            placeholder="you@company.com"
            autocomplete="username"
            required
          >
        </div>

        <div class="field">
          <label for="password">Password</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="••••••••"
            autocomplete="current-password"
            required
          >
        </div>

        <button
          type="submit"
          class="submit-btn"
          :disabled="loading"
        >
          <span
            v-if="loading"
            class="spinner"
          />
          <span v-else>Sign In</span>
        </button>
      </form>

      <div class="links">
        <router-link to="/signup">
          Create account
        </router-link>
        <span class="sep">·</span>
        <a href="#">Forgot password?</a>
      </div>
    </div>

    <div class="status-bar">
      <span
        class="status-dot"
        :class="healthClass"
      />
      <span class="status-text">{{ healthStatus }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../../shared/composables/useAuth'
import { useApi } from '../../shared/composables/useApi'
import type { HealthStatus } from '../../shared/types/common'

const router = useRouter()
const { login, loading, error } = useAuth()
const email = ref('')
const password = ref('')
const healthStatus = ref('connecting…')
const healthClass = ref('loading')

async function handleLogin() {
  const ok = await login({ email: email.value, password: password.value })
  if (ok) {
    router.push('/workspaces')
  }
}

async function checkHealth() {
  try {
    const api = useApi()
    const { data } = await api.get<HealthStatus>('/health', { baseURL: '/api/v1' })
    healthStatus.value = `${data.status} · v${data.version} · ${data.db.latency_ms}ms`
    healthClass.value = data.status === 'ok' ? 'ok' : data.status === 'degraded' ? 'degraded' : 'down'
  } catch (e: unknown) {
    console.error('[LoginView] Health check failed', e)
    healthStatus.value = 'unreachable'
    healthClass.value = 'down'
  }
}

onMounted(checkHealth)
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 24px;
}

.login-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.brand {
  text-align: center;
  margin-bottom: 32px;
}

.brand-name {
  font-size: 32px;
  font-weight: 800;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 4px;
}

.brand-tagline {
  font-size: 13px;
  color: #9aa0a6;
}

.form-error {
  background: #fce8e6;
  color: #c5221f;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 16px;
}

.field {
  margin-bottom: 16px;
}

.field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #5f6368;
  margin-bottom: 6px;
}

.field input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #dadce0;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border 0.15s;
}

.field input:focus {
  border-color: #667eea;
}

.submit-btn {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
  margin-top: 8px;
}

.submit-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.links {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: #5f6368;
}

.links a {
  color: #1a73e8;
}

.sep {
  margin: 0 8px;
}

.status-bar {
  margin-top: 24px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 11px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f9ab00;
}

.status-dot.ok { background: #34a853; }
.status-dot.degraded { background: #f9ab00; }
.status-dot.down { background: #ea4335; }
.status-dot.loading { background: #dadce0; animation: pulse 1s infinite; }

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
