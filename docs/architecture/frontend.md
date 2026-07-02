# 📁 Frontend — Admin Dashboard + Client Workspace

Два раздельных SPA. Никакого mixing вкладок платформы и бизнеса.

**Принцип:** Администрирование системы — отдельный кабинет от бизнес-кабинетов клиентов. Superadmin ≠ Tenant.

---

## 📊 Обзор

```
frontend/
├── 📁 admin/                          # Admin Dashboard (суперадминка)
│   ├── AdminApp.vue                   # Рутовый компонент админки
│   ├── router.ts                      # /aether/admin/* роуты
│   ├── 📁 layouts/
│   │   └── AdminLayout.vue            # Shell: sidebar + topbar + content
│   ├── 📁 views/
│   │   ├── DashboardView.vue          # Главная: хелс, MRR, DAU, графики
│   │   ├── TenantsListView.vue        # Таблица tenant'ов
│   │   ├── TenantDetailView.vue       # Карточка tenant'а
│   │   ├── SubscriptionsView.vue      # Все подписки
│   │   ├── PluginsView.vue            # Управление плагинами платформы
│   │   ├── DriversView.vue            # AI-драйверы: статус, метрики
│   │   ├── AuditView.vue              # Платформенный аудит
│   │   ├── BillingView.vue            # Счета, выручка
│   │   └── AnalyticsView.vue          # MRR, churn, когорты
│   └── 📁 components/
│       ├── AdminSidebar.vue           # Навигация админки
│       ├── TenantStatusBadge.vue      # active/trial/suspended
│       ├── SubscriptionStatusBadge.vue
│       ├── HealthIndicator.vue        # Зелёный/жёлтый/красный
│       ├── PlatformStatsCard.vue      # Big number + trend
│       ├── TenantCreateDialog.vue     # Модалка создания tenant
│       └── DriverMetricsChart.vue     # График latency/errors
│
├── 📁 client/                          # Client Workspace (email-client layout)
│   ├── ClientApp.vue                  # Рутовый компонент
│   ├── router.ts                      # /aether/{slug}/* (3 роута: workspace, settings, analytics)
│   ├── 📁 layouts/
│   │   └── ClientLayout.vue           # White-label shell с трёхпанельным workspace
│   ├── 📁 views/
│   │   ├── WorkspaceView.vue          # Главный экран: трёхпанельный inbox
│   │   ├── SettingsView.vue           # Все настройки на ОДНОЙ странице
│   │   ├── AnalyticsView.vue          # Статистика бизнеса
│   │   ├── SignupView.vue             # Регистрация компании
│   │   ├── LoginView.vue              # Smart login (passwordless-first)
│   │   ├── VerifyView.vue             # Magic link landing
│   │   ├── AcceptInviteView.vue       # Приглашение в Workspace
│   │   └── WorkspacePickerView.vue    # Выбор организации (если несколько)
│   └── 📁 components/
│       ├── 📁 workspace/               # Компоненты трёхпанельного workspace
│       │   ├── WorkspaceSidebar.vue   # Левая панель: папки, каналы, сервисы
│       │   ├── FolderList.vue         # Входящие, Важные, Черновики, Отправленные
│       │   ├── ChannelFilter.vue      # Фильтр по каналам (Telegram/Widget/Email)
│       │   ├── ServiceQuickAccess.vue # Быстрый доступ к сервисам
│       │   ├── ConversationList.vue   # Средняя панель: inbox
│       │   ├── ConversationListItem.vue # Один диалог (аватар, превью, время, канал)
│       │   ├── ConversationDetail.vue # Правая панель: окно диалога
│       │   ├── ChatHeader.vue         # Заголовок: имя, статус, канал, действия
│       │   ├── ChatMessages.vue       # Список сообщений (виртуальный скролл)
│       │   ├── ChatMessage.vue        # Одно сообщение (user/AI/system)
│       │   ├── ChatComposer.vue       # Поле ввода: текст + emoji + файлы
│       │   ├── QuickReplies.vue       # AI-предложенные быстрые ответы
│       │   ├── ConversationInfo.vue   # Боковая панель: инфо о диалоге
│       │   └── EmptyState.vue         # Placeholder когда диалог не выбран
│       └── 📁 settings/               # Компактные секции настроек
│           ├── BrandingSection.vue
│           ├── ChannelsSection.vue
│           ├── ChannelConfigInline.vue
│           ├── AISettingsSection.vue
│           ├── ServicesSection.vue
│           ├── ServiceConfigInline.vue
│           ├── UsersSection.vue       # Приглашения + роли
│           ├── BillingSection.vue
│           └── AuditSection.vue
│
└── 📁 shared/                          # Общие компоненты
    ├── 📁 ui/
    │   ├── BaseButton.vue
    │   ├── BaseInput.vue
    │   ├── BaseCard.vue
    │   ├── BaseBadge.vue
    │   ├── BaseModal.vue
    │   ├── BaseTable.vue
    │   ├── BaseTabs.vue
    │   ├── BaseToggle.vue
    │   ├── BaseChart.vue
    │   └── InlineEdit.vue             # Редактирование на месте (click to edit)
    ├── 📁 composables/
    │   ├── useApi.ts
    │   ├── useAuth.ts
    │   ├── useTenant.ts
    │   └── useWebSocket.ts
    └── 📁 types/
        ├── admin.ts
        ├── client.ts
        └── common.ts
```

