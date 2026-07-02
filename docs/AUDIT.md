# Aether Platform — Full Audit Report
_Generated: 2026-06-25 23:45 UTC | Auditor: Lora_

## Executive Summary

**Project State:** 20 commits, Stages 0-10, 70 backend files (8236 LOC), 35 frontend files (978 LOC), 130+ API endpoints, E2E verified.

**Overall Verdict:** 🟡 **PRODUCTION-NOT-READY** — Functional for dev/demo, but 3 critical security issues + missing tests block production deployment.

---

## 📋 Hardcode Inventory (Full — 2026-06-26)

### Backend Hardcodes
| # | File:Line | Value | Severity | Fix |
|---|-----------|-------|----------|-----|
| B1 | `auth.py:185` | `http://localhost:3000/auth/verify` | 🔴 CRITICAL | `settings.MAGIC_LINK_BASE_URL` |
| B2 | `main.py:64` | `http://localhost:8085` | 🟡 WARNING | Env var `LOCAL_AI_BASE_URL` |
| B3 | `local_driver.py:6` | `http://localhost:8080` | 🟡 WARNING | Remove default, require in constructor |
| B4 | `config.py:21` | `postgresql+asyncpg://postgres:postgres@localhost:5432/aether` | 🟢 HINT | Dev-only fallback, env overrides |
| B5 | `config.py:27` | `redis://localhost:6379/0` | 🟢 HINT | Dev-only fallback, env overrides |
| B6 | `config.py:51` | `http://localhost:3000,http://localhost:5173` | 🟢 HINT | Dev-only fallback, env overrides |
| B7 | `celery_app.py:21-22` | `redis://localhost:6379/0` (2x) | 🟢 HINT | 3rd-level fallback after settings |
| B8 | `ws.py:251` | `# TODO Stage 4: route to AI` | 🟡 WARNING | Stub — returns echo only |
| B9 | `ws.py:137,139,146` | `except: pass` (3x) | 🟡 WARNING | Silent WebSocket error swallowing |
| B10 | `drivers/*.py:86-89` | `except: pass` (3x) | 🟢 HINT | AI driver SSE parsing, low-risk |
| B11 | `telegram_channel.py:32` | `except:` (bare) | 🟡 WARNING | Catches KeyboardInterrupt + SystemExit |
| B12 | `main.py:6` | `import time` (unused) | 🟢 HINT | Dead import, remove |

### Frontend Hardcodes
| # | File:Line | Value | Severity | Fix |
|---|-----------|-------|----------|-----|
| F1 | `useApi.ts:4` | `http://localhost:8799/api/v1` | 🟡 WARNING | Dev fallback, `VITE_API_URL` overrides |
| F2 | `useWebSocket.ts:17` | `ws://localhost:8799` | 🟡 WARNING | Dev fallback, `VITE_WS_URL` overrides |
| F3 | `WorkspacePickerView.vue:118` | `memberCount: 1` | 🟡 WARNING | Hardcoded — shows 1 member for all workspaces |
| F4 | `WorkspaceView.vue:280` | Mock member count | 🟡 WARNING | Renders fake data, not from API |
| F5 | `SettingsView.vue:311,328,361` | 3 empty TODO handlers | 🟡 WARNING | Save/upload/delete do nothing |
| F6 | `auth.ts:7-8` | `localStorage.getItem` for tokens | 🟡 WARNING | XSS-vulnerable token storage |
| F7 | `DriversView.vue:114` | `placeholder="http://localhost:11434"` | 🟢 HINT | UX hint, not a runtime value |
| F8 | `15 files, 16 instances` | `catch (e: any)` + `plan: any` | 🟢 HINT | TypeScript strictness |
| F9 | `15 files, 15 instances` | `catch {}` (empty handler) | 🟡 WARNING | Silent error swallowing in UI |

### Verdict: NOT a stub-project
- ✅ Email channel: FULL implementation (IMAP IDLE + SMTP, aioimaplib + aiosmtplib)
- ✅ AI inference: Working (llama.cpp E2E verified)
- ✅ Auth: Full magic link + JWT + signup flow
- 🟡 WS AI routing: Echo-only stub (1 TODO)
- 🟡 Settings page: 3/3 handlers are empty stubs
- 🟡 Workspace picker: memberCount hardcoded

---

## 🔴 CRITICAL (3) — Must Fix Before Production

### C1. ✅ Hardcoded Magic Link URL — FIXED (2026-06-25)
- **File:** `backend/app/api/v1/auth.py:186`
- **Now:** `magic_url = f"{settings.FRONTEND_URL}/auth/verify?token={token}"`
- **Default:** `FRONTEND_URL` defaults to `http://localhost:3000` in config.py (dev fallback, overridable via `AETHER_FRONTEND_URL` env var)
- **Status:** FIXED — not a hardcode, uses Settings properly

