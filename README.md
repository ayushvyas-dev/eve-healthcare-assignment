# EVE Healthcare API

This API lets patients browse diagnostic centres and tests, book an appointment, and follow a simulated payment through to a booking status. It is a small FastAPI service built for the EVE Healthcare backend assignment.

## What it does

- Registers users and issues short-lived JWT access tokens on login. Passwords are stored as Argon2 hashes.
- Lets authenticated users create diagnostic centres and tests. Reads from the catalog are public.
- Creates bookings for future appointments and stores the test price on the booking, so a later catalog price change does not alter it.
- Allows a patient to see only their own bookings and make one simulated payment attempt per booking.
- Accepts signed payment webhooks and records provider event IDs so repeated deliveries are safe to handle.
- Paginates centre, test, and booking lists; applies Redis-backed fixed-window limits to login, payments, and webhooks.
- Adds request IDs and structured request logs, migrations, Docker support, and an OpenAPI interface.

Payment attempts are deliberately simulated: the service chooses `SUCCESS` or `FAILED` at random. The endpoint can return `201 Created` for either outcome; check the returned `status` to see what happened. A successful attempt confirms the booking, while a failed one marks it failed.

## Architecture

The project is a modular monolith: one deployable FastAPI application with code grouped by responsibility. Routes handle HTTP details and call service functions. Services apply business rules and own database queries and transactions. Pydantic schemas validate request and response data, while SQLAlchemy models describe persisted data.

```text
Client
  → FastAPI route and Pydantic validation
  → shared dependencies (JWT authentication or rate limiting, where required)
  → service logic and transaction
  → async SQLAlchemy session
  → PostgreSQL
```

The webhook route uses an HMAC signature instead of a patient JWT. Its event ledger and payment/booking changes are stored in PostgreSQL, which is the source of truth. Redis is used for rate-limit counters; it is not a store for booking or payment data. Retry handling records bounded retry metadata and reprocesses the last event when explicitly called. There is no background worker delivering retries automatically.

### Request flow

For a protected booking request, FastAPI parses and validates the body, the JWT dependency identifies the caller, and the booking service verifies the centre/test relationship and appointment time. It snapshots the price, creates a `PENDING` booking, and commits the transaction. The response schema serializes the booking.

For a payment webhook, the API validates the body and HMAC over the exact raw request bytes. The payment service checks the event ID, locks the payment and booking rows, applies a valid state change, and writes the event ledger entry in the same transaction. Replaying the same event returns `already_processed`; reusing its ID for a different result returns `409`.

### Data model

- `users`: normalized unique email and password hash.
- `diagnostic_centres` and `diagnostic_tests`: tests belong to centres and have positive decimal prices.
- `bookings`: links a user, test, and centre; includes the appointment time, price snapshot, and status.
- `payments`: one payment attempt per booking, with amount, outcome, and retry metadata.
- `payment_webhook_events`: unique provider event IDs linked to payments for durable replay detection.

Bookings start as `PENDING` and can move to `CONFIRMED`, `FAILED`, or `CANCELLED`. A settled state is terminal. A booking can be paid only once. PostgreSQL schema changes are managed with Alembic.

### Tradeoffs and assumptions

- **No admin roles:** the assignment does not define roles, so any authenticated user can create a centre or test. Catalog reads remain public.
- **One simulated payment attempt:** this keeps the assignment flow explicit and makes duplicate payment submissions a `409`. Real payment systems generally need provider-specific attempts and reconciliation.
- **PostgreSQL event ledger:** webhook idempotency must survive process restarts and work across app instances, so event IDs live in the same database transaction as the state change rather than only in Redis.
- **Manual retry endpoint:** retry count and exponential backoff metadata are implemented without adding Celery or another worker system. A production service would schedule delivery in a durable job queue.
- **PostgreSQL is external to Compose:** Docker Compose starts the API and Redis; the database URL must point to a configured PostgreSQL instance. This matches the hosted PostgreSQL setup used by the project.
- **Redis is optional for local development:** if the rate-limit store is unavailable, the current implementation allows the request through. Production deployments should monitor Redis availability and choose a deliberate fail-open/fail-closed policy.

## Tech stack

