<template>
  <div class="signup-page">
    <div class="signup-card">
      <div class="brand">
        <h1 class="brand-name">
          Create account
        </h1>
        <p class="brand-tagline">
          Set up your Aether workspace
        </p>
      </div>

      <form
        class="signup-form"
        @submit.prevent="handleSignup"
      >
        <div
          v-if="error"
          class="form-error"
        >
          {{ error }}
        </div>

        <div class="field">
          <label for="display_name">Full Name</label>
          <input
            id="display_name"
            v-model="displayName"
            type="text"
            placeholder="Jane Smith"
            required
          >
        </div>

        <div class="field">
          <label for="email">Work Email</label>
          <input
            id="email"
            v-model="email"
            type="email"
            placeholder="jane@company.com"
            required
          >
        </div>

        <div class="field">
          <label for="slug">Workspace Slug</label>
          <input
            id="slug"
            v-model="tenantSlug"
            type="text"
            placeholder="your-company"
            required
          >
          <span class="hint">Letters, numbers, hyphens only. This becomes your URL.</span>
        </div>

        <div class="field">
          <label for="password">Password</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="Min 8 characters"
            required
            minlength="8"
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
          <span v-else>Create Workspace</span>
        </button>
      </form>

      <div class="links">
        <router-link to="/login">
          Already have an account? Sign in
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../../shared/composables/useAuth'

const router = useRouter()
const { signup, loading, error } = useAuth()
const displayName = ref('')
const email = ref('')
const tenantSlug = ref('')
const password = ref('')

async function handleSignup() {
  const ok = await signup({
    display_name: displayName.value,
    email: email.value,
    tenant_slug: tenantSlug.value,
    password: password.value,
  })
  if (ok) {
    router.push(`/${tenantSlug.value}`)
  }
}
</script>

<style scoped>
.signup-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 24px;
}

.signup-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  width: 100%;
  max-width: 440px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.brand { text-align: center; margin-bottom: 28px; }
.brand-name { font-size: 24px; font-weight: 700; color: #202124; margin-bottom: 4px; }
.brand-tagline { font-size: 13px; color: #9aa0a6; }

.form-error { background: #fce8e6; color: #c5221f; padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 16px; }

.field { margin-bottom: 16px; }
.field label { display: block; font-size: 12px; font-weight: 600; color: #5f6368; margin-bottom: 6px; }
.field input { width: 100%; padding: 10px 14px; border: 1px solid #dadce0; border-radius: 8px; font-size: 14px; outline: none; transition: border 0.15s; }
.field input:focus { border-color: #667eea; }
.hint { font-size: 11px; color: #9aa0a6; margin-top: 4px; display: block; }

.submit-btn { width: 100%; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: opacity 0.15s; }
.submit-btn:hover:not(:disabled) { opacity: 0.9; }
.submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.links { text-align: center; margin-top: 20px; font-size: 13px; }
.links a { color: #1a73e8; }
.spinner { width: 18px; height: 18px; border: 2px solid transparent; border-top-color: currentColor; border-radius: 50%; animation: spin 0.6s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