### C2. 🟡 Tests — Partial (22 pass, 15 errors)
- **Status:** 4 test files (auth, billing, health, tenants), 37 tests total
- **22 pass**, 15 errors — mostly DB race conditions (tests share one DB), not logic errors
- **Fix:** Add test DB isolation (create/drop per test class) + fix logout assertion
- **Blocking:** Need green suite before production

### C3. ✅ Config Default "change-me-in-production" — FIXED (2026-06-25)
- **File:** `backend/app/config.py:33`
- **Issue:** `JWT_SECRET_KEY` default is `"change-me-in-production"` — if .env is missing, JWT is trivially forgeable
- **Fix:** Removed default — now a required field with no default (env var must be set)
- **Status:** COMMITTED c5a0cbc3

---

## 🟡 WARNINGS (8) — Should Fix

### W1. Bare `except:` blocks (4 instances)
- `backend/app/channels/telegram_channel.py:32` — `except:` (bare, catches everything)
- `backend/app/ai/drivers/openai_driver.py:89` — `except: pass`
- `backend/app/ai/drivers/anthropic_driver.py:81` — `except: pass`
- `backend/app/ai/drivers/local_driver.py:86` — `except: pass`
- **Fix:** Catch specific exceptions, log the error

### W1b. Hardcoded localhost defaults in Field() — 6 instances (NEW)
- **config.py:21** — `DATABASE_URL` default `postgresql+asyncpg://postgres:postgres@localhost:5432/aether`
- **config.py:27** — `REDIS_URL` default `redis://localhost:6379/0`
- **config.py:51** — `CORS_ORIGINS` default `http://localhost:3000,http://localhost:5173`
- **main.py:64** — `base_url="http://localhost:8085"` hardcoded in LocalDriver registration
- **local_driver.py:6** — constructor default `base_url="http://localhost:8080"`
- **celery_app.py:21-22** — fallback `redis://localhost:6379/0` (3rd-level fallback after settings)
- **Verdict:** Config defaults are acceptable for dev convenience (`.env.example` covers them), but `main.py:64` and `local_driver.py:6` are code-level hardcodes — these should be env-driven

### W1c. Empty catch blocks in frontend — 15 instances (NEW)
- `useTenant.ts:17,27` — `catch {}`
- `useWebSocket.ts:33` — `catch {}`
- `useAuth.ts:52,61,70` — `catch {}`
- `VerifyView.vue:90` — `catch {} finally {}`
- `WorkspacePickerView.vue:120` — `catch {}`
- `LoginView.vue:83` — `catch {}`
- `stores/workspace.ts:19,38,56` — `catch {}`
- `stores/auth.ts:41` — `catch {}`
- `stores/admin.ts:18,26` — `catch {}`
- **Fix:** At minimum `console.error`; ideally toast notification to user

### W2. Silent exception swallowing in WebSocket handler
- **File:** `backend/app/api/v1/ws.py` — multiple `except Exception: pass` blocks
- Lines: 136-139, 145-146
- **Fix:** Log errors at minimum; WebSocket errors disappearing silently makes debugging impossible

### W3. Hardcoded localhost fallbacks in config.py
- `DATABASE_URL` default: `postgresql+asyncpg://postgres:postgres@localhost:5432/aether` (wrong DB name — should be `aether_dev`)
- `REDIS_URL` default: `redis://localhost:6379/0`
- `CORS_ORIGINS` default: `http://localhost:3000,http://localhost:5173`
- `LOCAL_DRIVER_BASE_URL` hardcoded in `main.py:64`: `http://localhost:8085`
- **Fix:** Move ALL defaults to env-only, no hardcoded fallbacks in production config

### W4. Token storage in localStorage (frontend)
- **File:** `frontend/src/stores/auth.ts`
- Tokens stored in `localStorage` — vulnerable to XSS
- **Fix:** Use httpOnly cookies for refresh token; access token can stay in memory (Pinia store)
- **Acceptable for MVP** but needs a plan

### W5. Frontend has TODO stubs — 8 instances (UPDATED)
- **WorkspacePickerView.vue:103** — `TODO: derive from actual membership`; line 118: `memberCount: 1`
- **WorkspaceView.vue:280** — `Mock member count (TODO: from API)`
- **SettingsView.vue:311** — `TODO: API call to save` (profile save)
- **SettingsView.vue:328** — `TODO: API call` (avatar upload)
- **SettingsView.vue:361** — `TODO: API call` (delete account)
- **backend/app/api/v1/ws.py:251** — `TODO Stage 4: route to AI core for response generation`
- **Verdict:** Settings page is a ghost — 3 empty handlers with only TODOs. WorkspacePicker shows hardcoded memberCount=1. These will break in multi-user prod.