| Area | Technology | Use |
|---|---|---|
| Runtime and API | Python 3.12+, FastAPI, Uvicorn | Async HTTP API and OpenAPI docs |
| Validation/configuration | Pydantic v2, pydantic-settings | Request/response schemas and environment settings |
| Persistence | SQLAlchemy 2 async, PostgreSQL, asyncpg | ORM, async sessions, relational data |
| Schema changes | Alembic | Versioned database migrations |
| Authentication | PyJWT, pwdlib with Argon2 | JWT access tokens and password hashing |
| Rate limiting | Redis | Shared fixed-window counters |
| Logging | structlog | Structured application/request logs |
| Tests | pytest, pytest-asyncio, HTTPX, aiosqlite | Unit tests and async API integration tests |
| Containers | Docker, Docker Compose | App and Redis development services |

## Project layout

```text
app/
├── core/            # settings, security helpers, logging setup
├── db/              # SQLAlchemy base, engine, and session dependency
├── dependencies/    # JWT authentication and rate limiting
├── middleware/      # request ID and request logging
├── models/          # SQLAlchemy entities
├── routes/          # HTTP endpoints
├── schemas/         # Pydantic request and response contracts
├── services/        # catalog, auth, booking, payment, and retry logic
└── main.py          # app setup, router registration, error handlers
alembic/             # migration environment and versioned migrations
tests/
├── unit/            # state machine, idempotency, and rate-limit tests
└── integration/     # auth, catalog, booking, payment, webhook API tests
Dockerfile
docker-compose.yml
pyproject.toml
uv.lock
architecture.md
```

## API

Interactive API documentation is available at `/docs`; the OpenAPI document is `/openapi.json`. Protected endpoints require `Authorization: Bearer <access-token>`. Catalog reads, signup, login, health, and the signed webhook are public in the JWT sense. UUIDs and timestamps below are representative.

List endpoints use `page` (default `1`) and `limit` (default `20`, minimum `1`, values above `100` are clamped). Their response is `{ "items": [...], "page": 1, "limit": 20, "total": 0 }`.

Errors have the shape `{"error":{"code":"...","message":"..."}}`. Validation failures use HTTP `422` and include a `details` array. Missing/invalid JWTs are rejected with `401`; ownership violations return `403`.

### Authentication

`POST /auth/signup` — public, returns `201`.

Request:

```json
{"email":"patient@example.com","password":"long-password-123"}
```

Response:

```json
{"id":"<user-uuid>","email":"patient@example.com","created_at":"2030-01-01T09:00:00Z"}
```

Email must be valid and the password must be 8–128 characters. A duplicate email returns `409`.

`POST /auth/login` — public, returns `200`.

Request is the same as signup. Response:

```json
{"access_token":"<jwt>","token_type":"bearer"}
```

Invalid credentials return `401`. Login is limited to five requests per fixed window when Redis is available.

### Diagnostic centres and tests

`POST /centres/` — JWT required, returns `201`.

```json
{"name":"Central Lab","location":"Downtown"}
```

Response: `{"id":"<centre-uuid>","name":"Central Lab","location":"Downtown","created_at":"2030-01-01T09:00:00Z"}`.

`GET /centres/?page=1&limit=20` — public, returns the paginated centre shape; each item has `id`, `name`, `location`, and `created_at`.

`GET /centres/{centre_id}` — public, returns one centre with a `tests` array. Each test contains `id`, `centre_id`, `name`, `price`, and `created_at`. Unknown IDs return `404`.

`POST /centres/{centre_id}/tests/` — JWT required, returns `201`.

```json
{"name":"Complete Blood Count","price":"15.50"}
```

Response: `{"id":"<test-uuid>","centre_id":"<centre-uuid>","name":"Complete Blood Count","price":"15.50","created_at":"2030-01-01T09:00:00Z"}`. Price must be greater than zero and have at most two decimal places. A missing centre returns `404`.

`GET /tests/?page=1&limit=20&centre_id=<centre-uuid>` — public, paginated; `centre_id` is optional. Items have the `TestOut` shape above.

`GET /tests/{test_id}` — public, returns one test in the same shape; unknown IDs return `404`.

### Bookings

`POST /bookings/` — JWT required, returns `201`.

