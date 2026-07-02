export interface BaseEntity {
  id: string
  created_at: string
  updated_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export type ChannelType = 'telegram' | 'whatsapp' | 'email' | 'web_widget' | 'sms'
export type SubscriptionStatus = 'active' | 'trial' | 'cancelled' | 'expired' | 'past_due'
export type TenantStatus = 'active' | 'trial' | 'suspended' | 'deleted'
export type DriverStatus = 'online' | 'offline' | 'degraded' | 'error'
export type Environment = 'development' | 'staging' | 'production'

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'down'
  version: string
  uptime: number
  db: { status: string; latency_ms: number }
  redis: { status: string }
}
