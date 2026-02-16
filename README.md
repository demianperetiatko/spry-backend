# Spry Backend v2 - Migration Status

## Main Change

**v1 → v2: Transition from single organization to multi-organization model**

- **v1**: `OrganizationMember` belonged to one organization, contained `email`, `name`, `photo_url`
- **v2**: `User` can belong to multiple organizations via `OrganizationMember`
- **Consequence**: `type` and `permissions` depend on organization context

---

## Migrated Endpoints (41/41)

### Auth (4)
- `GET /auth/` - with optional `?organization_id={uuid}` for context
- `GET /auth/google/`, `GET /auth/callback/google/`, `GET /auth/logout/`

### User (4)
- `GET /users/profile`, `PUT /users/profile`, `DELETE /users/delete`
- **NEW** `GET /users/organizations` - list of organizations with roles and permissions

### Organization (3)
- `POST /organizations/onboard` (admin API)
- `GET /organizations/{organization_id}/cost`, `PUT /organizations/{organization_id}/cost`

### Invitation (1)
- `GET /invitations/{token}` - accept invitation with activation

### Analytics Personal (6)
- `GET /organizations/{organization_id}/members/{user_id}/analytics/personal/meeting`
- `GET /.../meeting/kpi`, `/meeting/participants`, `/meeting/distribution`, `/meeting/table`, `/productivity`

### Analytics Organization (6)
- `GET /organizations/{organization_id}/analytics/organization/meeting`
- `GET /.../meeting/kpi`, `/meeting/participants`, `/meeting/distribution`, `/meeting/table`, `/productivity`

### Calendar (1)
- **NEW** `POST /integrations/google/webhook` - automatic synchronization

### Organization Member (5)
- `GET /organizations/{organization_id}/members` - list of organization members (with pagination)
- `POST /organizations/{organization_id}/members` - add organization members
- `PUT /organizations/{organization_id}/members/{user_id}` - update member
- `DELETE /organizations/{organization_id}/members/{user_id}` - delete member
- `POST /organizations/{organization_id}/members/{user_id}/resend-invitation` - resend invitation

### Organization Team (5)
- `GET /organizations/{organization_id}/teams` - list teams
- `GET /organizations/{organization_id}/teams/{team_id}` - get team
- `POST /organizations/{organization_id}/teams` - create team
- `PUT /organizations/{organization_id}/teams/{team_id}` - update team
- `DELETE /organizations/{organization_id}/teams/{team_id}` - delete team
### Home (6)
- `GET /organizations/{organization_id}/home/kpi`
- `GET /organizations/{organization_id}/home/deep-work/time-slot`
- `POST /organizations/{organization_id}/home/deep-work/time-slot`
- `GET /organizations/{organization_id}/home/agenda-beta`
- `POST /organizations/{organization_id}/home/agenda-beta/{event_id}/notify`
- `POST /organizations/{organization_id}/home/agenda-beta/{event_id}/add`

---

## Key Changes

### Data Model
- **v1**: `OrganizationMember` (email, name, photo_url) → one organization
- **v2**: `User` (unique data) + `OrganizationMember` (relationship) → many organizations
- **v2**: `UserAccessInfo` instead of `OrganizationMemberCalendar` for tokens

### Organization Context
- `GET /auth/?organization_id={uuid}` → returns `UserWithOrganizationsInfo` with full list
- `GET /users/organizations` → list of organizations with `type` and `permissions` for each
- Endpoints use `organization_id` as path parameter + `OrganizationContext` dependency

### Architecture
- **v1**: Monolithic `service_views/`, synchronous code
- **v2**: Vertical Slice Architecture (modules: `router.py`, `service.py`, `repository.py`, `schemas.py`, `model.py`)
- **v2**: Repository Pattern, Dependency Injection, async/await, SQLAlchemy 2.0, Pydantic schemas

### New Modules
- **Invitation System**: tokens, email templates, transactions
- **Calendar Module**: Google Calendar API, webhooks, automatic synchronization
- **Email Service**: abstraction (Mailjet/Mock)

### Security
- `OrganizationContext` - automatic access verification
- `require_permission()` - dependency for permissions
- Transactions for critical operations (onboarding, invitation acceptance)

### Organization Member & Team - Logic Changes
- **v1 → v2 URL structure**:
  - v1: `/members/`, `/member/{member_id}/`, `/team/{team_id}`
  - v2: `/organizations/{organization_id}/members`, `/organizations/{organization_id}/members/{user_id}`, `/organizations/{organization_id}/teams/{team_id}`