---

## 🎯 Принцип: SettingsView — все настройки на ОДНОЙ странице

```
SettingsView.vue
│
├── BrandingSection      [лого, цвета, название]          ← 1 форма, 3 поля
├── ChannelsSection      [список каналов]
│   └── ChannelConfigInline [настройка канала]             ← открывается inline, не уводит
├── AISettingsSection    [модель, промпты, язык, tone]    ← 1 форма, 5 полей
├── ServicesSection      [список сервисов]
│   └── ServiceConfigInline [настройка сервиса]            ← открывается inline
├── UsersSection         [таблица операторов]             ← инлайн приглашение
├── BillingSection       [подписка, счета, кредиты]       ← read-only карточки
└── AuditSection         [лог действий]                   ← таблица с фильтром по дате
```

**Антипаттерн (как НЕ делать):** `/settings/branding`, `/settings/channels`, `/settings/channels/1`, `/settings/ai`, `/settings/services`, `/settings/services/1`, `/settings/users`, `/settings/billing`, `/settings/audit` — 10+ роутов для 6 секций.

**Паттерн (как делать):** `/settings` — одна страница. Секции раскрываются по клику. Формы — inline редактирование, не модалки и не отдельные страницы.

---

## 1. Admin Dashboard — структура

### `AdminApp.vue` — Entry Point
```typescript
// Роутинг админки: /aether/admin/*
const routes = [
  { path: '', component: DashboardView },
  { path: 'tenants', component: TenantsListView },
  { path: 'tenants/:id', component: TenantDetailView },
  { path: 'subscriptions', component: SubscriptionsView },
  { path: 'plugins', component: PluginsView },
  { path: 'drivers', component: DriversView },
  { path: 'audit', component: AuditView },
  { path: 'billing', component: BillingView },
  { path: 'analytics', component: AnalyticsView },
];
```

### `AdminLayout.vue` — Shell
```
┌──────────────────────────────────────────────────┐
│  TopBar: Aether Admin | superadmin@aether.cloud   │
├──────────┬───────────────────────────────────────┤
│ Sidebar  │  Content Area                         │
│          │                                       │
│ 🏠 Dash  │  [Tenant List] / [Metrics] / ...      │
│ 🏢 Tenants│                                      │
│ 💳 Subs   │                                       │
│ 🧩 Plugins│                                       │
│ 🧠 Drivers│                                       │
│ 📋 Audit  │                                       │
│ 💰 Billing│                                       │
│ 📊 Analytics│                                     │
└──────────┴───────────────────────────────────────┘
```

### `DashboardView.vue`
```typescript
// Главная админки: health + ключевые метрики + tenant рост
// Компоненты:
// - HealthIndicator (зелёный/жёлтый/красный для каждого компонента)
// - PlatformStatsCard: Total Tenants, Active Today, MRR, DAU, API Calls/h
// - TenantGrowthChart (linear график)
// - RecentAuditTable (последние 20 действий)
```

### `TenantsListView.vue`
```typescript
// Таблица всех tenant'ов: поиск, фильтр (active/trial/suspended), пагинация
// Колонки: slug, name, plan, status, users, created, actions
// Actions: view, suspend/reactivate, change plan
// Кнопка: + Create Tenant → TenantCreateDialog
```

### `TenantDetailView.vue`
```typescript
// Полная карточка tenant:
// Tab: Overview (статус, план, пользователи, каналы)
// Tab: Channels (какие каналы настроены)
// Tab: Services (установленные плагины)
// Tab: Billing (подписка, счета)
// Tab: Audit (лог действий этого tenant)
// Tab: Login As (impersonate — войти как tenant_admin)
```

