# Aether — Universal AI Funnel SaaS

_«Канал → AI‑ядро → Услуга → Канал обратно»_

**Статус:** Stage 0 — архитектурный анализ
**Стек:** TBD (см. `docs/analysis/stack-analysis.md`)

## 🎯 Концепция

Aether — white‑label SaaS платформа, закрывающая полную воронку взаимодействия бизнеса с клиентами через:

1. **Channels** — входящие каналы (Telegram, WhatsApp, Web, Email, API)
2. **AI Core** — интеллектуальная обработка (классификация, маршрутизация, генерация)
3. **Services** — предметная логика бизнеса (заявки, документы, расчёты)
4. **Delivery** — ответ обратно через тот же или другой канал

## 📁 Структура проекта

```
aether/
├── README.md
├── docs/
│   ├── analysis/          ← Stage 0: аналитика
│   │   ├── stack-analysis.md
│   │   ├── channels-analysis.md
│   │   ├── ai-core-analysis.md
│   │   └── domain-analysis.md
│   ├── architecture/      ← Stage 1: граф архитектуры
│   │   ├── overview.md
│   │   ├── backend.md
│   │   ├── channels.md
│   │   ├── ai-core.md
│   │   ├── tenant.md
│   │   ├── frontend.md
│   │   └── devops.md
│   ├── specs/             ← Stage 2: спецификации
│   └── design/            ← Дизайн-решения
├── backend/               ← Код (после Stage 1)
├── frontend/              ← Код (после Stage 1)
├── infra/                 ← DevOps (Docker, CI/CD)
└── scripts/               ← Утилиты
```

## Этапы

| Stage | Что | Результат |
|-------|-----|-----------|
| 0 | Анализ стека, каналов, AI‑ядра, домена | 4 analysis‑документа |
| 1 | Архитектурный граф (классы, функции, компоненты) | `docs/architecture/*.md` |
| 2 | Спецификации API, БД, протоколов | `docs/specs/*.md` |
| 3 | MVP backend + frontend + AI core | Код |
| 4 | Pilot client onboarding | Production |
