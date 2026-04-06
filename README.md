# TriageIQ — AI Support Ticket Triage System

Production-grade FastAPI backend with AI-powered ticket classification, full RBAC, JWT authentication with token rotation, Redis-backed blacklisting, and comprehensive audit logging.

---

## Architecture

Clean Architecture with strict layer separation:

```
Presentation (Routers/Schemas)
      ↓
Application (Services)
      ↓
Domain (Entities/Enums)
      ↓
Infrastructure (DB/Redis/OpenAI/JWT)
      ↑
Repositories (all DB access)
```

**Rules enforced:**

- No DB calls in services — only through repositories
- No business logic in routers — only in services
- No external API calls outside infrastructure layer
- No circular dependencies
- No hardcoded secrets — all from `.env` via `pydantic-settings`

---

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker + Docker Compose (for full stack)
- PostgreSQL 15 + Redis 7 (or use Docker)

### Local Development

```bash
# Clone and enter
git clone <repo>
cd triageiq

# Install dependencies
uv sync

# Copy and fill in environment
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY, DATABASE_URL, REDIS_URL, OPENAI_API_KEY

# Run database migrations
uv run alembic upgrade head

# Seed the first superadmin (REQUIRED before using admin features)
uv run python scripts/seed_superadmin.py \
  --email admin@yourcompany.com \
  --password "StrongPass@99" \
  --name "Super Admin"

# Start the server
uv run uvicorn app.main:app --reload
```

API available at: `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`
ReDoc: `http://localhost:8000/redoc`

### Docker (Full Stack)

```bash
# Copy env and set OPENAI_API_KEY at minimum
cp .env.example .env

# Build and start all services (api + postgres + redis)
docker compose -f docker/docker-compose.yml up --build

# Seed superadmin inside container
docker compose -f docker/docker-compose.yml exec api \
  python scripts/seed_superadmin.py \
  --email admin@yourcompany.com \
  --password "StrongPass@99"
```

---

## Authentication Flow

```
POST /api/v1/auth/register   → Creates USER account
POST /api/v1/auth/login      → Returns {access_token (15min), refresh_token (7d)}
POST /api/v1/auth/refresh    → Rotates token pair (single-use enforcement)
POST /api/v1/auth/logout     → Blacklists access token in Redis + revokes refresh
GET  /api/v1/auth/me         → Current user profile
```

All protected endpoints require: `Authorization: Bearer <access_token>`

**Security properties:**

- Passwords: bcrypt with cost factor 12
- JWT payload: only `user_id`, `role`, `jti` (no PII)
- Access tokens blacklisted on logout via Redis JTI store
- Refresh tokens: hashed (SHA-256) in DB, single-use, rotated on every use
- Suspended/banned users: all sessions invalidated immediately via Redis cutoff timestamp
- Failed logins: tracked per-IP (Redis) and per-account (DB), lockout after 5 failures

---

## Role-Based Access Control

```
SUPERADMIN  → everything below + promote/demote admins, delete users, audit logs
ADMIN       → everything below + manage users, view global analytics
MODERATOR   → view all tickets, update ticket status
USER        → own tickets only
```

RBAC is enforced via `Depends(require_roles(...))` — never inline in route handlers.

**SUPERADMIN creation:** Cannot be done via API by design. Use the seed script:

```bash
uv run python scripts/seed_superadmin.py --email ... --password ... --name ...
```

---

## API Reference

### Tickets (Authenticated Users)

| Method | Endpoint               | Description                                                |
| ------ | ---------------------- | ---------------------------------------------------------- |
| POST   | `/api/v1/tickets`      | Submit ticket → AI triage (category + priority + response) |
| GET    | `/api/v1/tickets`      | List own tickets (paginated)                               |
| GET    | `/api/v1/tickets/{id}` | Get specific ticket (owner only)                           |
| GET    | `/api/v1/analytics`    | Own stats (users) or global stats (admins)                 |

### Admin — User Management

