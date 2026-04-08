# Contributing to TriageIQ

---

## Table of contents

- [Prerequisites](#prerequisites)
- [Local setup](#local-setup)
- [Running the server](#running-the-server)
- [Running tests](#running-tests)
- [Code quality](#code-quality)
- [Adding a database migration](#adding-a-database-migration)
- [Project structure](#project-structure)
- [Architecture rules](#architecture-rules)
- [Branching strategy](#branching-strategy)
- [Pull request checklist](#pull-request-checklist)
- [Environment variables reference](#environment-variables-reference)

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | [python.org](https://www.python.org/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker + Compose | latest | [docker.com](https://www.docker.com/) |
| Redis | 7+ | via Docker (see below) |
| PostgreSQL | 15+ | via Docker (see below) |

---

## Local setup

```bash
# 1. Clone the repo
git clone https://github.com/YeabTesfaye/triageiq
cd triageiq

# 2. Install dependencies (creates .venv automatically)
uv sync

# 3. Copy and fill in environment variables
cp .env.example .env
# Edit .env — the minimum required fields are:
#   JWT_SECRET_KEY, DATABASE_URL, REDIS_URL, OPENAI_API_KEY

# 4. Start PostgreSQL and Redis via Docker
docker compose -f docker/docker-compose.yml up postgres redis -d

# 5. Run database migrations
uv run alembic upgrade head

# 6. Seed the superadmin (required once per fresh database)
uv run python scripts/seed_superadmin.py \
  --email admin@example.com \
  --password "StrongPass@99" \
  --name "Super Admin"
```

---

## Running the server

```bash
# Development server with auto-reload
uv run uvicorn main:app --reload

# API available at:  http://localhost:8000
# Swagger UI:        http://localhost:8000/docs
# ReDoc:             http://localhost:8000/redoc
# Prometheus:        http://localhost:8000/metrics
# Health check:      http://localhost:8000/health
# Readiness check:   http://localhost:8000/readiness
```

For the full stack (API + PostgreSQL + Redis) in Docker:

```bash
docker compose -f docker/docker-compose.yml up --build
```

---

## Running tests

The test suite uses SQLite in-memory and a real Redis instance. All 101 tests run without touching the production database or OpenAI.

```bash
# Run all tests
JWT_SECRET_KEY="testsecretkey_minimum_32_characters_req" \
DATABASE_URL="sqlite+aiosqlite:///:memory:" \
REDIS_URL="redis://localhost:6379/0" \
OPENAI_API_KEY="sk-test" \
ENV="development" \
BCRYPT_ROUNDS="4" \
uv run pytest tests/ -v

# With coverage report
uv run pytest tests/ --cov=app --cov-report=term-missing

# Run a single test file
uv run pytest tests/unit/test_auth_service.py -v

# Run a single test by name
uv run pytest tests/ -k "test_login_rate_limit" -v
```

**Notes:**
- `BCRYPT_ROUNDS=4` keeps tests fast (~5ms per hash vs ~300ms at the production cost of 12).
- `OPENAI_API_KEY=sk-test` is intentionally fake — AI calls are mocked in the test suite.
- Redis must be running locally for integration tests. Start it with `docker run -d -p 6379:6379 redis:7`.

---

## Code quality

CI runs these checks on every push. Run them locally before opening a PR to avoid round trips.

```bash
# Lint (ruff)
uv run ruff check .

# Auto-fix lint issues
uv run ruff check . --fix

# Format (black)
uv run black .

# Type check (mypy or pyright — whichever is configured in pyproject.toml)
uv run mypy app/
```

All four must pass before a PR can be merged. The CI pipeline runs them in order: lint → format check → type check → tests → Docker build.

---

## Adding a database migration

TriageIQ uses Alembic with async SQLAlchemy. Follow this workflow every time you change a model.

**Step 1 — Make your model change**

Edit the relevant entity in `app/domain/entities/`. Example: adding a `resolved_at` field to `Ticket`.

```python
# app/domain/entities/ticket.py
resolved_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

**Step 2 — Autogenerate the migration**

```bash
uv run alembic revision --autogenerate -m "add_resolved_at_to_tickets"
```

This creates a new file in `alembic/versions/`. Always open it and verify the generated `upgrade()` and `downgrade()` functions before proceeding — autogenerate is not perfect and occasionally misses index changes or column type nuances.

**Step 3 — Apply the migration**

```bash
uv run alembic upgrade head
```

**Step 4 — Verify**

```bash
# Check current migration state
uv run alembic current

# View migration history
uv run alembic history --verbose
```

**Step 5 — Commit both files**

Always commit the entity change and the migration file together in the same commit. Never commit one without the other.

```bash
git add app/domain/entities/ticket.py alembic/versions/<timestamp>_add_resolved_at_to_tickets.py
git commit -m "feat: add resolved_at field to tickets"
```

**Rolling back a migration:**

```bash
# Roll back one step
uv run alembic downgrade -1

# Roll back to a specific revision
uv run alembic downgrade <revision_id>
```

---

## Project structure

```
triageiq/
├── main.py                        # Entry point — imports app factory from app/
├── app/
│   ├── main.py                    # FastAPI app factory, middleware, lifespan
│   ├── config.py                  # Pydantic settings (all config from .env)
│   ├── dependencies.py            # get_current_user, require_roles() factory
│   ├── presentation/
│   │   ├── routers/               # HTTP route handlers — no business logic
│   │   └── schemas/               # Pydantic request/response models
│   ├── application/
│   │   └── services/              # Business logic — AuthService, TicketService, etc.
│   ├── domain/
│   │   ├── entities/              # SQLAlchemy ORM models (User, Ticket, AuditLog, …)
│   │   └── enums.py               # Role, UserStatus, TicketStatus, TicketCategory, …
│   ├── infrastructure/
│   │   ├── database.py            # Async engine + session factory
│   │   ├── db_types.py            # CompatibleJSONB (JSONB on PG, JSON on SQLite)
│   │   ├── redis_client.py        # Token blacklist, cutoff timestamps, rate limiting
│   │   ├── ai/openai_client.py    # OpenAI async client with retry + degraded mode
│   │   └── security/              # JWT handler, password handler
│   └── repositories/              # All database access — one class per entity
├── alembic/                       # Async Alembic migrations
├── tests/
│   ├── unit/                      # Pure logic tests — no DB, no network
│   └── integration/               # Full HTTP → DB tests — SQLite in-memory
├── docker/
│   ├── Dockerfile                 # Multi-stage, non-root appuser
│   └── docker-compose.yml         # api + postgres + redis
├── scripts/
│   └── seed_superadmin.py         # One-time superadmin creation
└── .github/workflows/ci.yml       # lint → type-check → tests → Docker build
```

---

## Architecture rules

TriageIQ enforces Clean Architecture. These rules are not style preferences — violations break the testability and maintainability guarantees the structure provides. Reviewers will reject PRs that break them.

**Layer dependencies flow one way only: Presentation → Application → Domain → Infrastructure.**

| Rule | Why |
|---|---|
| No DB calls in services — only through repositories | Services must be testable without a database |
| No business logic in routers — only in services | Routers are presentation; logic belongs in the application layer |
| No external API calls outside `infrastructure/` | All I/O is isolated and mockable in one place |
| No circular dependencies | A → B → A breaks the dependency graph and causes import errors |
| No hardcoded secrets — all config from `.env` via `pydantic-settings` | Secrets in code get committed; env vars do not |
| RBAC enforced via `Depends(require_roles(...))` only — never inline | Role checks inline in handlers are invisible to reviewers and easy to forget |

When adding a new feature, ask: which layer does this belong in? If it touches the database, it goes in a repository. If it contains a business rule, it goes in a service. If it speaks HTTP, it goes in a router.

---

## Branching strategy

```
main                    ← always deployable; protected branch
└── feature/<name>      ← all new work
└── fix/<name>          ← bug fixes
└── chore/<name>        ← non-functional changes (docs, deps, config)
```

**Rules:**
- `main` is protected — no direct pushes. All changes via pull request.
- Branch off `main`, not off another feature branch.
- Keep branches short-lived — ideally one logical change per branch.
- Rebase onto `main` before opening a PR to avoid merge conflicts in CI.

**Branch naming examples:**

```bash
git checkout -b feature/webhook-notifications
git checkout -b fix/refresh-token-timezone
git checkout -b chore/update-dependencies
```

---

## Pull request checklist

Before marking a PR ready for review, confirm each item:

```
[ ] All CI checks pass (lint, type check, tests, Docker build)
[ ] New code has tests — unit tests for logic, integration tests for new endpoints
[ ] No business logic added to routers
[ ] No DB calls added to services
[ ] Any new config values added to .env.example with a comment
[ ] Any new migration committed alongside the model change
[ ] Structlog used for logging (no print() or stdlib logging)
[ ] No PII (emails, names) in log lines — use user_id (UUID) only
[ ] PR description explains what changed and why, not just what
```

**Commit message format:**

```
<type>: <short description>

Types: feat | fix | chore | docs | test | refactor

Examples:
feat: add webhook delivery on ticket status change
fix: handle timezone-naive datetime from SQLite in refresh token
chore: upgrade aiosmtplib to 3.1
docs: add DECISIONS.md
test: cover degraded AI mode in ticket creation
```

---

## Environment variables reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `JWT_SECRET_KEY` | yes | — | Min 32 chars. Used to sign all JWTs. |
| `DATABASE_URL` | yes | — | Async SQLAlchemy URL. `postgresql+asyncpg://...` for production. |
| `REDIS_URL` | yes | — | `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | yes | — | Used for AI triage. Set to any string in tests. |
| `ENV` | no | `production` | Set to `development` to enable debug logging. |
| `BCRYPT_ROUNDS` | no | `12` | Cost factor. Use `4` in tests for speed. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `15` | Access token lifetime. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | no | `7` | Refresh token lifetime. |
| `AUTH_RATE_LIMIT_PER_15_MIN` | no | `5` | Failed login attempts per IP per 15 minutes. |
| `MAX_FAILED_LOGIN_ATTEMPTS` | no | `5` | Failed attempts before account lockout. |
| `ACCOUNT_LOCK_MINUTES` | no | `30` | Duration of account lockout. |
| `OPENAI_MODEL` | no | `gpt-4o-mini` | Model used for ticket triage. |
| `EMAIL_ENABLED` | no | `false` | Set to `true` to enable SMTP email sending. |
| `SMTP_HOST` | no | `smtp.gmail.com` | SMTP server hostname. |
| `SMTP_PORT` | no | `587` | SMTP server port. |
| `SMTP_USER` | no | — | SMTP authentication username. |
| `SMTP_PASSWORD` | no | — | SMTP authentication password or app password. |
| `SMTP_FROM_EMAIL` | no | — | From address on outgoing emails. |
| `SMTP_FROM_NAME` | no | `TriageIQ Support` | Display name on outgoing emails. |