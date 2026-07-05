import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Tenant, AIModel, Driver, SubscriptionPlan, Invoice } from '../shared/types/admin'
import { useApi } from '../shared/composables/useApi'

export const useAdminStore = defineStore('admin', () => {
  const tenants = ref<Tenant[]>([])
  const models = ref<AIModel[]>([])
  const drivers = ref<Driver[]>([])
  const plans = ref<SubscriptionPlan[]>([])
  const invoices = ref<Invoice[]>([])

  async function loadTenants() {
    try {
      const api = useApi()
      const { data } = await api.get<Tenant[]>('/tenants')
      tenants.value = data
    } catch (e: unknown) {
      console.error('[admin store] Failed to load tenants', e)
    }
  }

  async function loadModels() {
    try {
      const api = useApi()
      const { data } = await api.get<AIModel[]>('/ai/models')
      models.value = data
    } catch (e: unknown) {
      console.error('[admin store] Failed to load AI models', e)
    }
  }

  async function loadDrivers() {
    try {
      const api = useApi()
      const { data } = await api.get<Driver[]>('/ai/drivers')
      drivers.value = data
    } catch (e: unknown) {
      console.error('[admin store] Failed to load AI drivers', e)
    }
  }

  async function loadPlans() {
    try {
      const api = useApi()
      const { data } = await api.get<SubscriptionPlan[]>('/billing/plans')
      plans.value = data
    } catch (e: unknown) {
      console.error('[admin store] Failed to load subscription plans', e)
    }
  }

  async function loadInvoices() {
    try {
      const api = useApi()
      const { data } = await api.get<Invoice[]>('/billing/invoices')
      invoices.value = data
    } catch (e: unknown) {
      console.error('[admin store] Failed to load invoices', e)
    }
  }

  return {
    tenants, models, drivers, plans, invoices,
    loadTenants, loadModels, loadDrivers, loadPlans, loadInvoices,
  }
})
