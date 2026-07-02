-- ============================================================================
-- Aether Platform — Database Schema (PostgreSQL 16)
-- ============================================================================
-- Tenant isolation via RLS. Every business table has tenant_id.
-- All PKs are UUIDv4. All timestamps are timestamptz.
-- ============================================================================

-- ============================================================================
-- EXTENSIONS
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- ENUM TYPES
-- ============================================================================
CREATE TYPE channel_type_enum AS ENUM (
    'telegram', 'web_widget', 'email', 'whatsapp', 'rest_api'
);

CREATE TYPE conversation_status AS ENUM (
    'active', 'closed', 'archived'
);

CREATE TYPE message_role AS ENUM (
    'user', 'assistant', 'system'
);

CREATE TYPE subscription_status AS ENUM (
    'active', 'trial', 'cancelled', 'expired', 'past_due'
);

CREATE TYPE invoice_status AS ENUM (
    'draft', 'open', 'paid', 'void', 'past_due'
);

CREATE TYPE credential_type_enum AS ENUM (
    'api_key', 'bot_token', 'smtp_password', 'oauth_token'
);

CREATE TYPE usage_period AS ENUM (
    'hourly', 'daily', 'monthly'
);

CREATE TYPE entity_value_type AS ENUM (
    'string', 'number', 'date', 'email', 'phone'
);

CREATE TYPE execution_result AS ENUM (
    'success', 'error', 'partial'
);

-- ============================================================================
-- TENANTS
-- ============================================================================

CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL,
    name            TEXT NOT NULL,
    domain          TEXT,
    logo_url        TEXT,
    primary_color   TEXT NOT NULL DEFAULT '#1a73e8',
    timezone        TEXT NOT NULL DEFAULT 'UTC',
    locale          TEXT NOT NULL DEFAULT 'ru',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE tenants IS 'Platform tenants — each represents a company workspace';
COMMENT ON COLUMN tenants.slug IS 'URL-safe unique identifier: /aether/{slug}';
COMMENT ON COLUMN tenants.settings IS 'White-label, features, limits overrides';

CREATE UNIQUE INDEX ix_tenants_slug ON tenants (slug) WHERE is_active = TRUE;
CREATE UNIQUE INDEX ix_tenants_domain ON tenants (domain) WHERE domain IS NOT NULL AND is_active = TRUE;

-- ============================================================================
-- ORGANISATIONS (multi-org model)
-- ============================================================================

CREATE TABLE organisations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL,
    logo_url        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_orgs_slug_tenant ON organisations (tenant_id, slug);

-- ============================================================================
-- USERS & ROLES
-- ============================================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email           TEXT NOT NULL,
    hashed_password TEXT,
    full_name       TEXT,
    avatar_url      TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_superadmin   BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    mfa_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret      TEXT,
    locale          TEXT NOT NULL DEFAULT 'ru',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON COLUMN users.is_superadmin IS 'Platform-level admin — bypasses tenant RLS';

CREATE UNIQUE INDEX ix_users_email_tenant ON users (tenant_id, LOWER(email)) WHERE is_active = TRUE;

CREATE TABLE roles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    permissions     TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_roles_name_tenant ON roles (tenant_id, name);

-- Membership: user ↔ organisation with role
CREATE TABLE memberships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organisation_id UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    role_id         UUID REFERENCES roles(id) ON DELETE SET NULL,
    role            TEXT NOT NULL DEFAULT 'member',
    -- role: 'owner', 'admin', 'member', 'viewer'
    invited_at      TIMESTAMPTZ,
    accepted_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_memberships_user_org ON memberships (user_id, organisation_id);

-- ============================================================================
-- AUTH: SESSIONS, REFRESH TOKENS, API KEYS, PASSKEYS
-- ============================================================================

CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL,
    -- SHA-256 of access_token — for revocation lookups
    ip_address      TEXT,
    user_agent      TEXT,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_sessions_user ON sessions (tenant_id, user_id);
CREATE INDEX ix_sessions_expires ON sessions (expires_at) WHERE expires_at > NOW();

CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL,
    -- SHA-256 of refresh_token
    family_id       UUID NOT NULL DEFAULT gen_random_uuid(),
    -- Rotation family: revoke all when one is compromised
    is_revoked      BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_reason  TEXT,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_refresh_token_hash ON refresh_tokens (token_hash);
CREATE INDEX ix_refresh_family ON refresh_tokens (family_id);

