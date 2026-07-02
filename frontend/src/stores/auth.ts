import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AuthUser } from '../shared/types/client'
import { useApi } from '../shared/composables/useApi'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const user = ref<AuthUser | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  }

  function setUser(u: AuthUser) {
    user.value = u
  }

  function clearAuth() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  async function tryRefresh(): Promise<boolean> {
    if (!refreshToken.value) return false
    try {
      const api = useApi()
      const { data } = await api.post('/auth/refresh', {
        refresh_token: refreshToken.value,
      })
      setTokens(data.access_token, data.refresh_token)
      return true
    } catch (e: unknown) {
      console.error('[auth store] Token refresh failed', e)
      clearAuth()
      return false
    }
  }

  return {
    accessToken,
    refreshToken,
    user,
    isAuthenticated,
    setTokens,
    setUser,
    clearAuth,
    tryRefresh,
  }
})
