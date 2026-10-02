# EVE Healthcare Backend Assignment Plan

## Summary
Build a small backend service for diagnostic test bookings and simulated payments. The goal is to evaluate ability to design clean APIs, model data correctly, handle real-world edge cases, and write maintainable code.

## Stack
FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL (via docker-compose), pytest, pydantic-settings. Python 3.11+.

## Structure
app/ main.py, config.py, database.py, security.py, dependencies.py, models/, schemas/, routers/ (auth, centres, bookings, payments), services/ (booking_service, payment_service), tests/. Plus alembic/, Dockerfile, docker-compose.yml, README.md, requirements.txt, .env.example.

Layers: routers handle HTTP only, services hold business rules. No repository layer.

## Data Model
- users (is_admin flag)
- centres
- tests (catalogue)
- centre_tests (centre_id, test_id, price; unique on the pair)
- bookings (user, centre_test, appointment_at, amount, status)
- payments (booking_id, amount, status, provider_ref)
- webhook_events (event_id UNIQUE, payload, processed_at)

Notes:
- Money is Numeric(10,2), never float.
- bookings.amount is a snapshot of the price at booking time.
- Partial unique index: only one SUCCESS payment per booking.
- Index foreign keys and bookings(user_id, created_at).

## Payment Design
- One function apply_payment_result(payment, status) shared by POST /payments/ and POST /payments/webhook/.
- Booking states: PENDING, CONFIRMED, FAILED, CANCELLED.
  Transitions: PENDING -> CONFIRMED, FAILED, CANCELLED; FAILED -> CONFIRMED, CANCELLED; CONFIRMED -> CANCELLED; CANCELLED -> terminal. Any other transition is rejected (e.g., CONFIRMED -> FAILED).
- Webhook flow in one transaction: verify HMAC signature -> insert event_id (unique constraint; on conflict return 200 already_processed) -> SELECT ... FOR UPDATE on the payment -> apply result -> commit.
- POST /payments/ accepts optional simulate: success|failed (random if omitted, deterministic in tests).
- Accessing another user's booking returns 404, not 403.

## Phases
0. skeleton
1. auth + tests
2. centres catalogue
3. bookings + state machine
4. payments + webhook + idempotency tests
5. logging, pagination, Dockerfile
6. README.
