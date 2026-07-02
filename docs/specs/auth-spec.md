# Спецификация Auth Flow для Aether SaaS платформы

## 1. Общие принципы

Aether использует passwordless-first подход (с 2025+), где регистрация происходит через email + название компании, после чего пользователь получает magic link для входа. В системе реализованы следующие методы аутентификации:

1. Magic link (email-based)
2. Passkeys (WebAuthn)
3. OAuth (Google, Яндекс ID, VK ID)
4. Пароль (как fallback)
5. MFA (TOTP + hardware keys)

Токены:
- JWT access токены (15 минут)
- Refresh токены (7 дней)
- API keys для автоматизаций

## 2. Архитектурные ограничения

- Все эндпоинты auth защищены через middleware rate limiting
- JWT токены содержат tenant_id и org_id для multi-tenant изоляции
- Сессии управляются через Redis (session store)
- Требуется обязательная MFA для admin/owner ролей
- SSO (OIDC/SAML) для enterprise (Stage 3)
- Все данные по пользователю хранятся в PostgreSQL с RLS

## 3. Flow диаграммы

### 3.1. Регистрация (Single-field signup)

```
[User] → [POST /auth/signup] → [Magic Link Email] → [User clicks link] → [GET /auth/verify]
        ↓
[Redirect to Dashboard / Login]
```

### 3.2. Вход (Smart login)

```
[User] → [POST /auth/login]
        ↓
[Server] → [Check if user has MFA enabled]
        ↓
[If MFA enabled] → [Send TOTP challenge] → [User enters TOTP]
        ↓
[Else] → [Generate tokens and redirect]
```

### 3.3. Magic Link Auth

```
[User] → [POST /auth/magic-link]
        ↓
[Server] → [Check user exists]
        ↓
[Generate magic link with JWT token]
        ↓
[Send to user email]
        ↓
[User clicks link]
        ↓
[GET /auth/magic-link/verify]
        ↓
[Verify token, generate tokens, redirect]
```

### 3.4. Passkey Registration

```
[User] → [GET /auth/passkey/register]
        ↓
[Server] → [Generate challenge]
        ↓
[Send to client]
        ↓
[Client] → [WebAuthn registration]
        ↓
[Client] → [Send challenge response]
        ↓
[Server] → [Verify signature, store credential]
```

### 3.5. Passkey Authentication

```
[User] → [GET /auth/passkey/login]
        ↓
[Server] → [Generate challenge]
        ↓
[Send to client]
        ↓
[Client] → [WebAuthn authentication]
        ↓
[Client] → [Send challenge response]
        ↓
[Server] → [Verify signature, validate user]
        ↓
[Generate tokens, redirect]
```

### 3.6. OAuth Flow

```
[User] → [GET /auth/oauth/google]
        ↓
[Redirect to Google OAuth]
        ↓
[Google] → [User authenticates]
        ↓
[Google] → [Redirect back to Aether]
        ↓
[Server] → [Exchange code for tokens]
        ↓
[Server] → [Create or update user]
        ↓
[Generate tokens, redirect]
```

### 3.7. Invitation Accept

```
[User] → [GET /auth/invite/accept]
        ↓
[Server] → [Verify invite token]
        ↓
[Create user if not exists]
        ↓
[Assign role to organization]
        ↓
[Generate tokens, redirect]
```

## 4. JWT токены

Формат JWT токенов:

### 4.1. Claims

```
{
  "sub": "uuid",           // User ID
  "tenant_id": "uuid",    // Tenant ID
  "org_id": "uuid",       // Organization ID
  "role": "string",      // Role (owner, admin, member, viewer)
  "permissions": ["string"], // List of permissions
  "exp": 1234567890,      // Expiration timestamp
  "jti": "uuid",           // Token ID for revocation
  "iat": 1234567890,         // Issued at
  "iss": "aether",           // Issuer
  "aud": "aether"          // Audience
}
```

### 4.2. Типы токенов

- **Access token** (15 минут):
  - Используется для доступа к API
  - Выдается при успешной авторизации
  - Закодирован в JWT

- **Refresh token** (7 дней):
  - Используется для получения нового access token
  - Хранится в secure, http-only cookie
  - Подлежит rotation и revocation

## 5. Эндпоинты

### 5.1. Основные эндпоинты

| Метод | Путь | Описание |
|---------|------|---------|
| POST | `/auth/signup` | Регистрация нового пользователя |
| POST | `/auth/login` | Аутентификация |
| POST | `/auth/magic-link` | Генерация magic link |
| GET | `/auth/magic-link/verify` | Проверка magic link |
| POST | `/auth/passkey/register` | Регистрация passkey |
| POST | `/auth/passkey/login` | Аутентификация через passkey |
| GET | `/auth/oauth/google` | OAuth через Google |
| GET | `/auth/oauth/yandex` | OAuth через Яндекс |
| GET | `/auth/oauth/vk` | OAuth через VK |
| GET | `/auth/invite/accept` | Принятие приглашения |
| POST | `/auth/refresh` | Обновление access token |
| POST | `/auth/logout` | Выход |
| POST | `/auth/api-keys` | Создание API key |
| DELETE | `/auth/api-keys/{key_id}` | Отзыв API key |