---

## 2. Client Workspace — структура (Email-Client Layout)

**Принцип:** UI как почтовый клиент — знаком всем пользователям. Трёхпанельный макет.
Аналоги: Gmail, Outlook, Front, Intercom, Help Scout.

### Трёхпанельный Layout (основной экран)

```
┌──────────────────────────────────────────────────────────────────────┐
│ TopBar: [🔍 Поиск по диалогам...]     [⚙️] [🔔] [👤 User ▼]        │
├────────────┬───────────────────────────────┬─────────────────────────┤
│  SIDEBAR   │  CONVERSATION LIST            │  CONVERSATION DETAIL    │
│  (навигация)│  (средняя панель — inbox)     │  (правая панель — чат)  │
│            │                               │                         │
│ 📥 Входящие│  ┌─────────────────────────┐  │  Сегодня 14:22          │
│    (3)     │  │ 🟢 Иван Петров          │  │  ┌──────────────────┐    │
│ ⭐ Важные  │  │ Запрос ставки на вагон..│  │  │ Иван: Сколько    │    │
│ ✍️ Черновик│  │ 5 мин назад             │  │  │ будет стоить     │    │
│ 📤 Отправл.│  └─────────────────────────┘  │  │ перевозка угля   │    │
│ 🗑 Корзина │  ┌─────────────────────────┐  │  │ из Кузбасса?     │    │
│            │  │ 🔵 Сергей Сидоров       │  │  └──────────────────┘    │
│ ─────────  │  │ Нужна ГУ-12 на 3 вагона │  │  ┌──────────────────┐    │
│ Каналы     │  │ 12 мин назад             │  │  │ AI: Рассчитаю    │    │
│ 📱 Telegram│  └─────────────────────────┘  │  │ стоимость. Уточ- │    │
│ 💬 Widget  │  ┌─────────────────────────┐  │  │ ните вес груза?  │    │
│ ✉️ Email   │  │ ⚪ Мария Иванова        │  │  └──────────────────┘    │
│            │  │ Счёт на оплату...       │  │                         │
│ ─────────  │  │ 1 час назад             │  │  ┌───────────────────┐  │
│ Сервисы    │  └─────────────────────────┘  │  │ [Ввод сообщения]  │  │
│ 🧮 Кальк.  │                               │  │ [📎] [😊] [▶️ Send]│  │
│ 📄 ГУ-12   │  [Загрузить ещё...]           │  └───────────────────┘  │
│ 🚂 ЭТРАН   │                               │                         │
└────────────┴───────────────────────────────┴─────────────────────────┘
```

### Компоновка панелей

| Панель | Ширина | Назначение |
|--------|--------|------------|
| Левая (Sidebar) | 56px (collapsed) / 220px (expanded) | Навигация: папки, каналы, сервисы |
| Средняя (Inbox) | 320px | Список диалогов — как inbox в почте |
| Правая (Chat) | flex-1 (остаток) | Активный диалог / Placeholder |

**Адаптив:**
- На мобильных (<768px): одна панель на весь экран, навигация — жесты/swipe
- На планшетах (768-1024px): две панели (inbox + chat), sidebar скрыт
- Десктоп (>1024px): все три панели

### `ClientApp.vue` — Entry Point (упрощённый роутинг)

```typescript
// В email-client модели почти всё на одном экране.
// Отдельные страницы — только Settings и Analytics.

const routes = [
  { path: '', component: WorkspaceView },       // ← трёхпанельный inbox (главный экран)
  { path: 'settings', component: SettingsView }, // ← все настройки на 1 странице
  { path: 'analytics', component: AnalyticsView },
];

// ConversationsView, ConversationDetail, UsersView, AuditView — 
// теперь не отдельные роуты, а панели внутри WorkspaceView.
```

### `WorkspaceView.vue` — Главный экран (трёхпанельный)

```typescript
// Основной Workspace — аналог почтового клиента.
// Три панели: Sidebar | ConversationList | ConversationDetail
// 
// Состояние:
// - activeFolder: 'inbox' | 'important' | 'drafts' | 'sent' | 'trash'
// - activeChannel: ChannelType | null (фильтр по каналу)
// - selectedConversationId: UUID | null
// - conversations: ConversationSummary[] (пагинированный список)
// - sidebarCollapsed: boolean
//
// Поведение:
// - Клик по диалогу в средней панели → открывается в правой
// - Поиск (Ctrl+K / Cmd+K) → фокус в строку поиска TopBar
// - Клавиатурная навигация: ↑↓ по списку, Enter открыть, Esc закрыть
// - WebSocket: новые сообщения → диалог прыгает наверх (как новое письмо)
```

