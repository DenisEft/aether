# Анализ каналов связи для Aether — универсальной AI-воронки

> Актуально на июль 2026. Целевой рынок: РФ/СНГ.

---

## 1. Telegram Bot API

### Сводная таблица

| Параметр | Оценка |
|---|---|
| **API зрелость** | ⭐⭐⭐⭐⭐ — один из самых зрелых, стабильных и задокументированных бот-API в индустрии |
| **SDK / экосистема** | Python (python-telegram-bot, aiogram), Node.js (Telegraf, GramIO), Go (telegram-bot-api), Ruby, PHP — огромный выбор |
| **Rate limits** | 1 msg/sec в личке, ~30 msg/sec глобально (broadcast). С Paid Broadcast — до 1000 msg/sec за 0.1 Stars/msg (~$0.002) |
| **Стоимость** | **$0** — API полностью бесплатен, без подписки, без per-message. Платишь только за хостинг ($5-15/мес VPS) и LLM-вызовы |
| **Rich media** | Фото, видео, аудио, документы (до 50 МБ), inline-кнопки, reply-кнопки, sticker, polls, media groups (карусели до 10 файлов), animated/premium stickers |
| **Уведомления** | Push-нотификации на уровне OS, silent mode, service notifications. Нет template messages — но нет и ограничений на инициативу |
| **Mini Apps / Web Apps** | Полная поддержка (Telegram Web Apps — SPA в iframe, H5P, game schemes). Отдельный API-уровень |
| **Юридические риски (РФ)** | ⚠️ С февраля 2026 Кремль начал дросселировать Telegram. Риск полного блокирования существует. Данные хранятся на серверах Telegram (Дубай/Швеция) — трансграничная передача ПДн по 152-ФЗ |
| **ЦА в РФ** | ~80 млн пользователей. Основная аудитория 20-45 лет, бизнес, IT, маркетологи, фрилансеры |

### Плюсы
- Полностью бесплатный API
- Лучшая экосистема SDK (aiogram, Telegraf, GramIO)
- Inline-кнопки, callback-данные — идеальны для воронок и сценариев
- Mini Apps (Web Apps) — полноценные SPA-интерфейсы прямо в Telegram
- Нет ограничений на инициативу разговора (нет conversation window)
- Webhook и long polling (getUpdates)

### Минусы
- ⚠️ **Риск блокирования в РФ** — уже идёт дросселирование (2025-2026), полный бан возможен
- Трансграничная передача данных (152-ФЗ)
- Нет native template messages — все сообщения пользовательские
- Rate limits на broadcast без Stars

### Рекомендация для Aether
**✅ MVP-канал №1.** Telegram — must-have для РФ/СНГ воронки несмотря на риски. Бот-воронка — основной use-case. Мини-приложения (Web Apps) дают полноценный UI.

---

## 2. WhatsApp Business Cloud API (Meta)

### Сводная таблица

| Параметр | Оценка |
|---|---|
| **API зрелость** | ⭐⭐⭐⭐ — зрелый Cloud API от Meta, прямая интеграция без BSP |
| **SDK / экосистема** | Официальный Python/Node SDK, Graph API. BSP-партнёры (Respond.io, WATI, 360dialog) |
| **Rate limits** | Tier-система по уникальным пользователям за 24ч: Tier 1 = 1K, Tier 2 = 10K, Tier 3 = 100K, Tier 4 = 1M. Начнёшь с Tier 1 |
| **Стоимость** | С июля 2025 — **per-message billing** вместо per-conversation. Шаблонные сообщения платные, пользовательские в окне — бесплатно. Примерные ставки (РФ): Utility ~$0.005-0.02, Marketing ~$0.01-0.08, Authentication ~$0.005-0.015 |
| **Rich media** | Фото, видео, аудио, документы (до 100 МБ), интерактивные кнопки (Reply Buttons, List, CTA), carousels (до 10 карточек), location |
| **Уведомления** | Template messages (утверждённые Meta), 24h customer service window. Free entry points (Click-to-WhatsApp ads) |
| **Юридические риски (РФ)** | 🔴 **Критический риск.** С августа 2025 — ограничения вызовов, декабрь 2025 — дросселирование до 80%, февраль 2026 — попытка полной блокировки. Meta под санкциями. Данные на серверах Meta (США/ЕС) |
| **ЦА в РФ** | ~100 млн пользователей WhatsApp, но растёт нестабильность. В СНГ (Казахстан, Узбекистан, Беларусь) — стабильно высокая база |

