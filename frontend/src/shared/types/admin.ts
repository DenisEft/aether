import type { BaseEntity, ChannelType } from './common'

export interface Tenant extends BaseEntity {
  slug: string
  name: string
  domain: string | null
  logo_url: string | null
  primary_color: string
  is_active: boolean
  settings: Record<string, unknown>
}

export interface TenantConfig {
  id: string
  tenant_id: string
  key: string
  value: unknown
}

export interface TenantFeature {
  id: string
  tenant_id: string
  feature_key: string
  enabled: boolean
  quota: number | null
  used: number
}

export interface TenantLimit {
  id: string
  tenant_id: string
  limit_key: string
  max_value: number
  current_value: number
}

export interface TenantDomain {
  id: string
  tenant_id: string
  domain: string
  is_primary: boolean
  is_verified: boolean
}

export interface AIModel extends BaseEntity {
  tenant_id: string | null
  provider: string
  model_id: string
  display_name: string
  capabilities: string[]
  cost_per_1k_input: number
  cost_per_1k_output: number
  is_active: boolean
  priority: number
}

export interface Driver extends BaseEntity {
  tenant_id: string | null
  driver_type: string
  endpoint_url: string
  status: string
  priority: number
  config: Record<string, unknown>
  last_heartbeat: string | null
}

export interface DriverMetric {
  id: string
  driver_id: string
  latency_ms: number
  error_count: number
  request_count: number
  recorded_at: string
}

export interface SubscriptionPlan extends BaseEntity {
  name: string
  slug: string
  price_monthly_usd: number
  price_yearly_usd: number
  features: Record<string, unknown>
  is_public: boolean
  tier: number
}

export interface Subscription extends BaseEntity {
  tenant_id: string
  plan_id: string
  status: string
  trial_ends_at: string | null
  current_period_start: string
  current_period_end: string
  cancel_at_period_end: boolean
}

export interface Invoice extends BaseEntity {
  tenant_id: string
  subscription_id: string
  amount_usd: number
  currency: string
  status: string
  due_date: string
  paid_at: string | null
  invoice_pdf_url: string | null
}

export interface UsageRecord extends BaseEntity {
  tenant_id: string
  metric: string
  value: number
  recorded_at: string
}