### Компоненты Workspace

```
frontend/client/
├── views/
│   ├── WorkspaceView.vue          # Трёхпанельный экран
│   ├── SettingsView.vue           # Все настройки (1 страница)
│   └── AnalyticsView.vue          # Статистика
│
├── 📁 workspace/
│   ├── WorkspaceSidebar.vue       # Левая панель: папки, каналы, сервисы
│   ├── FolderList.vue             # Список папок: Входящие, Важные, Черновики...
│   ├── ChannelFilter.vue          # Фильтр по каналам (Telegram, Widget, Email)
│   ├── ServiceQuickAccess.vue     # Быстрый доступ к сервисам (Калькулятор, ГУ-12)
│   ├── ConversationList.vue       # Средняя панель: inbox
│   ├── ConversationListItem.vue   # Один элемент списка (аватар, имя, превью, время)
│   ├── ConversationDetail.vue     # Правая панель: окно диалога
│   ├── ChatHeader.vue             # Заголовок диалога (имя, канал, статус, действия)
│   ├── ChatMessages.vue           # Сообщения (виртуальный скролл для тысяч сообщений)
│   ├── ChatMessage.vue            # Одно сообщение (user/AI/system)
│   ├── ChatComposer.vue           # Поле ввода: текст + emoji + файлы + быстрые ответы
│   ├── QuickReplies.vue           # Предложенные AI быстрые ответы
│   ├── ConversationInfo.vue       # Боковая панель: инфо о диалоге, контакте, истории
│   └── EmptyState.vue             # Placeholder когда диалог не выбран
│
├── 📁 settings/                   # Компактные настройки (без изменений)
│   ├── BrandingSection.vue
│   ├── ChannelsSection.vue
│   ├── ChannelConfigInline.vue
│   ├── AISettingsSection.vue
│   ├── ServicesSection.vue
│   ├── ServiceConfigInline.vue
│   ├── UsersSection.vue           # ← обновлено: приглашения + роли
│   ├── BillingSection.vue
│   └── AuditSection.vue
│
└── 📁 auth/                       # Аутентификация
    ├── SignupView.vue             # Single-field: email + компания
    ├── LoginView.vue              # Email → challenge (password/passkey/magic link)
    ├── VerifyView.vue             # Magic link landing
    ├── AcceptInviteView.vue       # Приглашение в организацию
    └── WorkspacePickerView.vue    # Выбор Workspace (если несколько)
```

### `ConversationListItem.vue` — ключевой компонент

```typescript
// Один элемент в inbox — как письмо в почтовом клиенте.
// 
// Props:
// - conversation: ConversationSummary
// - isSelected: boolean
// - isUnread: boolean
//
// UI:
// ┌──────────────────────────────────────┐
// │ 🟢 [Аватар]  Иван Петров    5м назад │  ← зелёный индикатор = онлайн
// │             Запрос ставки на вагон... │  ← preview текста (1 строка)
// │             📱 Telegram               │  ← иконка канала
// └──────────────────────────────────────┘
//
// Состояния:
// - Непрочитанное: жирный шрифт + синяя точка
// - Важное: жёлтая звезда слева
// - В обработке AI: спиннер
// - Ожидает ответа: оранжевый индикатор
```

### `ChatComposer.vue` — поле ввода

```typescript
// Поле ввода сообщения — как в почтовом клиенте / мессенджере.
// 
// Фичи:
// - Авторасширение (textarea с max-height)
// - Shift+Enter → новая строка, Enter → отправить
// - Поддержка Markdown (жирный, курсив, списки)
// - Emoji picker (всплывающее окно)
// - Вложение файлов (drag & drop + кнопка)
// - Quick Replies (предложенные AI кнопки над полем ввода)
// - Индикатор «AI печатает...» когда плагин обрабатывает
```

### Auth Flow компоненты