CREATE TABLE magic_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email           TEXT NOT NULL,
    token_hash      TEXT NOT NULL,
    -- SHA-256 of magic link token
    is_used         BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_magic_links_email ON magic_links (tenant_id, email, created_at);

CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    key_hash        TEXT NOT NULL,
    -- SHA-256 of api_key prefix + full key
    key_prefix      TEXT NOT NULL,
    -- First 8 chars for UI display: "ak_a1b2c3d4"
    scopes          TEXT[] NOT NULL DEFAULT '{*}',
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    is_revoked      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_api_keys_hash ON api_keys (key_hash);
CREATE INDEX ix_api_keys_tenant ON api_keys (tenant_id, is_revoked);

CREATE TABLE passkeys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_id   TEXT NOT NULL,
    public_key      BYTEA NOT NULL,
    sign_count      BIGINT NOT NULL DEFAULT 0,
    device_name     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_passkeys_credential ON passkeys (credential_id);

-- ============================================================================
-- CHANNELS
-- ============================================================================

CREATE TABLE channels (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel_type    channel_type_enum NOT NULL,
    display_name    TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    priority        INTEGER NOT NULL DEFAULT 0,
    config          JSONB NOT NULL DEFAULT '{}',
    -- Channel-specific config: bot_token, smtp_host, widget_theme, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_channels_tenant_type ON channels (tenant_id, channel_type);

CREATE TABLE channel_credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel_id      UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    credential_type credential_type_enum NOT NULL,
    encrypted_value BYTEA NOT NULL,
    -- AES-256-GCM encrypted credential
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_creds_channel ON channel_credentials (channel_id);

CREATE TABLE channel_usage (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel_id      UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    messages_in     INTEGER NOT NULL DEFAULT 0,
    messages_out    INTEGER NOT NULL DEFAULT 0,
    errors          INTEGER NOT NULL DEFAULT 0,
    latency_avg_ms  DOUBLE PRECISION,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_channel_usage_date ON channel_usage (channel_id, date);

-- ============================================================================
-- CONVERSATIONS & MESSAGES
-- ============================================================================

CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    -- NULL for anonymous (web widget)
    channel_id      UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    external_user_id TEXT,
    -- Telegram user_id, email address, widget session_id
    status          conversation_status NOT NULL DEFAULT 'active',
    subject         TEXT,
    -- Auto-extracted topic
    state           JSONB NOT NULL DEFAULT '{}',
    -- Plugin state machine: {"step":"awaiting_wagon_number", ...}
    metadata        JSONB NOT NULL DEFAULT '{}',
    last_message_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_conv_tenant_status ON conversations (tenant_id, status);
CREATE INDEX ix_conv_channel ON conversations (channel_id);
CREATE INDEX ix_conv_external_user ON conversations (tenant_id, external_user_id);
CREATE INDEX ix_conv_last_msg ON conversations (tenant_id, last_message_at DESC);

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            message_role NOT NULL,
    content         TEXT NOT NULL,
    content_type    TEXT NOT NULL DEFAULT 'text',
    -- 'text', 'html', 'markdown'
    intent          TEXT,
    entities        JSONB,
    -- {"wagon_number": "1234", "cargo": "уголь"}
    tokens_used     INTEGER,
    cost_usd        DOUBLE PRECISION,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_messages_conv ON messages (conversation_id, created_at);
CREATE INDEX ix_messages_tenant ON messages (tenant_id, created_at);

CREATE TABLE message_attachments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    message_id      UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    file_type       TEXT NOT NULL,
    -- 'image', 'document', 'audio', 'video'
    file_url        TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    mime_type       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_attachments_msg ON message_attachments (message_id);

-- ============================================================================
-- INTENTS & ENTITIES (AI Core)
-- ============================================================================

CREATE TABLE intents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    -- NULL for builtin/system intents
    name            TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    description     TEXT,
    category        TEXT NOT NULL DEFAULT 'other',
    -- 'greeting', 'question', 'action', 'complaint', 'other'
    is_builtin      BOOLEAN NOT NULL DEFAULT FALSE,
    plugin_ids      TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_intents_name_tenant ON intents (tenant_id, name);

CREATE TABLE intent_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    intent_id       UUID NOT NULL REFERENCES intents(id) ON DELETE CASCADE,
    example_text    TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'ru',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_intent_templates_intent ON intent_templates (intent_id);

CREATE TABLE entity_types (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    value_type      entity_value_type NOT NULL DEFAULT 'string',
    pattern         TEXT,
    examples        TEXT[] NOT NULL DEFAULT '{}',
    lookup_table    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_entity_types_name ON entity_types (tenant_id, name);

-- ============================================================================
-- AI: MODELS, DRIVERS, EMBEDDINGS, KNOWLEDGE BASES
-- ============================================================================

CREATE TABLE ai_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    -- NULL for platform-wide models
    model_id        TEXT NOT NULL,
    -- 'llamacpp/Qwen3.6-35B', 'openai/gpt-4o'
    provider        TEXT NOT NULL,
    -- 'llamacpp', 'ollama', 'openai', 'deepseek'
    display_name    TEXT NOT NULL,
    capability      TEXT NOT NULL DEFAULT 'chat',
    -- 'chat', 'embedding', 'vision'
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    default_priority INTEGER NOT NULL DEFAULT 0,
    config          JSONB NOT NULL DEFAULT '{}',
    -- endpoint, api_key_ref, max_tokens, temperature defaults
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_ai_models_id ON ai_models (tenant_id, model_id);

CREATE TABLE driver_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_type     TEXT NOT NULL,
    -- 'llamacpp', 'ollama', 'openai', 'vllm'
    endpoint        TEXT NOT NULL,
    api_key_encrypted BYTEA,
    is_healthy      BOOLEAN NOT NULL DEFAULT TRUE,
    last_checked_at  TIMESTAMPTZ,
    error_message   TEXT,
    config          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE driver_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_config_id UUID NOT NULL REFERENCES driver_configs(id) ON DELETE CASCADE,
    model_id        TEXT NOT NULL,
    requests_total  INTEGER NOT NULL DEFAULT 0,
    requests_failed INTEGER NOT NULL DEFAULT 0,
    latency_avg_ms  DOUBLE PRECISION,
    tokens_in       BIGINT NOT NULL DEFAULT 0,
    tokens_out      BIGINT NOT NULL DEFAULT 0,
    cost_usd        DOUBLE PRECISION NOT NULL DEFAULT 0,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_driver_metrics_driver ON driver_metrics (driver_config_id, recorded_at);

CREATE TABLE knowledge_bases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    embedding_model TEXT NOT NULL,
    -- 'bge-small', 'text-embedding-3-small'
    document_count  INTEGER NOT NULL DEFAULT 0,
    vector_dim      INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE knowledge_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    source_url      TEXT,
    file_type       TEXT,
    -- 'pdf', 'txt', 'html', 'markdown'
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    tokens_total    INTEGER,
    indexed_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_kb_docs_base ON knowledge_documents (knowledge_base_id);

-- ============================================================================
-- SERVICES: PLUGINS & EXECUTIONS
-- ============================================================================

CREATE TABLE service_definitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_id       TEXT NOT NULL,
    -- 'gu12', 'faq', 'scheduler', 'etran'
    display_name    TEXT NOT NULL,
    description     TEXT,
    version         TEXT NOT NULL DEFAULT '1.0.0',
    is_builtin      BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    capabilities    TEXT[] NOT NULL DEFAULT '{}',
    -- 'document_generation', 'calculation', 'tracking'
    config_schema   JSONB NOT NULL DEFAULT '{}',
    -- JSON Schema for plugin config validation
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_service_def_plugin_version ON service_definitions (plugin_id, version);

CREATE TABLE service_instances (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_definition_id UUID NOT NULL REFERENCES service_definitions(id) ON DELETE CASCADE,
    config          JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    installed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_service_inst_tenant ON service_instances (tenant_id);

CREATE TABLE service_bindings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_instance_id UUID NOT NULL REFERENCES service_instances(id) ON DELETE CASCADE,
    channel_id      UUID REFERENCES channels(id) ON DELETE SET NULL,
    -- NULL = all channels
    priority        INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_service_bindings_inst ON service_bindings (service_instance_id);

CREATE TABLE service_executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_instance_id UUID REFERENCES service_instances(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    intent          TEXT,
    entities        JSONB,
    result          execution_result NOT NULL DEFAULT 'success',
    response_text   TEXT,
    duration_ms     INTEGER,
    tokens_used     INTEGER,
    cost_usd        DOUBLE PRECISION,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_service_exec_tenant_ts ON service_executions (tenant_id, created_at);
CREATE INDEX ix_service_exec_conv ON service_executions (conversation_id);

-- ============================================================================
-- BILLING & SUBSCRIPTIONS
-- ============================================================================

CREATE TABLE subscription_plans (
    id              TEXT PRIMARY KEY,
    -- 'free', 'starter', 'professional', 'enterprise'
    name            TEXT NOT NULL,
    description     TEXT,
    price_monthly_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    price_yearly_usd  DOUBLE PRECISION,
    features        TEXT[] NOT NULL DEFAULT '{}',
    limits          JSONB NOT NULL DEFAULT '{}',
    is_public       BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan_id         TEXT NOT NULL REFERENCES subscription_plans(id),
    status          subscription_status NOT NULL DEFAULT 'active',
    trial_started_at TIMESTAMPTZ,
    trial_ends_at   TIMESTAMPTZ,
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_period_end   TIMESTAMPTZ NOT NULL,
    auto_renew      BOOLEAN NOT NULL DEFAULT TRUE,
    payment_method_id UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_subscriptions_tenant ON subscriptions (tenant_id);
CREATE INDEX ix_subscriptions_status ON subscriptions (status);

CREATE TABLE invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    amount_usd      DOUBLE PRECISION NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'USD',
    status          invoice_status NOT NULL DEFAULT 'draft',
    due_date        DATE NOT NULL,
    paid_at         TIMESTAMPTZ,
    invoice_pdf_url TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_invoices_tenant ON invoices (tenant_id);
CREATE INDEX ix_invoices_sub ON invoices (subscription_id);

CREATE TABLE usage_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    metric          TEXT NOT NULL,
    -- 'api_calls', 'tokens_used', 'storage_bytes', 'active_users', 'conversations'
    value           DOUBLE PRECISION NOT NULL DEFAULT 0,
    period          usage_period NOT NULL DEFAULT 'daily',
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_usage_tenant_metric ON usage_records (tenant_id, metric, recorded_at);

CREATE TABLE payment_methods (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL,
    -- 'stripe', 'paddle', 'manual'
    provider_payment_method_id TEXT NOT NULL,
    last_four       TEXT,
    card_brand      TEXT,
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- TENANT CONFIGURATION
-- ============================================================================

CREATE TABLE tenant_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    key             TEXT NOT NULL,
    value           JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_tenant_configs_key ON tenant_configs (tenant_id, key);

CREATE TABLE tenant_features (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    feature_key     TEXT NOT NULL,
    is_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
    config          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_tenant_features_key ON tenant_features (tenant_id, feature_key);

CREATE TABLE tenant_limits (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    limit_key       TEXT NOT NULL,
    -- 'max_users', 'max_conversations_per_day', 'max_storage_bytes'
    limit_value     INTEGER NOT NULL,
    current_usage   INTEGER NOT NULL DEFAULT 0,
    period          usage_period NOT NULL DEFAULT 'monthly',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_tenant_limits_key ON tenant_limits (tenant_id, limit_key);

CREATE TABLE tenant_domains (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    domain          TEXT NOT NULL,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    ssl_certificate_id TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX ix_tenant_domains_value ON tenant_domains (domain);

-- ============================================================================
-- AUDIT & LOGGING
-- ============================================================================

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,
    -- 'tenant.create', 'channel.update', 'user.login', 'plugin.install'
    resource        TEXT NOT NULL,
    -- 'tenants', 'channels', 'users', 'plugins', 'subscriptions'
    resource_id     UUID,
    details         JSONB NOT NULL DEFAULT '{}',
    ip_address      TEXT,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_audit_tenant_ts ON audit_logs (tenant_id, created_at);
CREATE INDEX ix_audit_action ON audit_logs (tenant_id, action);
CREATE INDEX ix_audit_user ON audit_logs (user_id) WHERE user_id IS NOT NULL;

CREATE TABLE api_call_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    method          TEXT NOT NULL,
    path            TEXT NOT NULL,
    status_code     INTEGER NOT NULL,
    duration_ms     INTEGER NOT NULL,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    ip_address      TEXT,
    request_id      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_api_logs_tenant_ts ON api_call_logs (tenant_id, created_at);

-- ============================================================================
-- ROW-LEVEL SECURITY
-- ============================================================================

-- Helper: set tenant context for a transaction
CREATE OR REPLACE FUNCTION set_tenant_context(tid UUID) RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tid::TEXT, FALSE);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- RLS: All business tables use tenant_isolation policy
-- The policy checks: tenant_id = current_setting('app.current_tenant_id')::UUID
-- superadmin bypass via is_superadmin flag (checked in application layer)

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename NOT IN ('tenants', 'subscription_plans', 'driver_configs', 'driver_metrics')
          AND tablename LIKE '%' -- apply to all tables with tenant_id
    LOOP
        -- Check if column tenant_id exists
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = tbl
              AND column_name = 'tenant_id'
        ) THEN
            EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
            EXECUTE format(
                'CREATE POLICY tenant_isolation ON %I
                 USING (tenant_id = COALESCE(
                     NULLIF(current_setting(''app.current_tenant_id'', TRUE), '''')::UUID,
                     ''00000000-0000-0000-0000-000000000000''::UUID
                 ))
                 WITH CHECK (tenant_id = COALESCE(
                     NULLIF(current_setting(''app.current_tenant_id'', TRUE), '''')::UUID,
                     ''00000000-0000-0000-0000-000000000000''::UUID
                 ))',
                tbl
            );
        END IF;
    END LOOP;
END;
$$;

-- ============================================================================
-- TRIGGERS: updated_at auto-update
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT tablename FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name = 'updated_at'
        GROUP BY tablename
    LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_%I_updated_at
             BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()',
            tbl, tbl
        );
    END LOOP;
END;
$$;

-- ============================================================================
-- SEED DATA: Subscription Plans
-- ============================================================================

INSERT INTO subscription_plans (id, name, description, price_monthly_usd, price_yearly_usd, features, limits, sort_order) VALUES
('free', 'Free',
 'Базовый доступ для малого бизнеса. 1 канал, 50 диалогов/день.',
 0, 0,
 ARRAY['1 канал (Telegram или WebWidget)', '50 диалогов/день', '1 пользователь', 'FAQ-плагин', 'AI через облачного провайдера'],
 '{"max_users": 1, "max_channels": 1, "max_conversations_per_day": 50, "max_storage_bytes": 104857600, "rate_limit_rpm": 60}'::JSONB,
 1),
('starter', 'Starter',
 'Растущий бизнес. 3 канала, AI кастомизация, базовая аналитика.',
 29, 290,
 ARRAY['3 канала (Telegram, WebWidget, Email)', '500 диалогов/день', '5 пользователей', 'Все builtin плагины', 'Custom prompt + intents', 'Базовая аналитика'],
 '{"max_users": 5, "max_channels": 3, "max_conversations_per_day": 500, "max_storage_bytes": 1073741824, "rate_limit_rpm": 600}'::JSONB,
 2),
('professional', 'Professional',
 'Профессиональный набор. Неограниченные каналы, свои плагины, приоритетная поддержка.',
 99, 990,
 ARRAY['Неограниченные каналы', '10,000 диалогов/день', '20 пользователей', 'Custom Python плагины', 'PromptDrivenPlugin без ограничений', 'Расширенная аналитика', 'Priority support'],
 '{"max_users": 20, "max_channels": 10, "max_conversations_per_day": 10000, "max_storage_bytes": 10737418240, "rate_limit_rpm": 6000}'::JSONB,
 3),
('enterprise', 'Enterprise',
 'Enterprise: white-label, on-premise, SSO, dedicated support.',
 499, 4990,
 ARRAY['Всё из Professional', 'White-label полный', 'On-premise deploy', 'SSO (OIDC/SAML)', 'Dedicated support', 'SLA 99.9%', 'Custom integrations'],
 '{"max_users": 500, "max_channels": -1, "max_conversations_per_day": -1, "max_storage_bytes": -1, "rate_limit_rpm": -1}'::JSONB,
 4)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- INDEXES: Additional performance indexes
-- ============================================================================

-- Partial indexes for active records
CREATE INDEX ix_conversations_active ON conversations (tenant_id, last_message_at DESC)
    WHERE status = 'active';

CREATE INDEX ix_subscriptions_active ON subscriptions (tenant_id)
    WHERE status IN ('active', 'trial');

CREATE INDEX ix_api_keys_active ON api_keys (tenant_id)
    WHERE is_revoked = FALSE AND (expires_at IS NULL OR expires_at > NOW());

-- GIN indexes for JSONB columns (full-text search within JSON)
CREATE INDEX ix_tenants_settings_gin ON tenants USING GIN (settings);
CREATE INDEX ix_channels_config_gin ON channels USING GIN (config);
CREATE INDEX ix_conversations_metadata_gin ON conversations USING GIN (metadata);
CREATE INDEX ix_messages_entities_gin ON messages USING GIN (entities);
CREATE INDEX ix_service_instances_config_gin ON service_instances USING GIN (config);
CREATE INDEX ix_audit_logs_details_gin ON audit_logs USING GIN (details);