### 5.2. Request/Response схемы

#### 5.2.1. Регистрация (POST /auth/signup)

**Request:**
```json
{
  "email": "string",
  "company_name": "string"
}
```

**Response:**
```json
{
  "message": "Magic link sent to email"
}
```

#### 5.2.2. Magic link (POST /auth/magic-link)

**Request:**
```json
{
  "email": "string"
}
```

**Response:**
```json
{
  "message": "Magic link sent to email"
}
```

#### 5.2.3. Magic link verification (GET /auth/magic-link/verify)

**Query params:**
```
token: string
```

**Response:**
```json
{
  "access_token": "string",
  "refresh_token": "string"
}
```

#### 5.2.4. Вход (POST /auth/login)

**Request:**
```json
{
  "email": "string",
  "password": "string",
  "mfa_code": "string",
  "remember_me": "boolean"
}
```

**Response:**
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer"
}
```

#### 5.2.5. Passkey регистрация (POST /auth/passkey/register)

**Request:**
```json
{
  "email": "string"
}
```

**Response:**
```json
{
  "challenge": "string",
  "public_key": {
    "rp": {
      "name": "string"
    },
    "user": {
      "id": "string",
      "name": "string",
      "displayName": "string"
    },
    "challenge": "string",
    "pubKeyCredParams": [
      {
        "type": "string",
        "alg": "string"
      }
    ],
    "timeout": "number",
    "excludeCredentials": [
      {
        "type": "string",
        "id": "string"
      }
    ],
    "authenticatorSelection": {
      "requireResidentKey": "boolean",
      "userVerification": "string"
    },
    "attestation": "string"
  }
}
```

#### 5.2.6. Passkey аутентификация (POST /auth/passkey/login)

**Request:**
```json
{
  "email": "string"
}
```

**Response:**
```json
{
  "challenge": "string",
  "public_key": {
    "challenge": "string",
    "timeout": "number",
    "allowCredentials": [
      {
        "type": "string",
        "id": "string"
      }
    ],
    "userVerification": "string"
  }
}
```

#### 5.2.7. OAuth (GET /auth/oauth/google)

**Response:**
```json
{
  "redirect_url": "string"
}
```

#### 5.2.8. Приглашение (GET /auth/invite/accept)

**Query params:**
```
token: string
```

**Response:**
```json
{
  "access_token": "string",
  "refresh_token": "string"
}
```

#### 5.2.9. Обновление токена (POST /auth/refresh)

**Request:**
```json
{
  "refresh_token": "string"
}
```

**Response:**
```json
{
  "access_token": "string"
}
```

#### 5.2.10. Выход (POST /auth/logout)

**Request:**
```json
{
  "refresh_token": "string"
}
```

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

#### 5.2.11. Создание API key (POST /auth/api-keys)

**Request:**
```json
{
  "description": "string"
}
```

**Response:**
```json
{
  "key_id": "string",
  "key": "string",
  "description": "string",
  "created_at": "datetime"
}
```

#### 5.2.12. Отзыв API key (DELETE /auth/api-keys/{key_id})

**Response:**
```json
{
  "message": "API key revoked"
}
```

## 6. Refresh token rotation + revocation

### 6.1. Rotation

Каждый раз при обновлении access token через refresh token, старый refresh token аннулируется и генерируется новый. Это предотвращает повторное использование украденных refresh token.

### 6.2. Revocation

Refresh token может быть отозван по следующим причинам:
- Пользователь выходит из системы
- Система обнаружила подозрительную активность
- Пользователь изменил пароль
- Пользователь был заблокирован

### 6.3. Структура

Токены хранятся в Redis с TTL:
- Access token: 15 минут
- Refresh token: 7 дней
- Время хранения токенов также может быть ограничен по дате истечения

## 7. Безопасность

### 7.1. CSRF защита

- Все формы и POST эндпоинты защищены CSRF токенами
- Токены хранятся в secure cookies
- Используются SameSite cookies

### 7.2. XSS защита

- Все данные, выводимые в UI, проходят через sanitizer
- Используются Content Security Policy (CSP)
- Все API эндпоинты защищены CORS

### 7.3. Rate limiting

- Auth endpoint:
  - IP-based: 5 login attempts/минуту, 3 signup/hour
  - Tenant-based: ограничения на уровне tenant'ов

### 7.4. Защита от brute force

- Повторные попытки входа ограничены по IP
- Уведомление о подозрительной активности
- Блокировка аккаунта после N попыток

### 7.5. Проверка паролей

- Пароль должен содержать:
  - Минимум 12 символов
  - Минимум 1 строчную букву
  - Минимум 1 заглавную букву
  - Минимум 1 цифру
  - Минимум 1 специальный символ
- Проверка на уязвимые пароли через HaveIBeenPwned API

### 7.6. Защита от replay-атак

- Все JWT токены имеют уникальный JTI (JWT ID)
- Система отслеживает использованные токены для предотвращения replay-атак

## 8. Сессии и устройств

### 8.1. Множественные устройства

Пользователь может быть залогинен на нескольких устройствах одновременно.

### 8.2. Logout all

Пользователь может выйти со всех устройств, что аннулирует все refresh токены.

### 8.3. Сессии в Redis

- Сессии хранятся в Redis с TTL
- Используются для отслеживания активных устройств
- Позволяют отслеживать и блокировать подозрительные сессии

## 9. Организации и роли

### 9.1. Модель организации

Каждый пользователь может быть связан с одной или несколькими организациями.

### 9.2. Роли

- **Owner** (владелец): полный доступ ко всем ресурсам
- **Admin** (администратор): управление каналами и сервисами
- **Member** (участник): работа с диалогами
- **Viewer** (наблюдатель): только просмотр

### 9.3. Разрешения

Разрешения реализованы через matrix:
- Owner: все разрешения
- Admin: управление каналами, сервисами, пользователями
- Member: работа с диалогами
- Viewer: только чтение

## 10. Примеры JSON схем

### 10.1. Токен ответ

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwYzQ4M2JjZi03ZjQ5LTQ3YjItYmM0Mi1lNzYwOWY4Mjg4ZmQiLCJ0ZW5hbnRfaWQiOiJhZjI4NTA1ZS0yMjI0LTRhMjctYjQwZS02ZjQ2ZjQ2ZjQ2ZjQiLCJvcmdfaWQiOiJkZjQ2ZjQ2ZjQ2ZjQ2ZjQ2ZjQ2ZjQ2ZjQ2ZjQ2Iiwicm9sZSI6Im93bmVyIiwicGVybWlzc2lvbnMiOlsiYWRtaW4iXSwiZXhwIjoxNjgxNzQ3MDAwLCJqdGkiOiIwYzQ4M2JjZi03ZjQ5LTQ3YjItYmM0Mi1lNzYwOWY4Mjg4ZmQiLCJpYXQiOjE2ODE3NDM0MDB9.Xs64W4Yt0p3x5p3x5p3x5p3x5p3x5p3x5p3x5p3x5p3",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwYzQ4M2JjZi03ZjQ5LTQ3YjItYmM0Mi1lNzYwOWY4Mjg4ZmQiLCJ0ZW5hbnRfaWQiOiJhZjI4NTA1ZS0yMjI0LTRhMjctYjQwZS02ZjQ2ZjQ2ZjQ2ZjQiLCJvcmdfaWQiOiJkZjQ2ZjQ2ZjQ2ZjQ2ZjQ2ZjQ2ZjQ2ZjQ2ZjQ2Iiwicm9sZSI6Im93bmVyIiwicGVybWlzc2lvbnMiOlsiYWRtaW4iXSwidHlwZSI6InJlZnJlc2giLCJleHAiOjE2ODE3NDcwMDAsImp0aSI6IjBjNDgzYmNmLTdmNDktNDdiMi1iYzQyLWU3NjA5ZjgyODhmZCIsImlhdCI6MTY4MTc0MzQwMH0.5p3x5p3x5p3x5p3x5p3x5p3x5p3x5p3x5p3x5p3x5p3",
  "token_type": "bearer"
}
```

### 10.2. Ошибка

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "Неверный email или пароль",
    "details": {}
  }
}
```

### 10.3. Информация о пользователе

```json
{
  "id": "0c483bcf-7f49-47b2-bc42-e7609f8288fd",
  "email": "user@example.com",
  "full_name": "Иван Петров",
  "is_active": true,
  "is_superadmin": false,
  "last_login_at": "2026-07-02T12:34:56Z",
  "mfa_enabled": true,
  "roles": [
    {
      "id": "98765432-1234-5678-9012-345678901234",
      "name": "admin",
      "permissions": ["manage_channels", "manage_users"]
    }
  ]
}
```

## 11. Обработка ошибок

### 11.1. Коды ошибок

| Код | Описание |
|------|----------|
| `invalid_credentials` | Неверные учетные данные |
| `user_not_found` | Пользователь не найден |
| `token_expired` | Токен истек |
| `token_invalid` | Токен недействителен |
| `rate_limit_exceeded` | Превышен лимит запросов |
| `mfa_required` | Требуется MFA |
| `password_too_weak` | Слабый пароль |
| `email_already_registered` | Email уже зарегистрирован |

### 11.2. Структура ошибки

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {
      "field": "string"
    }
  }
}
```