### Плюсы
- Огромная пользовательская база в РФ/СНГ
- Лучший rich media (карусели, интерактивные кнопки)
- Высокий open rate (~98%)
- Template messages для outbound
- Интеграция с Meta Ads (Click-to-WhatsApp)

### Минусы
- 🔴 **Блокирование в РФ** — самый критический риск для РФ-ориентированного SaaS
- Платный API (per-template message)
- Сложная верификация шаблонов (Meta approval)
- Tier-система rate limits
- 24h conversation window
- Meta под санкциями РФ — юридические/платёжные сложности

### Рекомендация для Aether
**⏸️ Отложить на Phase 2.** Слишком рискованно для РФ. Имеет смысл только для СНГ (Казахстан, Беларусь, Узбекистан) и международных клиентов. Если делаешь — делай через BSP-партнёра с fallback.

---

## 3. Web Widget (встраиваемый чат на сайт)

### Сводная таблица

| Параметр | Оценка |
|---|---|
| **API зрелость** | ⭐⭐⭐ — нет единого API, это кастомный фронт. Используешь React/Vue/Svelte компонент + WebSocket |
| **SDK / экосистема** | Самописный виджет. Альтернативы: Tawk.to, Jivo, Chatra, Crisp (но это конкуренты). Библиотеки: Socket.IO, Pusher, ably |
| **Rate limits** | Зависит от инфраструктуры. WebSocket connections ~10K-100K на сервер (Node/Go). Масштабируемо |
| **Стоимость** | **$0-50/мес** — самописный виджет. Платишь за WebSocket-инфраструктуру и хостинг. Push notifications: Firebase Cloud Messaging ($0), Web Push ($0) |
| **Rich media** | Полный контроль — HTML/CSS/JS. Фото, видео, файлы, rich embeds, карточки, кнопки, прогресс-бары, анимации |
| **Уведомления** | Web Push Notifications (Service Workers), browser notifications, email fallback, SMS fallback. Onboarding — модальные окна, cookie-consent |
| **Юридические риски (РФ)** | ✅ Минимальные — данные хранишь на своих серверах. Cookie-consent по 152-ФЗ. Нет трансграничной передачи, если серверы в РФ |
| **ЦА в РФ** | Все посетители сайтов. Не зависит от мессенджера. Единственный канал с прямым доступом к трафику |

### Плюсы
- Полный контроль над UI/UX
- Нет зависимости от внешних платформ (блокирование, санкции)
- Данные на своих серверах — 152-ФЗ, GDPR compliance
- Интеграция с аналитикой (GA, Яндекс.Метрика)
- Контекстный чат (видит что делает пользователь на сайте)
- White-label — легко кастомизируется

### Минусы
- Нужно писать и поддерживать фронт (React/Vue)
- Нет push-уведомлений «в мессенджер» — только browser push (низкий open rate ~5-20%)
- Зависит от визита на сайт
- Web Push notification — ненадёжный канал (браузеры блокируют, нужно разрешение)
- Нет offline-доступа (PWA частично решает)

### Рекомендация для Aether
**✅ MVP-канал №2.** Критически важен для white-label SaaS. Это канал, который даёт полный контроль и compliance. Для воронок — как primary landing-point.

---

## 4. Email (SMTP/IMAP воронка)

### Сводная таблица

| Параметр | Оценка |
|---|---|
| **API зрелость** | ⭐⭐⭐⭐ — стандарты SMTP/IMAP (RFC 5321/3501). Зрелые библиотеки: Postmark, SendGrid, Resend, Mailgun, Amazon SES |
| **SDK / экосистема** | Python (smtplib, aiosmtplib), Node.js (nodemailer, @resend/node). ESP: Postmark, Resend, Mailchimp, SendPulse |
| **Rate limits** | Зависит от провайдера. Amazon SES: ~14,400 msg/hr (по умолчанию), до 500K/hr. Postmark: 300 msg/min. SendGrid: 100 msg/min (free) |
| **Стоимость** | Amazon SES: **$0.10 / 1000 писем**. Postmark: $0.50 / 1000. SendGrid: бесплатно до 100/день. Resend: $0.50 / 1000. IMAP-чтение: обычно входит в план |
| **Rich media** | HTML-письма, inline-картинки, кнопки (CTA). Ограничения: нет видео (только GIF/ссылки), нет интерактивных кнопок в письме (только ссылки). AMP for Email (Gmail, Yahoo) — интерактивные формы |
| **Уведомления** | Transactional email, drip-campaigns, welcome series. Нет push (но email → link → action). Open/click tracking |
| **Юридические риски (РФ)** | ✅ Низкие. 152-ФЗ требует согласия на рассылку. GDPR — для ЕС. Данные хранишь сам. Email — один из самых регуляторно-зрелых каналов |
| **ЦА в РФ** | 100% аудитории. Email — самый массовый канал. Open rate ~15-25%. Click rate ~2-5% |

