import type { BaseEntity, ChannelType, SubscriptionStatus } from './common'

export interface AuthUser {
  id: string
  email: string
  display_name: string
  avatar_url: string | null
  is_verified: boolean
  created_at: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface SignupPayload {
  email: string
  password: string
  tenant_slug: string
  display_name: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface Channel extends BaseEntity {
  tenant_id: string
  channel_type: ChannelType
  display_name: string
  is_active: boolean
  priority: number
  config: Record<string, unknown>
}

export interface Conversation extends BaseEntity {
  tenant_id: string
  channel_id: string
  organisation_id: string | null
  subject: string
  status: 'active' | 'archived' | 'closed'
  last_message_at: string | null
  last_message_preview: string | null
  unread_count: number
  assigned_to: string | null
  tags: string[]
}

export interface Message extends BaseEntity {
  tenant_id: string
  conversation_id: string
  user_id: string | null
  role: 'user' | 'assistant' | 'system'
  content: string
  metadata: Record<string, unknown> | null
}

export interface Organisation extends BaseEntity {
  tenant_id: string
  name: string
  slug: string
  logo_url: string | null
  is_active: boolean
}

export interface OrganisationMember {
  user_id: string
  full_name: string
  email: string
  role: string
  role_id: string | null
  invited_at: string | null
  accepted_at: string | null
}

export interface ServiceDefinition extends BaseEntity {
  tenant_id: string
  name: string
  display_name: string
  description: string | null
  icon: string | null
  is_active: boolean
}

export interface ServiceInstance extends BaseEntity {
  tenant_id: string
  definition_id: string
  name: string
  config: Record<string, unknown>
  is_active: boolean
}

export interface ServiceBinding extends BaseEntity {
  tenant_id: string
  instance_id: string
  channel_id: string
  config: Record<string, unknown>
  is_active: boolean
}

export interface ServiceExecution extends BaseEntity {
  tenant_id: string
  binding_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  input_data: Record<string, unknown> | null
  output_data: Record<string, unknown> | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

export interface Intent extends BaseEntity {
  tenant_id: string
  name: string
  display_name: string
  description: string | null
  examples: string[]
  is_active: boolean
}

export interface Entity extends BaseEntity {
  tenant_id: string
  name: string
  display_name: string
  type: string
  values: string[]
}

export interface KnowledgeBase extends BaseEntity {
  tenant_id: string
  name: string
  description: string | null
  document_count: number
}

export interface KnowledgeDocument extends BaseEntity {
  tenant_id: string
  knowledge_base_id: string
  title: string
  content_type: string
  size_bytes: number
  status: 'pending' | 'indexing' | 'ready' | 'error'
}

export interface SubscriptionInfo {
  plan_name: string
  status: SubscriptionStatus
  trial_ends_at: string | null
  current_period_end: string
  features: Record<string, unknown>
}

export interface WSMessage {
  type: string
  event?: string
  [key: string]: unknown
}
