# Database Schema — Spry

Всі таблиці і поля які є в базі даних.

---

## 📅 calendar_events — Зустрічі

Кожен запис = одна зустріч в календарі одного користувача.

| Поле | Тип | Опис |
|---|---|---|
| `id` | UUID | Первинний ключ |
| `google_event_id` | String | ID події в Google Calendar |
| `summary` | String(500) | **Назва зустрічі** |
| `description` | Text | **Текст опису / agenda** (null = немає agenda) |
| `location` | String(500) | Місце проведення |
| `start_datetime` | DateTime | **Початок зустрічі** |
| `end_datetime` | DateTime | **Кінець зустрічі** |
| `is_all_day` | Boolean | Чи цілоденна подія |
| `status` | enum | `confirmed` / `tentative` / `cancelled` |
| `organizer_email` | String | **Email організатора** |
| `creator_email` | String | Email того хто створив в календарі |
| `is_self_created` | Boolean | Чи сам користувач створив |
| `recurring_event_id` | String | **ID серії якщо зустріч повторювана** (null = одноразова) |
| `recurrence` | JSONB | Правило повторення (щодня / щотижня тощо) |
| `conference_data` | JSONB | Посилання на Google Meet / Zoom |
| `user_calendar_id` | UUID | → `user_calendars.id` |

**Що можна рахувати:**
- Тривалість: `end_datetime - start_datetime`
- Повторювані: `recurring_event_id IS NOT NULL`
- Без agenda: `description IS NULL OR description = ''`
- Скасовані: `status = 'cancelled'`
- Організовані мною: `organizer_email = мій_email`

---

## 👥 calendar_event_attendees — Учасники зустрічей

Кожен запис = один учасник однієї зустрічі.

| Поле | Тип | Опис |
|---|---|---|
| `id` | UUID | Первинний ключ |
| `calendar_event_id` | UUID | → `calendar_events.id` |
| `email` | String | **Email учасника** |
| `display_name` | String | Ім'я учасника |
| `response_status` | enum | **`accepted` / `declined` / `tentative` / `needsAction`** |
| `organizer` | Boolean | Чи є організатором цієї зустрічі |
| `optional` | Boolean | Чи необов'язковий учасник |
| `resource` | Boolean | Чи це ресурс (кімната, обладнання) а не людина |

**Що можна рахувати:**
- Кількість учасників: `COUNT(attendees)` де `resource = false`
- Хто відмовився: `response_status = 'declined'`
- Великі зустрічі: `COUNT(attendees) > 5`
- 1-на-1: `COUNT(attendees) = 2`

---

## 📆 user_calendars — Календарі користувачів

| Поле | Тип | Опис |
|---|---|---|
| `id` | UUID | Первинний ключ |
| `calendar_email` | String | Email пов'язаний з календарем |
| `type` | enum | `google` / `google_service` |
| `is_primary` | Boolean | Основний календар |
| `user_access_info_id` | UUID | → `users_access_info.id` |

---

## 👤 users — Користувачі

| Поле | Тип | Опис |
|---|---|---|
| `id` | UUID | Первинний ключ |
| `name` | String(128) | **Ім'я** |
| `email` | String(128) | **Email** (унікальний) |
| `photo_url` | Text | Фото |
| `status` | enum | `pending` / `active` |

---

## 🏢 organization_members — Члени організації

Зв'язок між користувачем і організацією.

| Поле | Тип | Опис |
|---|---|---|
| `id` | UUID | Первинний ключ |
| `user_id` | UUID | → `users.id` |
| `organization_id` | UUID | → `organizations.id` |
| `role` | enum | **`admin` / `member`** |
| `status` | enum | `active` / `pending` |
| `hourly_cost` | Numeric | **Годинна ставка** (для розрахунку вартості зустрічей) |

**Що можна рахувати:**
- Вартість зустрічі для людини: `hourly_cost × тривалість_в_годинах`
- Вартість зустрічі для всіх: сума `hourly_cost` кожного учасника × тривалість

---

## 🏢 organizations — Організації

| Поле | Тип | Опис |
|---|---|---|
| `id` | UUID | Первинний ключ |
| `name` | String | Назва організації |
| `organizations_currency_id` | UUID | → `organizations_currency.id` |

---

## 💰 organizations_currency — Налаштування вартості

| Поле | Тип | Опис |
|---|---|---|
| `id` | UUID | Первинний ключ |
| `currency_code` | String | Валюта: `USD`, `EUR` тощо |
| `cost_avg` | Numeric | **Середня годинна ставка по організації** |
| `cost_is_active` | Boolean | Чи увімкнений розрахунок вартості |
| `cost_type` | enum | `per_member` (індивідуально) / `average` (середня) |
| `cost_period` | enum | `hour` / `month` / `year` (в якому форматі вказана ставка) |
| `cost_visibility` | enum | Хто бачить вартість: `admin` / `manager` / `all` |

---

## 👥 organization_teams — Команди

| Поле | Тип | Опис |
|---|---|---|
| `id` | UUID | Первинний ключ |
| `name` | String(128) | **Назва команди** |
| `organization_id` | UUID | → `organizations.id` |

---

## 👥 organization_team_members — Члени команд

| Поле | Тип | Опис |
|---|---|---|
| `id` | UUID | Первинний ключ |
| `team_id` | UUID | → `organization_teams.id` |
| `organization_member_id` | UUID | → `organization_members.id` |
| `type` | enum | **`manager` / `member`** в цій команді |

---

## 📋 agenda_beta — Зустрічі з заповненою agenda

Трекер зустрічей для яких member заповнив agenda через систему.

| Поле | Тип | Опис |
|---|---|---|
| `id` | UUID | Первинний ключ |
| `organization_member_id` | UUID | → `organization_members.id` |
| `event_id` | String | Google Event ID зустрічі |

---

## 🔗 Зв'язки між таблицями

```
users
  └── users_access_info (1:1)
        └── user_calendars (1:many)
              └── calendar_events (1:many)
                    └── calendar_event_attendees (1:many)

users
  └── organization_members (1:many)
        ├── organization_member_calendars → user_calendars
        ├── organization_team_members → organization_teams
        └── agenda_beta

organizations
  ├── organization_members
  ├── organization_teams
  └── organizations_currency (1:1)
```