### Плюсы
- Самый массовый канал (100% покрытие)
- Дёшево (Amazon SES ~$0.0001/письмо)
- Дрип-воронки — native email-фича
- Высокая deliverability при правильной репутации
- Легко комбинировать с другими каналами
- Transactional + marketing

### Минусы
- Низкий open rate (15-25%)
- Сложности с deliverability (spam, blacklists, DKIM/SPF/DMARC)
- Нет мгновенного взаимодействия
- Сложная верстка кросс-клиентных HTML-писем
- Нет native rich media (карусели, inline-кнопки с callback)

### Рекомендация для Aether
**✅ MVP-канал №3.** Email — essential для воронок (onboarding, nurturing, re-engagement, drip). Дёшево, массово, регуляторно чисто. Делай как transactional email-движок с шаблонами.

---

## 5. VK / Telegram Mini Apps

### Сводная таблица

| Параметр | Оценка |
|---|---|
| **API зрелость** | ⭐⭐ — VK Mini Apps (Mini Apps + VK Pay) и Telegram Web Apps — разные экосистемы, быстрое развитие, документация среднестатистическая |
| **SDK / экосистема** | VK: vk-mini-apps SDK (React/Vue/JS). Telegram: Web App SDK (@twa-dev/sdk). VK Pay + Telegram Stars для платежей |
| **Rate limits** | VK: зависит от типа API. Telegram: унаследованы от Bot API |
| **Стоимость** | VK: бесплатно, комиссия VK Pay ~3-5%. Telegram: бесплатно, Stars — 0.1 Stars/msg для broadcast. Комиссия за выплаты |
| **Rich media** | Полноценный WebView (React/HTML/CSS/JS). VK: карусели, кнопки, списки, inline-контент. Telegram Web Apps: полный HTML |
| **Уведомления** | VK: push в приложении. Telegram: push через бота. Нет template messages |
| **Юридические риски (РФ)** | ✅ VK — российская платформа, данные в РФ, 152-ФЗ compliant. Telegram — см. выше (Дубай/Швеция, трансграничная передача) |
| **ЦА в РФ** | VK: ~85 млн пользователей (основная аудитория 18-35). Telegram Web Apps: растёт, ~15-20 млн активных пользователей Mini Apps |

### Плюсы
- VK: полностью российская экосистема, 152-ФЗ, VK Pay
- Telegram Web Apps: быстрый рост, SPA-интерфейсы
- Нативные платежи (VK Pay, Stars)
- Интеграция с соцсетями, маркетплейсами

### Минусы
- Маленькая аудитория Mini Apps по сравнению с обычными ботами
- Быстро меняющиеся API
- Сложная отладка (разные устройства, версии приложений)
- VK: ограничения на функциональность Mini Apps
- Telegram Web Apps: зависят от Telegram (те же риски блокирования)
- Не отдельный канал — это расширение Telegram/VK ботов

### Рекомендация для Aether
**⏸️ Отложить на Phase 2.** Mini Apps — это не отдельный канал связи, а UI-расширение ботов. Делать когда Telegram-бот работает, и нужен богатый UI (формы, каталоги, оплата). VK Mini Apps — как backup для РФ.

---

## 6. REST API (White-Label интеграция)

### Сводная таблица

