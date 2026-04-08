# Architecture Decision Records — TriageIQ

Key decisions made during the design and implementation of TriageIQ, with the reasoning behind each. These are not post-hoc justifications — they reflect real tradeoffs considered during development.

---

## 1. Clean Architecture over flat structure

**Decision:** Strict four-layer separation — Presentation → Application → Domain → Infrastructure — with repositories as the only path to the database.

**Why:** Flat FastAPI projects (routers that call `db.query(...)` directly) are fast to start and painful to maintain. Business logic leaks into route handlers, tests require a real database, and adding a second data source (Redis, an external API) means touching every file that ever queried the first one.

Clean Architecture keeps the pain surface small: if OpenAI changes their API, only `infrastructure/ai/openai_client.py` changes. If we swap PostgreSQL for a different database, only the repositories change. Services stay untouched.

**Rules enforced:**
- No DB calls in services — only through repositories
- No business logic in routers — only in services
- No external API calls outside the infrastructure layer
- No circular dependencies

**Tradeoff:** More files and more indirection than a flat structure. For a project this size, that cost is real. It's worth it because the test suite proves it: unit tests run against pure Python with no database or network, and integration tests use SQLite in-memory. Neither category touches the real infrastructure.

---

## 2. JWT access tokens + hashed refresh tokens, not sessions

**Decision:** Stateless JWT access tokens (15-minute TTL) paired with SHA-256-hashed, single-use refresh tokens stored in PostgreSQL.

**Why:** Sessions require sticky routing or a shared session store — fine for monoliths, awkward when you add workers or scale horizontally. JWTs are stateless by nature and work across any number of instances without coordination.

Refresh tokens are stored as SHA-256 hashes, never as raw values. If the `refresh_tokens` table is compromised, the attacker gets hashes they cannot use — the raw token only ever exists in transit.

**Why not short-lived tokens only (no refresh)?** A 15-minute access token with no refresh mechanism means users re-authenticate every 15 minutes. A 7-day access token with no rotation is a credential that stays valid for a week after logout. Refresh token rotation gives us both: short-lived access tokens and a long-lived session that can be cleanly revoked.

**Single-use enforcement:** Every `POST /auth/refresh` call immediately revokes the old refresh token and issues a new pair. Reusing a refresh token returns 401. This prevents replay attacks — a stolen token is usable at most once before it's invalidated by the legitimate client.

---

## 3. Redis JTI blacklist for access token revocation

**Decision:** On logout, the access token's `jti` (JWT ID) is written to Redis with a TTL equal to the token's remaining lifetime.

**Why:** JWTs are stateless — there is no built-in revocation mechanism. The naive solution (check every token against a DB blocklist) adds a database round-trip to every authenticated request. Redis is orders of magnitude faster for this pattern: a single `GET jti:<id>` with sub-millisecond latency.

The TTL matches the token's remaining lifetime precisely, so the Redis key self-expires when the token would have expired anyway. No cleanup job needed.

**Why not just use short-lived tokens and skip revocation?** Logout would be a lie. The client discards the token, but anyone who intercepted it retains a valid credential until expiry. For a support ticketing system with RBAC and audit logs, that's an unacceptable gap.

**Suspended/banned users:** Redis also stores a per-user cutoff timestamp (`user_cutoff:<id>`). Any access token issued before that timestamp is rejected, even if its JTI is not in the blacklist. This covers the case where an admin suspends a user with multiple active sessions — all are invalidated immediately without needing to enumerate every active JTI.

---

## 4. Timing-safe authentication to prevent user enumeration

**Decision:** On login, always run `bcrypt.verify()` even when the email does not exist in the database.

**Why:** A naive implementation returns "user not found" instantly and "wrong password" after a slow bcrypt comparison. This timing difference is measurable and lets an attacker enumerate valid email addresses.

The implementation always hashes — using a dummy hash for missing users — before returning a response. Both code paths take the same time. The response is always "Invalid email or password" regardless of which check failed.

---

## 5. Bcrypt with cost factor 12

**Decision:** Passwords are hashed with bcrypt at cost factor 12 (configurable via `BCRYPT_ROUNDS` env var).