```json
{
  "test_id":"<test-uuid>",
  "centre_id":"<centre-uuid>",
  "appointment_time":"2030-01-01T10:00:00Z"
}
```

Response:

```json
{
  "id":"<booking-uuid>",
  "user_id":"<user-uuid>",
  "test_id":"<test-uuid>",
  "centre_id":"<centre-uuid>",
  "appointment_time":"2030-01-01T10:00:00Z",
  "amount":"15.50",
  "status":"PENDING",
  "created_at":"2030-01-01T09:00:00Z",
  "updated_at":"2030-01-01T09:00:00Z"
}
```

The appointment must be in the future and the selected test must belong to the supplied centre. Invalid catalog references return `404`; inconsistent or past appointments return `400`.

`GET /bookings/?page=1&limit=20` — JWT required; returns only the caller’s bookings in the paginated shape.

`GET /bookings/{booking_id}` — JWT required; returns the booking shape above. Unknown bookings return `404`; another user’s booking returns `403`.

### Payments and webhook

`POST /payments/` — JWT required; caller must own the booking. Returns `201` for either simulated outcome.

```json
{"booking_id":"<booking-uuid>"}
```

Response:

```json
{"id":"<payment-uuid>","booking_id":"<booking-uuid>","status":"FAILED","amount":"15.50"}
```

`status` is `SUCCESS` or `FAILED`; it determines whether the booking becomes `CONFIRMED` or `FAILED`. A missing booking returns `404`, a different owner gets `403`, and an already settled or already-paid booking returns `409`. Payment creation is limited to ten requests per fixed window per user when Redis is available.

`POST /payments/webhook/` — provider-facing endpoint; requires `X-Webhook-Signature`. The value is the lowercase hex HMAC-SHA256 digest of the exact raw JSON request body, using `WEBHOOK_SIGNING_SECRET`.

```json
{"provider_event_id":"evt-123","payment_id":"<payment-uuid>","status":"SUCCESS"}
```

First accepted delivery returns `{"status":"processed"}`. An identical replay returns `{"status":"already_processed"}`. Invalid signatures return `400`, unknown payments return `404`, and conflicting event IDs or final outcomes return `409`. Only `SUCCESS` and `FAILED` are accepted.

`POST /payments/webhook/retry/{payment_id}` — internal/manual operation; send `X-Webhook-Signature` with the exact configured `WEBHOOK_SIGNING_SECRET` value. It records the next bounded retry and reprocesses the last stored event. Response:

```json
{"payment_id":"<payment-uuid>","retry_count":1,"next_retry_at":"2030-01-01T09:00:02Z"}
```

Unknown payments return `404`; payments without a recorded provider event or at the retry limit return `409`.

### Operations

`GET /health` returns `{"status":"ok"}`. It is a simple process health check and does not verify database or Redis connectivity.

## Local setup

You’ll need Python 3.12+, `uv`, and a PostgreSQL database. Redis is needed for rate limiting but can be absent during local development; in that case rate limiting fails open. The repository’s Compose file starts the API and Redis, but expects PostgreSQL to be supplied separately.

1. Copy `.env.example` to `.env` and set `DATABASE_URL` to a reachable PostgreSQL database. Set `JWT_SECRET_KEY` and `WEBHOOK_SIGNING_SECRET` to local random values; retain the async PostgreSQL URL format, for example `postgresql+asyncpg://user:password@localhost/eve_healthcare`.
2. Install the project and test extras, then apply migrations:

```sh
uv sync --extra dev
uv run alembic upgrade head
```

3. Start the API:

```sh
uv run uvicorn app.main:app --reload
```

The API listens at `http://localhost:8000`. Open `http://localhost:8000/docs` to try the routes. If using Compose, create `.env` first; point `DATABASE_URL` at a PostgreSQL service reachable from the container.

## Tests

Run the full suite:

```sh
uv run pytest
```

The integration suite overrides the app database with an isolated SQLite database via `aiosqlite`; you do not need PostgreSQL to run the tests. The tests cover auth, catalog, booking ownership and validation, payment outcomes, webhook signatures/replays/conflicts, retry behavior, and unit-level state/idempotency/rate-limit logic.

To run one area, for example:

```sh
uv run pytest tests/unit
uv run pytest tests/integration/test_payments.py
```
