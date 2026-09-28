# EVE Healthcare API

FastAPI service for diagnostic centre discovery, bookings, simulated payments, and payment webhooks. Centre and test creation is available to any authenticated user because the assignment does not define admin roles.

## Run locally

Requires Python 3.12+, PostgreSQL (Neon is supported), and Redis. Copy `.env.example` to `.env`, set credentials, then:

```sh
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

Swagger is at `/docs`, OpenAPI at `/openapi.json`, and `/health` provides a process health check. Docker Compose runs the API and Redis; PostgreSQL remains external. Run `docker compose up --build` after configuring `.env`.

## API overview

| Method and path | Access | Description |
|---|---|---|
| `POST /auth/signup`, `POST /auth/login` | Public | Register and obtain a JWT |
| `POST /centres/`, `POST /centres/{id}/tests/` | JWT | Create centre and offered tests |
| `GET /centres/`, `GET /centres/{id}` | Public | Paginated centres; detail includes tests |
| `GET /tests/`, `GET /tests/{id}` | Public | Paginated tests, optional `centre_id` filter |
| `POST /bookings/`, `GET /bookings/`, `GET /bookings/{id}` | JWT | Create and view owned bookings |
| `POST /payments/` | JWT | Simulate one payment attempt per booking |
| `POST /payments/webhook/` | HMAC signature | Idempotently apply provider result |
| `POST /payments/webhook/retry/{payment_id}` | Shared-secret header | Record bounded retry metadata |

Paginated responses contain `items`, `page`, `limit`, and `total`; limits are 1–100. Errors use `{"error":{"code":"...","message":"..."}}`. Authenticated routes use `Authorization: Bearer <token>`.

## Webhook signing

Set `X-Webhook-Signature` to the lowercase hex HMAC-SHA256 of the exact UTF-8 request body using `WEBHOOK_SIGNING_SECRET`. For example:

```sh
printf '%s' '{"provider_event_id":"evt-1","payment_id":"<payment-uuid>","status":"SUCCESS"}' | openssl dgst -sha256 -hmac "$WEBHOOK_SIGNING_SECRET"
```

Events identify a payment row and may carry `SUCCESS` or `FAILED`. A unique database constraint on `provider_event_id` makes replays safe across service instances. Payment and booking changes commit together.

## Data model and operations

PostgreSQL stores users, diagnostic centres/tests, bookings, and payments. Booking amounts snapshot the test price at creation. Booking state transitions are `PENDING` to `CONFIRMED`, `FAILED`, or `CANCELLED`; settled states are terminal. Schema changes are managed with Alembic (`alembic upgrade head`).

Redis fixed-window counters protect login, payment, and webhook endpoints. The API continues if Redis is unavailable for local development. Structured JSON request logs include request ID, method, path, status, and duration. Never use the development secrets in production.

Run tests with `pytest` (integration fixtures use isolated SQLite databases; PostgreSQL is the deployment database). Unit tests cover the state machine and retry backoff, while HTTP integration tests cover auth, booking, payment, and webhook behavior.
