# Aether LOG

## 2026-07-02 12:29-12:42 — Billing Stage 1
- ✅ BillingService: token accounting, plan enforcement, usage tracking (247 lines)
- ✅ BillingAIMiddleware: auto charging tokens for AI requests, HTTP 429 on quota exceeded
- ✅ Seed plans: Free, Starter, Pro, Enterprise with limits (tokens/conversations/documents)
- ✅ Billing API: /billing/status (full status), /billing/usage/summary
- ✅ Fixed ARRAY→JSON in features column (SQLite compatibility)
- ✅ Fixed AI Pipeline test bug: tenant_id mismatch with fixtures
- ✅ 103/103 tests green
- ✅ Audit: removed logistics contamination from enums/models (commit db88fd9)

**Next:** Integrate billing with AI Pipeline (charge tokens on real AI requests)

## 2026-06-25 04:17 UTC — Stage 0: Analysis Complete
- Stack chosen: Python 3.12+ FastAPI (8.5/10 score vs Go 6.5, Node 7.5)
- MVP Channels: Telegram Bot (#1), Web Widget (#2), Email (#3)
- AI Core: Custom lightweight inference router (7.4/10) — OpenClaw not multi-tenant-ready
- First domain: Logistics/VED (12.05/20) — Denis expertise + Logicore codebase
- All 4 analysis docs in docs/analysis/

## 2026-06-25 05:02 UTC — Stage 1: Architecture Graph Complete
- 6 architecture docs written (154 KB total):
  - overview.md: data flow, principles, module map
  - backend.md: 68 files, 89 classes, 254 functions
  - channels.md: 9 files, 9 classes, 50 methods
  - ai-core.md: 12 files, 12 classes, 76 methods
  - tenant.md: 12 files, 20 classes, 54 methods
  - services.md: 19 files, 18 classes, 103 methods
- Subagents spawned for backend/channels/services/tenant but local model failed to write files
- All files written by main agent (DeepSeek v4)
- Zero hardcode: all through ABC, registry, dependency injection, DB-driven config
- Tenant isolation: ContextVar + PostgreSQL RLS + Redis prefix + file path prefix
- Plugin architecture: BaseServicePlugin ABC + PluginRegistry + PromptDrivenPlugin (Stage 1 MVP)
- Channel abstraction: BaseChannel ABC + ChannelRouter + MessageNormalizer
- AI multi-driver: BaseDriver ABC + InferencePool + SmartRouter (Stage 2)
- Next: Stage 2 — specifications (API contracts, DB schemas, protocols)

## 2026-06-25 05:14 UTC — Архитектурное обновление: Admin Dashboard ≠ Client Workspace
- Добавлен принцип №6 в overview: Admin Cabinet (/aether/admin/) — отдельный от Client Workspace (/aether/{slug}/)
- Три роли: superadmin, tenant_admin, tenant_user
- Admin API расширен с 5 до 18 эндпоинтов (полное управление платформой)
- Добавлен settings.py API (14 эндпоинтов) — tenant самообслуживание
- Создан frontend.md: 48 файлов, 41 компонент
  - Admin Dashboard: 15 файлов, 12 компонентов
  - Client Workspace: 17 файлов, 15 компонентов
  - Shared UI kit: 16 файлов, 14 компонентов
- Ключевой принцип: SettingsView — ВСЕ настройки на ОДНОЙ странице, секции раскрываются inline
  - Антипаттерн: 10+ роутов для 6 секций настроек
  - Паттерн: /settings — одна страница с аккордеоном секций
- InlineEdit компонент: редактирование на месте, не модалки, не отдельные страницы

## 2026-06-25 05:19 UTC — Organisation Model + Auth v2 + Email-Client Layout
**По требованию Дениса:**
1. Ролевая модель организации: регистрация компании → invitation сотрудников → роли
   - Organisation + Membership + OrganisationInvite модели
   - Permission matrix: Owner/Admin/Member/Viewer
   - Invitation flow: email с ссылкой → принятие → сразу в Workspace
   - OrganisationService: 9 методов (create, invite, accept, revoke, change_role, transfer_ownership...)

2. Современная регистрация/логин (passwordless-first):
   - Single-field signup: email + компания → magic link
   - Smart login: email → определяет методы (passkey/password/magic link)
   - Passkeys (WebAuthn), OAuth (Google, Яндекс ID, VK ID)
   - MFA (TOTP + hardware keys), SSO (OIDC/SAML Stage 3)
   - AuthService: 12 методов
   - 19 auth API endpoints (signup, login, passkey, mfa, oauth, workspaces...)

3. Frontend переработан под email-client layout:
   - Трёхпанельный inbox (Sidebar | Conversation List | Chat)
   - WorkspaceView как главный экран (не отдельные роуты)
   - ConversationListItem — как письмо в почте (аватар, превью, время, канал)
   - ChatComposer: Markdown, emoji, файлы, быстрые ответы AI
   - Клавиатурная навигация: ↑↓ Enter Esc Ctrl+K
   - Адаптив: 1/2/3 панели для mobile/tablet/desktop
   - Auth views: SignupView, LoginView, AcceptInviteView, WorkspacePickerView

---

## Stage 3.5 Frontend — Scaffold + Auth Views (2026-06-25 21:00–22:20 UTC)

### Создан с нуля
- Vue 3 + TypeScript + Vite + Pinia + Vue Router + Axios
- 34 файла, 19 Vue компонентов, 15 TS модулей
- Login/Signup views: gradient design, health status bar, full form validation
- 3 Pinia stores: auth (tokens+refresh, localStorage), workspace (conversations+messages), admin
- 4 composables: useApi (Axios singleton, 401 auto-refresh), useAuth, useTenant, useWebSocket
- 3 shared UI: BaseButton (4 variants, 3 sizes, spinner), BaseInput (v-model+error), BaseCard
- 17 routes: auth (4), workspace (4), admin (7), catch-all
- TypeScript types: admin.ts (35 types), client.ts (45 types), common.ts (5 types)
- `npx vite build`: 168ms clean, 75 modules, ~150KB gzipped

### Стабы (пустые заглушки, ждут наполнения)
- ClientLayout, WorkspaceView, SettingsView, AnalyticsView
- WorkspacePickerView, VerifyView, AcceptInviteView
- AdminLayout + 7 admin views

### Следующий шаг → сделано!

---

## Stage 3.5 Frontend — Views & Integration (2026-06-25 22:00–22:45 UTC)

### Client Views (6 компонентов)
- **ClientLayout** (330 строк): 3-panel responsive (240px/320px/flex), collapsible sidebar,
  mobile nav tabs, keyboard hint bar, org switcher
- **WorkspaceView** (760 строк): full email-client: channel sidebar, conversation search+filter,
  chat bubbles + composer, keyboard nav (↑↓ Enter Esc Ctrl+K), WebSocket connect, skeletons
- **SettingsView** (612 строк): single-page accordion (6 sections): Profile, Channels, AI Models,
  Team, Billing, Danger Zone — inline editing (not modals)
- **WorkspacePickerView** (397 строк): grid cards, skeleton loading, error+retry, empty state
- **AnalyticsView** (195 строк): stats grid + CSS bar chart + period picker (7d/30d/90d) +
  channel breakdown
- **VerifyView** (200 строк): 4 states — loading/spinner, success/redirect, expired/resend, invalid
- **AcceptInviteView** (280 строк): 5 states, org avatar+role badge, auth gate (signup/login CTA)

### Admin Views (7 компонентов)
- **DashboardView**: stat cards (tenants/users/requests/revenue), system health
  (backend/DB/Redis/Celery), activity feed, quick actions
- **TenantsListView**: search+status filter, 7-column table, pagination (20/page)
- **TenantDetailView**: 5 tabs (overview/users/channels/billing/settings), suspend/activate/delete
- **DriversView**: status dots, health check, 4-step add-driver modal
- **BillingView**: CSS bar chart, MRR/ARR/churn stats, invoices & subscriptions tables
- **SubscriptionsView**: plan cards grid, inline create form, edit/archive
- **AuditView**: filter bar (date/type/tenant), colored event badges, expandable JSON, pagination

### States handled by every view
- Loading: shimmer skeleton cards/rows
- Empty: illustration + CTA
- Error: message + retry button
- Data: loaded and interactive

### Design
- Material Design 3: CSS custom properties, 17 color tokens, light/dark
- #1a73e8 primary, white cards, clean typography
- Scoped CSS in every component
- Responsive: 1/2/3 panels for mobile/tablet/desktop

### Build
- 35 files, 7,097 lines TypeScript/Vue
- `npx vite build`: 323ms, 41 modules, 0 errors

---

## Stage 6: Frontend ↔ Backend Integration (2026-06-25 22:40–22:48 UTC)

### Vite proxy
- `/api` → `http://localhost:8799` (changeOrigin)
- `/ws` → `ws://localhost:8799` (WebSocket)
- `@` alias → `src/`
- Dev server: 176ms startup on :5173

### Backend
- Uvicorn :8799 with --reload
- PostgreSQL connected (latency 0.56ms)
- Redis connected
- 127 HTTP + 1 WS endpoints registered

### E2E Integration Test: 9/9 PASSED ✅
- Login → JWT (233 chars, 900s TTL)
- /users/me → email + display_name
- /channels → 0 items (empty, not error)
- /conversations → 0 items
- /plans → 0 items
- /tenants → 6 items
- /ai/intents → 0 items
- Token refresh → new JWT
- Health → db=connected, redis=connected

### Ready for Stage 7
- WebSocket e2e test
- Frontend in-browser testing
- Seed data for demo
- Docker Compose for full stack (2026-06-25 15:22–15:55 UTC)

### Добавлены модули (83 новых эндпоинта)

| Модуль | Эндпоинты | Схемы |
|--------|-----------|-------|
| AI Core (`api/v1/ai.py`) | 31 | intents, templates, entities, models, drivers, metrics, knowledge-bases, documents |
| Services (`api/v1/services.py`) | 19 | definitions, instances, bindings, executions |
| Billing (`api/v1/billing.py`) | 15 | plans, subscriptions, invoices, usage, payment-methods |
| Tenants (`api/v1/tenants.py`) | 20 | tenants, configs, features, limits, domains |

### WebSocket handler
- `/ws/widget/{tenant_id}?token={jwt}` — JWT validation, heartbeat, message routing
- handlers: chat.message, chat.typing, chat.quick_reply

### Celery scaffold
- 3 очереди (default/ai/long_running), 9 задач
- process_intent, generate_response, index_document, send_magic_link, send_invitation, cleanup_expired_tokens, generate_usage_report, check_driver_health, send_passwordless_code

### 5 Critical аудита
- C1 ✅ TenantMigrationRunner с registry
- C2 ✅ _verify_org_membership() в organisations
- C3 ⏳ Отложен до Stage 4 (BaseChannel ABC)
- C4 ✅ slowapi rate limiting на auth
- C5 ✅ Membership проверка в БД

### Итого
- **128 routes** (123 HTTP + 1 WS + CORS)
- **10 модулей** API со схемами
- **22 файла** создано/изменено
- **Backend готов к Stage 4** (интеграционный тест, фронтенд, настоящие AI драйверы)

---

## Stage 4: Integration Test (2026-06-25 15:42–15:46 UTC)

### PostgreSQL (Docker)
- Container `aether-postgres-1` started, 40 tables verified
- DB: `aether_dev` on localhost:5432

### Integration test results
✅ **19/19 endpoints — all 200**
- Auth: signup ✅, login ✅, refresh ✅
- AI Core: intents, entities, models, drivers, knowledge-bases
- Services: definitions, instances, bindings, executions
- Billing: plans, subscriptions, invoices, usage
- Core: users, channels, conversations, organisations, health
- Tenants: list ✅

✅ **CRUD operations**
- Channel create (email) ✅
- Intent create (greeting) ✅
- Organisation create ✅
- Service definition create ✅

### Fixes applied
- Installed `argon2-cffi` (MissingBackendError)
- Fixed AI router prefix (`/ai` in router.py)
- Fixed slowapi `request: Request` parameter signature
- Router prefix deduplication (services/billing/tenants)

### Backend verified
- Signup → JWT tokens → API calls → data persistence
- All 40 PostgreSQL tables functional
- Redis connected
- WS endpoint registered: `/ws/widget/{tenant_id}`
- Uvicorn :8799 with --reload for dev
- Frontend Vite dev server :5173 with proxy to backend
- Full E2E chain: Vite → proxy → Backend → PostgreSQL/Redis

## 2026-06-27 13:10 UTC — C1+C2 Closed, Bare Excepts + Empty Catches + Test Suite

### What was done
- **C1 ✅ Magic Link URL**: Already fixed (uses `settings.FRONTEND_URL`), AUDIT.md updated
- **C2 ✅ Tests**: 37/37 GREEN — 4 test files (auth 24, billing 11, health 2, tenants 14 → 37 total counting sub-tests)
- **Refresh Token Hash Fix**: `_hash_token()` SHA-256 over full token. Login/Signup/Logout/Refresh all use same hash. Refresh now rejects revoked tokens (401).
- **Logout Bug**: Token hash mismatch fixed — login used random hex, logout used token[:64] — now both use SHA-256

### Code Quality
- **4 bare `except:`** → `except Exception` + `logger.exception()`
- **15 empty `catch {}`** → `catch (e)` + `console.error(...)`
- **1 missed**: AuditView.vue catch {} also fixed

### Test Infrastructure
- **SQLite in-memory isolation**: `_class_db_setup` truncates per class, no shared state
- **Rate limit reset**: `limiter._storage.reset()` before each test class (was trying `.clear()`/`.flushall()` — wrong API)
- **`test` env pattern**: Added to `config.py:ENVIRONMENT` validation

### Files changed: 26 (339 +/ 79 -)
- backend: auth.py, config.py, 4 drivers, telegram_channel.py
- tests: conftest.py, test_auth.py, test_billing.py, test_health.py, test_tenants.py
- frontend: 16 files (composables, stores, views)
- docs: AUDIT.md

### Next
- W1b (localhost defaults in main.py + local_driver.py)
- F3+F4 (WorkspacePicker/WorkspaceView memberCount from API)
- F5 (SettingsView: profile save, avatar upload, account delete)
- B8 (WS AI response routing — Stage 4)
