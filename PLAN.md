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
MODELS
- Payment: id, booking_id FK (indexed), amount Numeric(10,2), status (Python Enum PENDING|SUCCESS|FAILED with a CheckConstraint), provider_ref (String, unique, generated as "pay_" + uuid4 hex), created_at, updated_at.
- Partial unique index on payments(booking_id) WHERE status = 'SUCCESS': at most one successful payment per booking, enforced by the database.
- WebhookEvent: id, event_id (String, UNIQUE, not null), provider_ref, payload (JSONB), received_at.
- Generate the migration, READ it, upgrade head, and `alembic check` must report no differences.
PAYMENT RULES (app/services/payment_service.py)
- Payment status: PENDING -> SUCCESS | FAILED; SUCCESS and FAILED are terminal.
- ONE function apply_payment_result(db, payment, new_status) is the only code that changes payment.status or changes a booking because of a payment. Both endpoints call it. Rules:
  * payment already has new_status -> no-op, return "unchanged".
  * payment is terminal with a different status -> do nothing, log a warning, return "ignored".
  * payment is PENDING -> set the status, then the booking:
      SUCCESS: booking PENDING or FAILED -> change_status(CONFIRMED); booking CONFIRMED -> nothing; booking CANCELLED -> payment is recorded SUCCESS but the booking stays CANCELLED, and log a warning "paid_after_cancel, refund needed".
      FAILED: booking PENDING -> change_status(FAILED); any other booking status -> leave it.
  * Check the booking's current status BEFORE calling change_status, so these cases are quiet no-ops and never raise a 409.
- Lock order everywhere: booking row first (SELECT ... FOR UPDATE), then payment row. A consistent order avoids deadlocks.
POST /payments/ (JWT required; path exactly /payments/)
- Body: booking_id, optional simulate = "success" | "failed" | "pending" (random choice of success/failed when omitted).
- amount always comes from booking.amount, never from the client; ignore any amount in the body.
- Booking missing or owned by someone else -> 404. Lock the booking. Booking CONFIRMED or CANCELLED -> 409. Booking already has a PENDING payment -> 409.
- Otherwise create the payment; unless simulate is "pending", call apply_payment_result immediately. Return 201 with the payment and the booking's resulting status.
POST /payments/webhook/ (no JWT; HMAC instead)
- Header X-Signature = hex HMAC-SHA256 of the RAW request body using WEBHOOK_SECRET (add to config and .env.example with a fake value). Verify with hmac.compare_digest BEFORE parsing the JSON. Missing or wrong signature -> 401.
- Body: event_id (non-empty), provider_ref, status = SUCCESS | FAILED. Invalid -> 422.
- Flow, all in ONE transaction:
  1. Find the payment by provider_ref; unknown -> 404 (nothing is stored, so a provider retry works once the payment exists).
  2. Lock the booking, then the payment (FOR UPDATE).
  3. INSERT the event with postgresql insert(...).on_conflict_do_nothing(index_elements=["event_id"]). If rowcount is 0, return 200 {"status": "already_processed"}. Do not rely on catching IntegrityError here.
  4. Call apply_payment_result, commit, return 200 {"status": "processed"} (or "ignored").
- If anything fails, the whole transaction rolls back including the event row, so the provider's retry is processed again. Put a short comment explaining why this must stay one transaction.
- Add logger.info lines (key=value style) for: payment created, result applied, duplicate event, conflicting event ignored.
TESTS (app/tests/test_payments.py)
- Payments: success confirms the booking and amount equals booking amount; failed sets the booking FAILED; a successful retry after a failure gives CONFIRMED; paying for a CONFIRMED or CANCELLED booking -> 409; another user's booking -> 404; unknown booking -> 404; no token -> 401; invalid simulate value -> 422; a client-supplied amount is ignored.
- Webhook: missing or bad signature -> 401; invalid body -> 422; unknown provider_ref -> 404; a pending payment plus a SUCCESS event confirms the booking; the SAME event sent 3 times -> one WebhookEvent row, one payment, booking unchanged after the first, later responses "already_processed"; a different event_id with the same status -> unchanged; a FAILED event after SUCCESS -> ignored, booking still CONFIRMED; SUCCESS after the booking was cancelled -> booking stays CANCELLED.
- Database level: inserting a second SUCCESS payment for one booking directly raises IntegrityError.
- Concurrency: deliver the same event from two threads at once, each with its own session. Because this needs committed data, build a separate fixture that commits its setup data and truncates the tables afterwards; do not use the rollback-wrapped fixture. Assert exactly one "processed", one "already_processed", and one WebhookEvent row.

## Phases
0. skeleton
1. auth + tests
2. centres catalogue
3. bookings + state machine
4. payments + webhook + idempotency tests
5. logging, pagination, Dockerfile
6. README.