```typescript
// SignupView.vue — Single-field регистрация
// ┌──────────────────────────────────┐
// │         🚀 Создать Workspace      │
// │                                  │
// │  Email:    [________________]    │
// │  Компания: [________________]    │
// │                                  │
// │  [Создать]  или [Войти]         │
// └──────────────────────────────────┘

// LoginView.vue — Smart login
// ┌──────────────────────────────────┐
// │         👋 Войти в Aether         │
// │                                  │
// │  Email: [________________]       │
// │  [Продолжить]                    │
// │                                  │
// │  — или —                         │
// │  [G] Google  [Я] Яндекс  [V] VK │
// └──────────────────────────────────┘
// После ввода email:
// - Если есть passkey → предложить биометрию
// - Если есть пароль → поле пароля
// - Если ничего → magic link отправлен

// AcceptInviteView.vue — Принять приглашение
// ┌──────────────────────────────────┐
// │  🎉 Вас пригласили в «Логистика+» │
// │                                  │
// │  Роль: Оператор                  │
// │  Пригласил: Иван Петров          │
// │                                  │
// │  [Принять приглашение]           │
// └──────────────────────────────────┘
```

---

## 3. Shared UI Kit (общие компоненты)

```typescript
// InlineEdit.vue — ключевой компонент для эргономики
// Позволяет редактировать поле на месте, без модалок и отдельных страниц
// 
// <InlineEdit v-model="channel.name" @save="updateChannel">
//   <template #display>{{ channel.name }}</template>
//   <template #edit><BaseInput v-model="editValue" /></template>
// </InlineEdit>

// BaseTable.vue — таблица с сортировкой, поиском, пагинацией
// BaseTabs.vue — вкладки внутри страницы (не роуты)
// BaseToggle.vue — переключатель (для фича-флагов)
// BaseCard.vue — карточка с заголовком и действиями
// BaseModal.vue — модальное окно (только для создания новых сущностей, не для редактирования)
```

---

## 4. White-Label Theming

```typescript
// Theme system — цвета клиента применяются к Client Workspace
// Admin Dashboard всегда использует дефолтную тему Aether

interface TenantTheme {
  primaryColor: string;       // #1a73e8
  secondaryColor: string;     // #34a853
  logoUrl: string | null;
  faviconUrl: string | null;
  companyName: string;
}

// CSS Variables (инжектятся в :root при загрузке ClientApp):
// --aether-primary: #1a73e8;
// --aether-primary-light: #e8f0fe;
// --aether-sidebar-bg: #f8f9fa;
// --aether-font: 'Inter', sans-serif;
```

---

## 5. Роутинг и Entry Points

```
# Nginx/Aether Gateway routing:

/aether/admin/           → Admin SPA (admin/index.html)
/aether/admin/*          → Admin SPA (client-side routing)

/aether/{tenant-slug}/   → Client SPA (client/index.html)
/aether/{tenant-slug}/*  → Client SPA (client-side routing)

/api/v1/                 → Backend API (FastAPI)
/api/v1/admin/*          → Admin API (superadmin required)
/api/v1/tenants/{tid}/*  → Tenant API (tenant_admin/user required)
/webhooks/*              → Public webhook endpoints
```

---

## 📊 Статистика модуля

| Раздел | Файлов | Компонентов | Описание |
|--------|--------|------------|----------|
| Admin Dashboard | ~15 | ~12 | Только платформенное управление |
| Client Workspace | ~28 | ~25 | Email-client трёхпанельный layout + settings + auth |
| Shared | ~16 | ~14 | Общие UI компоненты, composables, типы |
| **Итого** | **~59 файлов** | **~51 компонент** | |

## 🔑 Ключевые принципы

1. **Admin ≠ Client** — раздельные SPA, раздельная навигация, нет пересечения
2. **Email-client layout** — трёхпанельный inbox (Sidebar | Inbox | Chat) как основной интерфейс
3. **Passwordless-first auth** — magic link по умолчанию, passkeys для returning users, OAuth для соцсетей
4. **Organisation model** — регистрация компании → invitation сотрудников по email → роли
5. **SettingsView compact** — все настройки на одной странице, секции раскрываются inline
6. **Inline editing > modals** — не уводить пользователя на отдельную страницу ради 3 полей
7. **White-label только для Client Workspace** — Admin Dashboard всегда в теме Aether
8. **Role-based visibility** — компоненты проверяют `membership.role` перед рендером
9. **Клавиатурная навигация** — ↑↓ по списку, Enter открыть, Esc закрыть, Ctrl+K поиск
10. **Нет dead clicks** — каждая кнопка ведёт к действию, не к пустой странице
