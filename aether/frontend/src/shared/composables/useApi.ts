import axios, { type AxiosInstance, type AxiosError } from 'axios'
import { useAuthStore } from '../../stores/auth'

// Priority: explicit env var > same-origin relative > direct backend
const API_BASE = import.meta.env.VITE_API_URL ||
  (typeof window !== 'undefined' && window.location.hostname === 'localhost'
    ? '/api/v1'  // use Vite proxy on dev
    : 'http://localhost:8000/api/v1')  // direct backend otherwise

let _api: AxiosInstance | null = null

export function useApi(): AxiosInstance {
  if (!_api) {
    _api = axios.create({
      baseURL: API_BASE,
      headers: { 'Content-Type': 'application/json' },
    })

    _api.interceptors.request.use((config) => {
      const auth = useAuthStore()
      if (auth.accessToken) {
        config.headers.Authorization = `Bearer ${auth.accessToken}`
      }
      return config
    })

    _api.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        if (error.response?.status === 401) {
          const auth = useAuthStore()
          const refreshed = await auth.tryRefresh()
          if (refreshed && error.config) {
            return _api!.request(error.config)
          }
        }
        return Promise.reject(error)
      }
    )
  }
  return _api
}

export function createApi(): AxiosInstance {
  return useApi()
}