### W6. WorkspaceView.vue is 1002 lines
- **File:** `frontend/src/client/views/WorkspaceView.vue`
- Single component >1000 lines — violates separation of concerns
- **Fix:** Extract ConversationList, ChatWindow, ChatComposer into separate components

### W7. ✅ .env committed to git — FIXED (2026-06-25)
- **File:** `backend/.env` — force-added with `git add -f`
- Contains real JWT secret, DB credentials, encryption keys
- **Fix:** Removed from git tracking, added to .gitignore
- **Status:** COMMITTED c5a0cbc3

### W8. `any` usage in TypeScript — 16 instances (UPDATED)
- `catch (e: any)` in: `useAuth.ts` (2x), `AnalyticsView.vue`, `VerifyView.vue`, `AcceptInviteView.vue` (2x), `DriversView.vue` (2x), `DashboardView.vue`, `SubscriptionsView.vue` (2x), `TenantDetailView.vue`, `TenantsListView.vue`
- `plan: any` in `SubscriptionsView.vue` — `planFeatures(plan: any)`, `editPlan(plan: any)`, `archivePlan(plan: any)`
- **Fix:** Use `unknown` in catch blocks; define proper `Plan` interface for subscriptions

---

## 🟢 SUGGESTIONS (5) — Nice to Have

### S1. No input validation on frontend
- Login/Signup forms don't validate email format, password strength before submission
- **Suggestion:** Add vee-validate or zod for client-side validation

### S2. No loading/error states in admin views
- 7 admin views render but don't handle API loading/empty/error states
- **Suggestion:** Add BaseLoading, BaseEmpty, BaseError shared components

### S3. Vite build produces large chunks
- `runtime-core.esm-bundler-C-pOzyiC.js` — 59.83 kB
- `index-DVfRNwAA.js` — 95.39 kB
- **Suggestion:** Add lazy loading for admin routes (dynamic imports)

### S4. No API versioning beyond `/v1`
- All endpoints under `/api/v1/` — good, but no strategy for v2
- **Suggestion:** Document versioning policy in architecture docs

### S5. No health check for llama.cpp in backend startup
- `main.py` registers driver but doesn't verify llama.cpp is actually responding
- **Suggestion:** Add startup health check with retry

---

## ✅ WHAT'S GOOD

| Area | Status | Details |
|------|--------|--------|
| **Architecture** | ✅ | ABC + Registry + DI pattern consistently applied |
| **Tenant isolation** | ✅ | Every API query filters by `tenant_id` |
| **Rate limiting** | ✅ | slowapi on auth endpoints, Redis-backed |
| **Password hashing** | ✅ | argon2 via passlib |
| **JWT** | ✅ | HS256, separate access/refresh tokens, refresh endpoint |
| **SQL injection** | ✅ | All queries use SQLAlchemy ORM, no raw SQL |
| **XSS (frontend)** | ✅ | No `v-html` usage found |
| **CORS** | ✅ | Configurable comma-separated origins |
| **Docker** | ✅ | docker-compose.yml + Dockerfile + Makefile |
| **CI/CD** | ✅ | GitHub Actions workflow + deploy script + nginx config |
| **Documentation** | ✅ | 10 architecture docs covering all modules |
| **Alembic** | ✅ | Migrations in sync with models |
| **AI Inference** | ✅ | E2E verified: llama.cpp → Qwen 35B → "Hello" in 508ms |
| **WebSocket** | ✅ | Widget WS endpoint with JWT auth |
| **Widget** | ✅ | Standalone JS embed, no framework deps |

---

## Action Items Priority

1. ✅ ~~Remove `.env` from git history~~ — DONE (c5a0cbc3)
2. ✅ ~~C3 (JWT default)~~ — DONE (c5a0cbc3)
3. 🔴 **C1 (magic link URL)** — `auth.py:185` hardcoded `localhost:3000` → use env var
4. 🔴 **C2 (tests)** — Write pytest suite, minimum 30% coverage
5. 🟡 **B2+B3** — Remove hardcoded localhost from `main.py:64` + `local_driver.py:6`
6. 🟡 **F3+F4** — Wire WorkspacePicker/WorkspaceView memberCount from actual API
7. 🟡 **F5** — Wire SettingsView: profile save, avatar upload, account delete
8. 🟡 **B8** — Implement WS AI response routing (Stage 4)
9. 🟡 **F9** — Add error logging in all 15 empty `catch {}` blocks
10. 🟡 **W1** — Fix 4 bare `except:` blocks in backend
11. 🟢 **W8** — Replace `any` with `unknown` + typed interfaces
12. 🟢 **S1-S5** — Polish suggestions
