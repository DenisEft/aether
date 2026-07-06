import { ref, computed } from 'vue'
import { useAuthStore } from '../../stores/auth'
import type { SignupPayload, LoginPayload } from '../types/client'
import { useApi } from './useApi'

export function useAuth() {
  const store = useAuthStore()
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => store.isAuthenticated)
  const currentUser = computed(() => store.user)

  async function signup(payload: SignupPayload): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const api = useApi()
      const { data } = await api.post('/auth/signup', payload)
      store.setTokens(data.access_token, data.refresh_token)
      store.setUser(data.user)
      return true
    } catch (e: unknown) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      error.value = detail || 'Signup failed'
      console.error('[useAuth] Signup failed', e)
      return false
    } finally {
      loading.value = false
    }
  }

  async function login(payload: LoginPayload): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const api = useApi()
      console.log('[useAuth] login: posting to', api.defaults.baseURL + '/auth/login', 'payload:', { ...payload, password: '***' })
      const { data } = await api.post('/auth/login', payload)
      console.log('[useAuth] login: response', { access_token: data.access_token?.slice(0,20)+'...', refresh_token: !!data.refresh_token })
      store.setTokens(data.access_token, data.refresh_token)
      console.log('[useAuth] login: tokens set, fetching user...')
      await fetchUser()
      console.log('[useAuth] login: user fetched, returning true')
      return true
    } catch (e: unknown) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const msg = detail || (e instanceof Error ? e.message : 'Login failed')
      console.error('[useAuth] Login failed:', msg, e)
      error.value = msg
      return false
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      const api = useApi()
      await api.post('/auth/logout')
    } catch (e: unknown) {
      console.error('[useAuth] Logout API call failed', e)
    }
    store.clearAuth()
  }

  async function fetchUser(): Promise<void> {
    try {
      const api = useApi()
      console.log('[useAuth] fetchUser: GET', api.defaults.baseURL + '/users/me')
      const { data } = await api.get('/users/me')
      console.log('[useAuth] fetchUser: got user', data.email)
      store.setUser(data)
    } catch (e: unknown) {
      console.error('[useAuth] Failed to fetch current user', e)
    }
  }

  async function updateProfile(displayName: string, email: string): Promise<boolean> {
    try {
      const api = useApi()
      const { data } = await api.patch('/api/v1/users/me', { display_name: displayName, email })
      store.setUser(data)
      return true
    } catch (e: unknown) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const msg = detail || (e instanceof Error ? e.message : 'Failed to update profile')
      console.error('[useAuth] Update profile failed:', msg, e)
      error.value = msg
      return false
    }
  }

  async function uploadAvatar(imageFile: File): Promise<boolean> {
    try {
      const api = useApi()
      const formData = new FormData()
      formData.append('avatar', imageFile)
      const { data } = await api.post('/api/v1/users/me/avatar', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      store.setUser(data)
      return true
    } catch (e: unknown) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const msg = detail || (e instanceof Error ? e.message : 'Failed to upload avatar')
      console.error('[useAuth] Upload avatar failed:', msg, e)
      error.value = msg
      return false
    }
  }

  async function deleteAccount(): Promise<boolean> {
    try {
      const api = useApi()
      await api.delete('/api/v1/users/me')
      store.clearAuth()
      return true
    } catch (e: unknown) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const msg = detail || (e instanceof Error ? e.message : 'Failed to delete account')
      console.error('[useAuth] Delete account failed:', msg, e)
      error.value = msg
      return false
    }
  }

  async function tryRestoreSession(): Promise<boolean> {
    const token = store.accessToken
    if (!token) return false
    try {
      await fetchUser()
      return true
    } catch (e: unknown) {
      console.error('[useAuth] Failed to restore auth session', e)
      store.clearAuth()
      return false
    }
  }

  return {
    loading,
    error,
    isAuthenticated,
    currentUser,
    signup,
    login,
    logout,
    fetchUser,
    updateProfile,
    uploadAvatar,
    deleteAccount,
    tryRestoreSession,
  }
}