| Method | Endpoint                          | Role Required |
| ------ | --------------------------------- | ------------- |
| GET    | `/api/v1/admin/users`             | ADMIN+        |
| GET    | `/api/v1/admin/users/{id}`        | ADMIN+        |
| PATCH  | `/api/v1/admin/users/{id}/role`   | SUPERADMIN    |
| PATCH  | `/api/v1/admin/users/{id}/status` | ADMIN+        |
| DELETE | `/api/v1/admin/users/{id}`        | SUPERADMIN    |

### Admin — Ticket Management

| Method | Endpoint                            | Role Required |
| ------ | ----------------------------------- | ------------- |
| GET    | `/api/v1/admin/tickets`             | MODERATOR+    |
| PATCH  | `/api/v1/admin/tickets/{id}/status` | MODERATOR+    |
| DELETE | `/api/v1/admin/tickets/{id}`        | ADMIN+        |

### Admin — Audit Logs

| Method | Endpoint                   | Role Required |
| ------ | -------------------------- | ------------- |
| GET    | `/api/v1/admin/audit-logs` | SUPERADMIN    |

---

## AI Integration

Tickets are processed by OpenAI on creation:

- **Model:** `gpt-4o-mini` (configurable)
- **Output:** `category` (billing/technical/general) + `priority` (low/medium/high) + `ai_response`
- **Resilience:** 15s timeout, 2 retries with exponential backoff
- **Degraded mode:** If AI unavailable, ticket is saved without classification; structured error returned

---

## Observability

- **Structured JSON logging** via structlog — every log line includes `request_id`
- **`X-Request-ID` header** on every response (auto-generated if not provided)
- **Prometheus metrics** at `/metrics`:
  - `http_requests_total` (by endpoint, method, status)
  - `http_request_duration_seconds`
- **Health endpoints:**
  - `GET /health` — always 200 if app is running
  - `GET /readiness` — checks DB + Redis connectivity

---

## Testing

```bash
# Run all tests
JWT_SECRET_KEY="testsecretkey_minimum_32_characters_req" \
DATABASE_URL="sqlite+aiosqlite:///:memory:" \
REDIS_URL="redis://localhost:6379/0" \
OPENAI_API_KEY="sk-test" \
ENV="development" \
BCRYPT_ROUNDS="4" \
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=app --cov-report=term-missing
```

**101 tests** covering:

- Password hashing, policy validation
- JWT creation/validation/blacklisting
- Role hierarchy and RBAC enforcement
- Auth flows: register, login, refresh, logout, token reuse prevention
- Ticket flows: create with AI, ownership enforcement, pagination
- Admin flows: role change, status change, suspension blocks login, soft delete
- Audit log access control

---

## Project Structure

```
triageiq/
├── app/
│   ├── main.py                    # FastAPI app factory, middleware, lifespan
│   ├── config.py                  # Pydantic settings (all from .env)
│   ├── dependencies.py            # get_current_user, require_roles() factory
│   ├── presentation/
│   │   ├── routers/               # auth, tickets, admin, analytics
│   │   └── schemas/               # Pydantic request/response models
│   ├── application/services/      # AuthService, TicketService, AdminService
│   ├── domain/
│   │   ├── entities/              # User, Ticket, RefreshToken, AuditLog (ORM)
│   │   └── enums.py               # Role, UserStatus, TicketStatus, etc.
│   ├── infrastructure/
│   │   ├── database.py            # Async SQLAlchemy engine + session factory
│   │   ├── db_types.py            # CompatibleJSONB (JSONB on PG, JSON on SQLite)
│   │   ├── redis_client.py        # Token blacklist, cutoff timestamps, rate limiting
│   │   ├── ai/openai_client.py    # OpenAI async client with retry + validation
│   │   └── security/              # JWT handler, password handler (direct bcrypt)
│   └── repositories/              # UserRepo, TicketRepo, RefreshTokenRepo, AuditLogRepo
├── alembic/                       # Async migrations
├── tests/
│   ├── unit/                      # Pure logic tests (no external services)
│   └── integration/               # Full HTTP→DB flow tests (SQLite in-memory)
├── docker/
│   ├── Dockerfile                 # Multi-stage, non-root appuser
│   └── docker-compose.yml         # api + postgres + redis
├── scripts/
│   └── seed_superadmin.py         # One-time superadmin creation
├── .github/workflows/ci.yml       # lint → type-check → test → docker build
└── pyproject.toml
```