| Параметр | Оценка |
|---|---|
| **API зрелость** | ⭐⭐⭐⭐ — стандартный REST/GraphQL, OpenAPI/Swagger. Zod validation, FastAPI (Python), или NestJS (Node.js) |
| **SDK / экосистема** | Самописное API. Swagger/OpenAPI docs, Postman collection, SDK для Python/Node/PHP. Webhook для async events |
| **Rate limits** | Настраиваемые: token bucket / sliding window. Пример: 100 req/min (free), 1000 req/min (pro), 10,000 req/min (enterprise) |
| **Стоимость** | **$0** — самописное. Платишь за инфраструктуру. Monitization: subscription или per-request pricing |
| **Rich media** | Полный контроль — JSON с attachments, file uploads (multipart/form-data), rich responses. Клиент рендерит как хочет |
| **Уведомления** | Webhook-уведомления (event-driven), polling. Push via WebSocket/SSE. Client-side notification |
| **Юридические риски (РФ)** | ✅ Минимальные — данные не покидают инфраструктуру клиента. API только передает данные, хранение у клиента. GDPR/152-ФЗ — ответственность клиента |
| **ЦА в РФ** | B2B клиенты: CRM, ERP, маркетплейсы, кастомные чат-боты, агентства |

### Плюсы
- White-label — ключевая ценность для SaaS
- Полный контроль над архитектурой
- Масштабируемо (any client, any channel)
- Revenue: subscription pricing
- Webhook-first архитектура
- Идеально для enterprise

### Минусы
- Высокий порог входа для клиентов (нужен разработчик)
- Нужно поддерживать versioning (v1, v2)
- Документация и SDK — ongoing overhead
- Rate limiting и abuse detection
- Нет готовой пользовательской базы (нужно привлекать клиентов)

### Рекомендация для Aether
**✅ MVP-канал №4 (параллельно).** REST API — основа white-label SaaS. Делай с нуля, но не как priority #1. API-first архитектура с самого начала, но функциональность — Phase 1.5.

---

## Сравнительная таблица

| Канал | Стоимость | Rich Media | Push | Юр. риски РФ | ЦА РФ | Сложность |
|---|---|---|---|---|---|---|
| **Telegram Bot** | $0 | ★★★★☆ | ★★★★☆ | ⚠️ Средние | ★★★★★ | ★☆☆☆☆ |
| **WhatsApp** | $/msg | ★★★★★ | ★★★★★ | 🔴 Критичные | ★★★★☆ | ★★★☆☆ |
| **Web Widget** | $0-50/мес | ★★★★★ | ★★☆☆☆ | ✅ Низкие | ★★★★★ | ★★★☆☆ |
| **Email** | $0.0001/msg | ★★★☆☆ | ★☆☆☆☆ | ✅ Низкие | ★★★★★ | ★★☆☆☆ |
| **VK Mini Apps** | $0 | ★★★★☆ | ★★★☆☆ | ✅ Низкие | ★★★☆☆ | ★★★★☆ |
| **REST API** | $0 (infra) | ★★★★★ | ★★★☆☆ | ✅ Низкие | ★★★★☆ | ★★★★☆ |

---

## MVP Рекомендации

### Запускать первыми (Phase 1):

| Приоритет | Канал | Почему |
|---|---|---|
| **1** | **Telegram Bot** | Основная воронка. Бесплатно. Лучшая экосистема. inline-кнопки для сценариев. 80 млн ЦА в РФ |
| **2** | **Web Widget** | White-label. Полный контроль. 152-ФЗ compliant. Нет зависимости от платформ. Контекстный чат |
| **3** | **Email** | Drip-воронки. Onboarding. Нurturing. Дёшево. 100% покрытие. Transactional + marketing |

### Отложить (Phase 2):

| Канал | Когда подключать |
|---|---|
| **WhatsApp** | Когда есть клиенты в СНГ (Казахстан, Узбекистан) или нужно cover WhatsApp-аудиторию |
| **VK Mini Apps** | Когда Telegram-бот работает и нужен богатый UI / backup для РФ |
| **REST API** | Phase 1.5 — делать API-first архитектуру с начала, но полноценную документацию и SDK — когда есть B2B-спрос |

### Архитектурная рекомендация

```
                    ┌─────────────┐
                    │   Aether    │
                    │   Core      │
                    │ (AI Engine) │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼───┐ ┌─────▼─────┐
        │ Telegram  │ │  Web  │ │  Email    │
        │   Bot     │ │Widget │ │  (SES)    │
        └───────────┘ └───────┘ └───────────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼──────┐
                    │ Channel     │
                    │  Abstraction│
                    │  Layer      │
                    └─────────────┘
```

Ключевой принцип: **Channel Abstraction Layer** — единый интерфейс для всех каналов. Каждый канал — adapter. Это позволит добавлять WhatsApp/VK/REST без переписывания core-логики.

---

*Анализ составлен: июль 2026*
*Источники: Meta Developers, Telegram Bot API docs, RKН, 152-ФЗ, workspace.ru*
