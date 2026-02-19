# Spry Backend

Meeting analytics and productivity platform backend. Multi-organization model with Google Calendar integration.

## Tech Stack

- **Python 3.13+**, FastAPI, Uvicorn
- **PostgreSQL**, SQLAlchemy 2.0 (async), Alembic
- **Google OAuth2** (auth), **Google Calendar API** (sync, webhooks)
- **Google Cloud Storage** (file uploads), **Mailjet** (emails)
- **Docker Compose** for local development

## Project Structure

```
src/
├── core/                   # Database, config, exceptions, middleware
├── modules/
│   ├── auth/               # Google OAuth2 login, session management
│   ├── user/               # User profile, organizations list
│   ├── organization/       # Organization onboarding, cost settings
│   ├── organization_member/# Member CRUD, invitations, permissions
│   ├── organization_team/  # Team CRUD, membership
│   ├── invitation/         # Invitation tokens, email flow
│   ├── calendar/           # Google Calendar sync, webhooks, resync
│   ├── analytics/
│   │   ├── personal/       # Personal meeting & productivity metrics
│   │   └── organization/   # Organization-wide analytics
│   ├── home/               # Dashboard KPIs, deep work slots, agenda
│   └── agenda/             # Agenda data model
├── shared/                 # Email service, notifications, templates
└── templates/              # Jinja2 email templates
```

Each module follows: `router.py` → `service.py` → `repository.py` → `schemas.py` → `model.py`

## API Endpoints

### Auth (`/auth`)
- `GET /` — current user info (optional `?organization_id=`)
- `GET /google/` — initiate Google OAuth
- `GET /callback/google/` — OAuth callback
- `GET /logout/` — logout

### Users (`/users`)
- `GET /profile`, `PUT /profile`, `DELETE /delete`
- `GET /organizations` — user's organizations with roles

### Organizations (`/organizations`)
- `POST /onboard` — create organization (admin API key)
- `GET /{org_id}/cost`, `PUT /{org_id}/cost`

### Members (`/organizations/{org_id}/members`)
- `GET /` — list (search, pagination)
- `POST /` — add members (sends invitations)
- `PUT /{user_id}`, `DELETE /{user_id}`
- `POST /{user_id}/resend-invitation`

### Teams (`/organizations/{org_id}/teams`)
- `GET /`, `GET /{team_id}`, `POST /`, `PUT /{team_id}`, `DELETE /{team_id}`

### Invitations (`/invitations`)
- `GET /{token}` — accept invitation

### Calendar (`/integrations/google`)
- `POST /webhook` — Google Calendar push notifications
- `POST /resync` — manual user resync
- `POST /organizations/{org_id}/integrations/google/resync-all` — org-wide resync

### Personal Analytics (`/organizations/{org_id}/members/{user_id}/analytics/personal`)
- `GET /meeting` — meeting chart
- `GET /meeting/kpi` — KPIs
- `GET /meeting/participants`, `/distribution`, `/table`
- `GET /productivity`

### Organization Analytics (`/organizations/{org_id}/analytics/organization`)
- `GET /meeting/kpi`, `/meeting`, `/meeting/participants`, `/meeting/distribution`
- `GET /meeting/table`, `/productivity`

### Home (`/home`)
- `GET /kpi` — dashboard KPIs
- `GET /deep-work/time-slot` — available deep work slots
- `POST /deep-work/time-slot` — create deep work calendar blocks
- `GET /agenda-beta` — upcoming meetings agenda
- `POST /agenda-beta/{event_id}/notify`, `/add`

## Setup

```bash
cp .env.example .env    # configure environment
make build              # build Docker images
make run                # start containers
make migrate-upgrade    # apply migrations
```

## Development

```bash
make help               # show all commands
make run-detached       # run in background
make logs               # follow container logs
make lint               # run linter
make format             # run formatter
make shell              # open container shell
```

### Pre-commit hooks

```bash
pip install pre-commit
pre-commit install
```

Runs Ruff formatter and linter on every commit.

## Architecture

- **Multi-organization**: user can belong to multiple organizations; endpoints require `organization_id` context
- **RBAC**: role-based permissions via `OrganizationContext` + `require_permission()`
- **Calendar sync**: incremental sync via `sync_token`, full sync fallback, webhook-driven updates, automatic token refresh with retry/backoff
- **Async**: all I/O is async (SQLAlchemy async sessions, httpx, background tasks)
