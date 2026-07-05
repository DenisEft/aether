import { ref, computed } from 'vue'
import { useApi } from './useApi'
import type { Tenant } from '../types/admin'

const currentTenant = ref<Tenant | null>(null)
const tenants = ref<Tenant[]>([])

export function useTenant() {
  const slug = computed(() => currentTenant.value?.slug || '')

  async function loadTenant(tenantSlug: string): Promise<void> {
    try {
      const api = useApi()
      const { data } = await api.get<Tenant[]>('/tenants')
      const found = data.find((t) => t.slug === tenantSlug)
      if (found) currentTenant.value = found
    } catch (e: unknown) {
      console.error('[useTenant] Failed to load current tenant', e)
      currentTenant.value = null
    }
  }

  async function loadTenants(): Promise<void> {
    try {
      const api = useApi()
      const { data } = await api.get<Tenant[]>('/tenants')
      tenants.value = data
    } catch (e: unknown) {
      console.error('[useTenant] Failed to load tenants list', e)
    }
  }

  return { currentTenant, tenants, slug, loadTenant, loadTenants }
}