- **v1 → v2 identification**: v1 used `member_id` (string), v2 uses `user_id` (UUID) - now it's the user ID, not the organization member ID
- **Adding members**: v2 checks user existence via `User` model, creates `Invitation` for new users, uses transactions
- **Updating member**: v2 checks permissions via `OrganizationContext`, uses `User` to get data, supports team membership updates
- **Teams**: v2 verifies all team members belong to the organization, uses `OrganizationTeamMember` with `organization_member_id` instead of direct `member_id`
- **Resend Invitation**: v2 checks member status (cannot send to active), uses new invitation system with tokens

---

## Statistics

| Category | Migrated | Not Migrated | Status |
|----------|----------|--------------|--------|
| Auth | 4 | 0 | 100% |
| User | 4 | 0 | 100% |
| Organization | 3 | 0 | 100% |
| Invitation | 1 | 0 | 100% |
| Calendar | 1 | 0 | 100% |
| Analytics Personal | 6 | 0 | 100% |
| Organization Member | 5 | 0 | 100% |
| Organization Team | 5 | 0 | 100% |
| Analytics Organization | 6 | 0 | 100% |
| Home | 6 | 0 | 100% |
| **Total** | **41** | **0** | **100%** |

---

## Important Notes

1. **`GET /auth/` without `organization_id`** returns only basic data (without `type`/`permissions`)
2. **Calendars**: v2 uses `UserAccessInfo` (one set of tokens) instead of `OrganizationMemberCalendar` (tokens at organization level)
3. **All migrated endpoints**: async/await, Pydantic schemas, Dependency Injection, transactions where needed
4. **Temporary**: `SINGLE_ORG_POLICY_ENABLED=True` enforces 1 user = 1 organization for frontend v1 compatibility; disable flag when redesign is ready.

---

## What Changed vs v1 (logic)

- **Multi-org**: user can бути у декількох організаціях; усі ендпоінти вимагають `organization_id` контекст.
- **Perms/roles**: права залежать від організації (через `OrganizationContext` + `require_permission`).
- **Calendars**: токени на користувача (`UserAccessInfo`), а не на організаційного учасника.
- **Teams/ Members**: валідація належності до організації, операції через репозиторії та транзакції.
- **Vertical Slice**: кожен модуль має `router/service/repository/schemas`; async + SQLAlchemy 2.0.

---

## Recent fixes (2026-01)

- **Analytics Organization**: прибрано дубль KPI `avg_daily_meetings_cost`, залишено один ключ.
- **Analytics Organization**: виправлено `NameError` у побудові графіка зустрічей (імпорт `AnalyticsCalculator`).

---

## Migration Status Snapshot (actual)

- Загалом мігровано: **35 / 41** (85%) — див. таблицю вище.
- Залишилось: **6** ендпоінтів (усі в Home).
- Нове в v2: webhook Google Calendar, список організацій користувача, багаторганізаційні перміси та оновлена архітектура.

---

## Calendar: ключові нюанси (v2)

- **Токени**: зберігаються у `UserAccessInfo` (на користувача). При кожному зверненні до Google календаря токен перевіряється та оновлюється (timeout refresh 30s). Якщо refresh/403 провалюється — sync помічається як `FAILED`, користувачу відправляється email про закінчення токена (`shared/notifications.py`, шаблон `templates/emails/token_expiry.html`). SMS немає.
- **Sync вікно**: якщо є `sync_token` — інкрементальний; якщо ні або `force_full` — повний sync за вікном: від найпершої події (або `now-180d`) до кінця поточного року.
- **Локи та ретраї**: перед sync береться lock, фонова синхронізація/конект/ресинк мають до 3 спроб з експоненційним backoff.
- **Webhooks**: канал вважається валідним, якщо не спливає менше ніж за 24h; якщо ні — перевидається. Перед watch старий канал зупиняється; webhook URL має бути HTTPS, інакше помилка конфігурації.
- **Пуш-нотифікації → інкрементальний sync**: webhook запускає `background_incremental_sync_task` для конкретного `user_calendar_id`.
- **Manual resync**: є фоновий ресинк для організації та користувача; використовує ті ж блокування й перевірки токенів.

---

## Next Steps

1. **Optional**: `POST /users/organizations/{id}/select` - save current organization in session