**Why:** Cost factor 12 targets ~300ms on commodity hardware. This is slow enough to make offline brute-force attacks expensive and fast enough that legitimate login latency is acceptable.

The cost factor is configurable specifically for tests: `BCRYPT_ROUNDS=4` in the test environment reduces per-test overhead from ~300ms to ~5ms, which is the difference between a 30-second and a 3-minute test suite.

---

## 6. Async SQLAlchemy with asyncpg

**Decision:** `sqlalchemy[asyncio]` with `asyncpg` as the PostgreSQL driver.

**Why:** FastAPI is async-native. A synchronous database driver (psycopg2) blocks the event loop during every query, negating the concurrency benefits of async. `asyncpg` is the fastest async PostgreSQL driver available for Python — significantly faster than the async wrapper around psycopg2.

**SQLite in tests:** The test suite uses `aiosqlite` with SQLite in-memory. This is possible because the repository layer abstracts all SQL — tests exercise real query logic without a running PostgreSQL instance. `CompatibleJSONB` in `db_types.py` handles the one dialect difference (JSONB on PostgreSQL, JSON on SQLite).

---

## 7. AI triage in the request path, with graceful degradation

**Decision:** OpenAI is called synchronously during `POST /tickets`, with a 15-second timeout, 2 retries with exponential backoff, and a defined degraded mode.

**Why not background tasks?** Background processing (Celery, asyncio tasks) requires the client to poll for results or accept an incomplete response. For this use case, the AI response is the primary value of the endpoint — returning a ticket with no classification and making the user check back is a worse user experience than a slightly slower response.

**Degraded mode:** If OpenAI is unavailable after retries, the ticket is saved with `category=null`, `priority=null`, and `ai_response=null`. The router returns HTTP 503 with a structured error body containing the ticket ID. The ticket exists and can be re-triaged later. The system never loses data due to AI unavailability.

---

## 8. Soft delete for users, hard delete for tickets

**Decision:** Users are soft-deleted (a `deleted_at` timestamp is set). Tickets are hard-deleted.

**Why soft delete for users?** Users are referenced by tickets, audit logs, and refresh tokens. Deleting a user row would cascade in unpredictable ways or require `ON DELETE SET NULL` on every foreign key. Soft delete preserves referential integrity while making the account inaccessible. Audit logs retain a masked snapshot of the user's state at deletion time.

**Why hard delete for tickets?** Tickets contain user-submitted content. When an admin deletes a ticket, the intent is permanent removal. Tickets do not carry the same referential weight as users — they are not referenced by other entities in a way that requires preservation.

---

## 9. SUPERADMIN cannot be created via API

**Decision:** The `SUPERADMIN` role cannot be assigned through any API endpoint. It is only created via the `scripts/seed_superadmin.py` script with direct database access.

**Why:** Any endpoint that can promote a user to SUPERADMIN is a critical privilege escalation target. Removing the API surface entirely eliminates the attack vector. There is no authorization check sophisticated enough to be safer than no endpoint at all.

The seed script requires server access to run, which means it requires infrastructure-level access — the correct bar for creating a superadmin account.

---

## 10. Structured logging with structlog

**Decision:** All logging uses `structlog` with JSON output, and every log line includes a `request_id`.

**Why:** Plain-text logs are difficult to query at scale. Structured JSON logs can be indexed by any field — filter by `user_id`, `ticket_id`, or `action` without grep. Every request generates a `X-Request-ID` header (auto-generated if the client does not provide one) and this ID is bound to the logger for the duration of the request, so every log line from a single request is trivially correlated.

**PII policy:** User emails are never logged. `user_id` (a UUID) is used as the identifier in all log lines. Audit log snapshots mask emails to the last 6 characters.

---

## 11. uv over pip / poetry

**Decision:** `uv` is used for dependency management and script running.

**Why:** `uv` resolves and installs dependencies an order of magnitude faster than pip or poetry. It produces a lockfile (`uv.lock`) for reproducible installs and integrates cleanly with `pyproject.toml`. For a project with a CI pipeline that installs dependencies on every run, the difference between a 45-second install and a 4-second install compounds quickly.