# EVE Healthcare API

FastAPI backend for diagnostic centre discovery, test bookings, simulated payments, and signed payment webhooks.

## Run locally

Requires Python 3.12+, PostgreSQL, and (optionally) Redis. Copy `.env.example` to `.env` and configure `DATABASE_URL`, `JWT_SECRET_KEY`, and `WEBHOOK_SIGNING_SECRET`.

```sh
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Swagger UI is available at `http://localhost:8000/docs`; the OpenAPI schema is at `/openapi.json`. `/health` is a process health check. Docker Compose starts the API and Redis; PostgreSQL is external and must be configured in `.env`.

## API overview

| Method and path | Access | Description |
|---|---|---|
| `POST /auth/signup`, `POST /auth/login` | Public | Register and obtain a JWT |
| `POST /centres/`, `POST /centres/{centre_id}/tests/` | JWT | Create centres and tests |
| `GET /centres/`, `GET /centres/{centre_id}` | Public | Paginated centre list; detail includes tests |
| `GET /tests/`, `GET /tests/{test_id}` | Public | Paginated tests, optional `centre_id` filter |
| `POST /bookings/`, `GET /bookings/`, `GET /bookings/{booking_id}` | JWT | Create and view owned bookings |
| `POST /payments/` | JWT | Create one simulated payment per booking |
| `POST /payments/webhook/` | HMAC signature | Apply a provider payment event idempotently |
| `POST /payments/webhook/retry/{payment_id}` | Shared-secret header | Record bounded retry metadata and safely redeliver the last event |

Authenticated requests use `Authorization: Bearer <token>`. List endpoints accept `page` (default `1`) and `limit` (default `20`, maximum `100`; larger values are clamped). Responses include `items`, `page`, `limit`, and `total`. Errors use an `error` object with a code and message.

## Example flow

Create an account and use its token for centre, test, booking, and payment requests:

```sh
curl -X POST http://localhost:8000/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"patient@example.com","password":"long-password-123"}'

curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"patient@example.com","password":"long-password-123"}'

curl -X POST http://localhost:8000/centres/ \
  -H 'Authorization: Bearer <access-token>' -H 'Content-Type: application/json' \
  -d '{"name":"Central Lab","location":"Downtown"}'

curl -X POST http://localhost:8000/centres/<centre-id>/tests/ \
  -H 'Authorization: Bearer <access-token>' -H 'Content-Type: application/json' \
  -d '{"name":"CBC","price":"15.50"}'

curl -X POST http://localhost:8000/bookings/ \
  -H 'Authorization: Bearer <access-token>' -H 'Content-Type: application/json' \
  -d '{"centre_id":"<centre-id>","test_id":"<test-id>","appointment_time":"2030-01-01T10:00:00Z"}'

curl -X POST http://localhost:8000/payments/ \
  -H 'Authorization: Bearer <access-token>' -H 'Content-Type: application/json' \
  -d '{"booking_id":"<booking-id>"}'
```

The payment attempt returns `SUCCESS` or `FAILED` at random. `201 Created` means the attempt was created; the `status` field is the simulated outcome. The booking becomes `CONFIRMED` or `FAILED` to match it. A booking accepts only one payment attempt.

## Webhook signing

Sign the exact request body with HMAC-SHA256 using `WEBHOOK_SIGNING_SECRET`; send the lowercase hex digest in `X-Webhook-Signature`.

```sh
body='{"provider_event_id":"evt-1","payment_id":"<payment-id>","status":"SUCCESS"}'
signature=$(printf '%s' "$body" | openssl dgst -sha256 -hmac "$WEBHOOK_SIGNING_SECRET" | awk '{print $NF}')
curl -X POST http://localhost:8000/payments/webhook/ \
  -H "X-Webhook-Signature: $signature" -H 'Content-Type: application/json' -d "$body"
```

Each accepted provider event ID is stored in a unique event ledger in the same transaction as payment and booking updates. Replays return `already_processed`; reuse of an event ID with a different payment or result returns `409` without changing payment state.

## Data model and assumptions

- `users` stores normalized unique email addresses and Argon2 password hashes.
- `diagnostic_centres` owns `diagnostic_tests`; each test has a positive decimal price.
- `bookings` links a user, test, and centre; it snapshots the test price and starts `PENDING`.
- `payments` links one payment attempt to a booking and stores its amount and outcome.
- `payment_webhook_events` stores unique provider event IDs so replay detection survives process restarts and multiple API instances.

Centre and test creation is available to any authenticated user because the assignment does not define admin roles. Centre and test reads are public. Booking states move from `PENDING` to `CONFIRMED`, `FAILED`, or `CANCELLED`; settled states are terminal. PostgreSQL migrations are managed by Alembic.

## Tests and next improvements

Run tests with:

```sh
uv run pytest
```

Integration tests use an isolated SQLite database; PostgreSQL is the deployment database. The current suite covers authentication, catalog validation and pagination, booking ownership and validation, both payment outcomes, webhook signatures/replays/conflicts, and retry metadata.

With more time, I would add PostgreSQL-backed concurrency tests, automated transient webhook retry delivery with a durable worker, rate-limit integration tests, and deployment monitoring. Redis is used for fixed-window rate limiting; the API continues in development if Redis is unavailable. Structured request logs include request ID, authenticated user ID when available, method, path, status, and duration. Secrets in `.env.example` are placeholders only.
