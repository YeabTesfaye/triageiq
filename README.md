# TriageIQ — AI Support Ticket Triage System

[![CI](https://github.com/YeabTesfaye/triageiq/actions/workflows/ci.yml/badge.svg)](https://github.com/YeabTesfaye/triageiq/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-107%20passing-brightgreen.svg)](https://github.com/YeabTesfaye/triageiq/actions)
[![Coverage](https://img.shields.io/badge/coverage-77%25-yellowgreen.svg)](https://github.com/YeabTesfaye/triageiq/actions)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Stop routing support tickets manually.** TriageIQ classifies, prioritises, and responds to every ticket with AI — then lets your team continue the conversation in real-time.

---

## What It Solves

Support teams waste hours reading, categorising, and routing tickets by hand. A billing issue goes to the technical team. A critical outage sits at "low priority." Customers wait days for a reply.

**TriageIQ fixes this end-to-end:**

- Customer submits a ticket → AI classifies it as **billing / technical / general**
- AI assigns **low / medium / high** priority based on urgency signals in the message
- AI drafts a professional **first response** instantly
- Customer and agent continue in a **real-time chat thread** — no email back-and-forth
- AI replies in the background; the agent is free to take over at any point
- Admins get full **audit trails**, **RBAC**, and **analytics** out of the box

---

## Architecture

Clean Architecture with strict one-way dependency flow:

```
Presentation  (Routers + Schemas)   — HTTP only, zero business logic
      ↓
Application   (Services)            — Orchestration, business rules
      ↓
Domain        (Entities + Enums)    — Pure Python, no framework deps
      ↓
Repositories  (Data Access)         — All SQL lives here, nowhere else
      ↑
Infrastructure (DB/Redis/AI/JWT)    — All external I/O lives here
```

**Enforced constraints:**
- Services never call the DB directly — only through repositories
- Routes never contain business logic — only call services
- External APIs (OpenAI, Firebase) only called from `infrastructure/`
- RBAC enforced via `Depends(require_roles(...))` — never inline in route handlers
- No hardcoded secrets — everything from `.env` via `pydantic-settings`

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| API | FastAPI + Uvicorn | Async-native, auto OpenAPI docs |
| AI triage | OpenAI GPT-4o-mini | Fast, cheap, structured JSON output |
| Real-time chat | Firebase Realtime DB | Push AI replies without polling |
| Database | PostgreSQL 16 + SQLAlchemy 2 async | Full async, type-safe, connection pooling |
| Auth | JWT HS256 + bcrypt 12 | No third-party auth service needed |
| Cache | Redis 7 | Token blacklist, rate limits, session kill |
| Migrations | Alembic | Versioned schema — no `create_all()` |
| Observability | structlog + Prometheus | JSON logs with `request_id`, `/metrics` |
| Testing | pytest-asyncio + httpx | 107 tests, 77% coverage, SQLite in-memory |
| Packaging | uv | 10× faster than pip, lockfile-reproducible |

---

## How a Ticket Works — End to End

```
1. POST /api/v1/tickets
   ├── Middleware: attach request_id, rate-limit check
   ├── Auth guard: decode JWT → check Redis blacklist → load user
   ├── Router: validate body, sanitise message (bleach)
   ├── TicketService: call OpenAI (15s timeout, 2 retries)
   │     └── category + priority + ai_response → save to PostgreSQL
   └── Return 201 with classified ticket

2. GET /api/v1/chat/{ticket_id}/thread
   └── Open chat window — ticket header + latest messages in one call

3. POST /api/v1/chat/{ticket_id}/messages
   ├── Persist user message → HTTP 201 immediately (<50ms)
   └── Background task: generate AI reply → push to Firebase
         └── Client receives reply via Firebase subscription (no polling)

4. GET /api/v1/chat/{ticket_id}/messages?before_id=<cursor>
   └── Load older messages — infinite scroll / "load more"
```

---

## Security Model

```
SUPERADMIN  ─── promote/demote admins · delete users · view audit logs
    │
  ADMIN  ─────── manage users · view global analytics
    │
MODERATOR  ─────── view all tickets · update ticket status
    │
  USER  ──────────── own tickets and own chat threads only
```

| Property | Implementation |
|---|---|
| Passwords | bcrypt cost factor 12 — never stored plain |
| Access tokens | JWT HS256, 15-minute expiry, JTI per token |
| Refresh tokens | SHA-256 hashed in DB, single-use with rotation |
| Logout | JTI blacklisted in Redis for remaining token lifetime |
| Suspension/ban | All active sessions killed immediately via Redis cutoff |
| Rate limiting | 100 req/min globally · 20 login attempts per 15 min per IP |
| Audit trail | Every privileged action written to immutable `audit_logs` table |

---

## Quick Start

### Option A — Docker (recommended)

```bash
git clone https://github.com/YeabTesfaye/triageiq
cd triageiq

cp .env.example .env
# Set OPENAI_API_KEY, JWT_SECRET_KEY, and FIREBASE_CREDENTIALS at minimum

# Start everything: postgres + redis + migrate + api
docker compose -f docker-compose.yml up --build

# Create the first superadmin (run once)
docker compose -f docker-compose.yml exec api \
  python scripts/seed_superadmin.py \
  --email admin@yourcompany.com \
  --name "Super Admin"
```

API at **http://localhost:8000** · Swagger UI at **http://localhost:8000/docs**

### Option B — Local development

```bash
git clone https://github.com/YeabTesfaye/triageiq
cd triageiq

uv sync --all-extras
cp .env.example .env

# Start backing services only
docker compose -f docker-compose.yml up postgres redis -d

uv run alembic upgrade head

uv run python scripts/seed_superadmin.py \
  --email admin@yourcompany.com \
  --name "Super Admin"

uv run uvicorn app.main:app --reload
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register — auto-assigned USER role |
| POST | `/api/v1/auth/login` | Authenticate → `{access_token (15min), refresh_token (7d)}` |
| POST | `/api/v1/auth/refresh` | Rotate token pair (single-use) |
| POST | `/api/v1/auth/logout` | Blacklist access token + revoke refresh |
| GET | `/api/v1/auth/me` | Current user profile |

All protected endpoints require: `Authorization: Bearer <access_token>`

---

### Tickets

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/tickets` | Submit ticket → AI classifies in real-time |
| GET | `/api/v1/tickets` | List own tickets (paginated) |
| GET | `/api/v1/tickets/{id}` | Get ticket (owner only — 404 if not owner) |
| GET | `/api/v1/analytics` | Own stats (USER) or global stats (ADMIN+) |

**Example — submit a ticket:**

```bash
curl -X POST http://localhost:8000/api/v1/tickets \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "My payment failed and I cannot access premium features."}'
```

```json
{
  "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
  "category": "billing",
  "priority": "high",
  "ai_response": "We are sorry about the payment issue. Our billing team will investigate and reach out within 2 hours.",
  "status": "open",
  "created_at": "2026-04-08T10:30:00Z"
}
```

---

### Chat

Real-time threaded conversation between the customer and the support team. AI replies are generated in the background and pushed via Firebase — clients subscribe to the thread instead of polling.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/chat/{ticket_id}/messages` | Send a message — AI reply pushed via Firebase |
| GET | `/api/v1/chat/{ticket_id}/thread` | Open chat window — ticket + messages in one call |
| GET | `/api/v1/chat/{ticket_id}/messages` | Load older messages (cursor pagination) |

**Typical client flow:**

```
1. GET  /chat/{id}/thread                       ← open chat (ticket header + latest messages)
2.      Subscribe to Firebase thread            ← receive AI replies in real-time
3. POST /chat/{id}/messages                     ← send message, 201 back in <50ms
4.      User scrolls up:
   GET  /chat/{id}/messages?before_id=<cursor>  ← load older messages
5. Repeat step 4 until has_more=false
```

**POST `/{ticket_id}/messages` — response:**

```json
{
  "id": "uuid",
  "ticket_id": "uuid",
  "sender_id": "uuid",
  "content": "Can you check my invoice #INV-2024-001?",
  "is_ai": false,
  "created_at": "2026-04-08T10:31:00Z"
}
```

The HTTP response is the user's own message. The AI reply arrives separately via Firebase push — keeping this endpoint under 50ms regardless of model latency.

**GET `/{ticket_id}/thread` — response:**

```json
{
  "ticket": {
    "id": "uuid",
    "subject": "My payment failed and I cannot access premium features.",
    "status": "open",
    "category": "billing",
    "priority": "high",
    "created_at": "2026-04-08T10:30:00Z"
  },
  "messages": [...],
  "total": 12,
  "limit": 50,
  "has_more": false,
  "next_cursor": null
}
```

---

### Admin — User Management

| Method | Endpoint | Role Required |
|---|---|---|
| GET | `/api/v1/admin/users` | ADMIN+ |
| GET | `/api/v1/admin/users/{id}` | ADMIN+ |
| PATCH | `/api/v1/admin/users/{id}/role` | SUPERADMIN only |
| PATCH | `/api/v1/admin/users/{id}/status` | ADMIN+ |
| DELETE | `/api/v1/admin/users/{id}` | SUPERADMIN only |

### Admin — Ticket Management

| Method | Endpoint | Role Required |
|---|---|---|
| GET | `/api/v1/admin/tickets` | MODERATOR+ |
| PATCH | `/api/v1/admin/tickets/{id}/status` | MODERATOR+ |
| DELETE | `/api/v1/admin/tickets/{id}` | ADMIN+ |

### Admin — Audit Logs

| Method | Endpoint | Role Required |
|---|---|---|
| GET | `/api/v1/admin/audit-logs` | SUPERADMIN only |

---

## AI Integration

### Ticket triage (synchronous)

Every ticket submitted to `POST /api/v1/tickets` is triaged inline:

- **Model:** `gpt-4o-mini` (configurable via `OPENAI_MODEL`)
- **Output:** `category` + `priority` + `ai_response` — strict JSON schema enforced by Pydantic
- **Resilience:** 15s timeout, 2 retries with exponential backoff
- **Degraded mode:** if AI is unavailable, ticket is saved without classification and a structured `503` is returned — the ticket is never lost

### Chat replies (asynchronous)

Every user message in a chat thread triggers a background AI reply:

- User sends message → `201` returned immediately (< 50ms)
- Background task generates the AI reply using the full ticket + thread context
- Reply is pushed to Firebase Realtime Database
- Client receives it via Firebase subscription — **no polling needed**
- The agent can take over at any point; AI only replies when no agent has responded

---

## Observability

- **Structured JSON logging** via structlog — every log line includes `request_id`, path, method, duration
- **`X-Request-ID` header** on every response — correlate logs to specific requests
- **Prometheus metrics** at `/metrics` — `http_requests_total`, `http_request_duration_seconds`
- **Health endpoints:**
  - `GET /health` — always 200 while app is running (lightweight, no DB check)
  - `GET /readiness` — checks PostgreSQL + Redis connectivity

---

## Running Tests

No external services needed — SQLite in-memory, Redis and OpenAI are mocked automatically.

```bash
JWT_SECRET_KEY="testsecretkey_minimum_32_characters_req" \
DATABASE_URL="sqlite+aiosqlite:///:memory:" \
REDIS_URL="redis://localhost:6379/0" \
OPENAI_API_KEY="sk-test" \
ENV="development" \
BCRYPT_ROUNDS="4" \
uv run pytest tests/ -v

# With coverage report
uv run pytest tests/ --cov=app --cov-report=term-missing
```

**107 tests across 5 files:**

| File | Coverage |
|---|---|
| `tests/unit/test_core.py` | Password hashing, JWT lifecycle, role hierarchy, AI schema validation |
| `tests/unit/test_auth_service.py` | Register, login, logout — all edge cases |
| `tests/unit/test_services.py` | TicketService, AdminService, ChatService business rules |
| `tests/integration/test_api_flows.py` | Full HTTP → DB flows, RBAC enforcement |
| `tests/unit/test_security.py` | Token blacklist, permissions |

---

## Environment Variables

```bash
# Required
JWT_SECRET_KEY=              # min 32 chars — python -c "import secrets; print(secrets.token_hex(32))"
DATABASE_URL=                # postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=                   # redis://host:6379/0
OPENAI_API_KEY=              # sk-...
FIREBASE_CREDENTIALS=        # path to Firebase service account JSON

# Optional (defaults shown)
ENV=development              # development | staging | production
BCRYPT_ROUNDS=12
WORKERS=2
ALLOWED_ORIGINS=http://localhost:3000
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
RATE_LIMIT_PER_MINUTE=100
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=15
OPENAI_MAX_RETRIES=2
```

---

## Project Structure

```
triageiq/
├── app/
│   ├── main.py                        # App factory, middleware, lifespan
│   ├── config.py                      # All config via pydantic-settings
│   ├── dependencies.py                # get_current_user, require_roles()
│   ├── presentation/
│   │   ├── routers/
│   │   │   ├── auth.py                # register, login, refresh, logout, me
│   │   │   ├── tickets.py             # submit, list, get, analytics
│   │   │   ├── chat.py                # send message, get thread, list messages
│   │   │   └── admin.py               # user mgmt, ticket mgmt, audit logs
│   │   └── schemas/                   # Pydantic request/response models
│   ├── application/
│   │   └── services/
│   │       ├── auth_service.py        # register, login, refresh, logout
│   │       ├── ticket_service.py      # create + triage, list, get
│   │       ├── chat_service.py        # send message, get thread, AI reply
│   │       └── admin_service.py       # user/ticket management, audit logging
│   ├── domain/
│   │   ├── entities/                  # User, Ticket, Message, AuditLog (ORM)
│   │   └── enums.py                   # Role, UserStatus, TicketStatus, etc.
│   ├── infrastructure/
│   │   ├── database.py                # Async engine, connection pooling
│   │   ├── redis_client.py            # Blacklist, cutoffs, rate limiting
│   │   ├── firebase.py                # Firebase Realtime DB push
│   │   ├── ai/openai_client.py        # Retry logic, validation, timeout
│   │   └── security/                  # JWT handler, bcrypt password handler
│   └── repositories/
│       ├── user_repository.py
│       ├── ticket_repository.py
│       ├── chat_repository.py         # Message CRUD, cursor pagination
│       ├── refresh_token_repository.py
│       └── audit_log_repository.py
├── alembic/                           # Versioned async migrations
├── tests/
│   ├── conftest.py                    # Shared fixtures, SQLite test engine
│   ├── unit/                          # Pure logic, fully mocked
│   └── integration/                   # HTTP → service → DB flows
│   ├── Dockerfile                     # Multi-stage, non-root, pinned uv
│   └── docker-compose.yml             # postgres + redis + migrate + api
├── scripts/
│   └── seed_superadmin.py             # Secure CLI, writes audit log
└── .github/workflows/ci.yml          # lint → typecheck → test → docker
```

---

## CI/CD

Every push to `main` or `develop`:

```
Lint & Format ──── Type Check ──── Tests (107) ──── Docker Build
ruff + black       mypy             pytest            multi-stage
                                    77% cov       needs lint + test ✓
```

---

## License

MIT — use it, extend it, ship it.
