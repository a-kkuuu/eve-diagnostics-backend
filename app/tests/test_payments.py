import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
import hmac
import hashlib
import json
import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus, WebhookEvent
from app.models.user import User
from app.database import Base, get_db
import time

def create_booking(client: TestClient, auth_headers, setup_data):
    c_id, t_id = setup_data
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    res = client.post("/bookings", headers=auth_headers, json={
        "centre_id": c_id, "test_id": t_id, "appointment_at": future_time
    })
    return res.json()

def generate_signature(payload: dict) -> str:
    body = json.dumps(payload).encode()
    return hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()

def test_payment_no_token(client: TestClient):
    res = client.post("/payments/", json={"booking_id": 1})
    assert res.status_code == 401

def test_payment_unknown_booking(client: TestClient, auth_headers):
    res = client.post("/payments/", headers=auth_headers, json={"booking_id": 9999})
    assert res.status_code == 404

def test_payment_other_user_booking(client: TestClient, auth_headers, setup_data, db):
    # Setup data uses user_token. Let's create a booking with user B.
    from app.tests.conftest import hash_password
    b_user = User(email="testpay_b@eve.com", password_hash=hash_password("password"), full_name="B")
    db.add(b_user)
    db.commit()
    from app.security import create_access_token
    b_token = create_access_token(b_user.id)
    b_headers = {"Authorization": f"Bearer {b_token}"}
    
    b_booking = create_booking(client, b_headers, setup_data)
    
    # Try to pay for B's booking with user A's token
    res = client.post("/payments/", headers=auth_headers, json={"booking_id": b_booking["id"]})
    assert res.status_code == 404

def test_payment_invalid_simulate(client: TestClient, auth_headers, setup_data):
    b = create_booking(client, auth_headers, setup_data)
    res = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "invalid"})
    assert res.status_code == 422

def test_payment_success(client: TestClient, auth_headers, setup_data):
    b = create_booking(client, auth_headers, setup_data)
    # Ignore client amount
    res = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "success", "amount": 1.0})
    assert res.status_code == 201
    pay = res.json()
    assert pay["status"] == "SUCCESS"
    assert pay["amount"] == b["amount"]
    
    # Check booking status
    b_res = client.get(f"/bookings", headers=auth_headers)
    booking = next(x for x in b_res.json()["items"] if x["id"] == b["id"])
    assert booking["status"] == "CONFIRMED"

def test_payment_failed(client: TestClient, auth_headers, setup_data):
    b = create_booking(client, auth_headers, setup_data)
    res = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "failed"})
    assert res.status_code == 201
    assert res.json()["status"] == "FAILED"
    
    b_res = client.get(f"/bookings", headers=auth_headers)
    booking = next(x for x in b_res.json()["items"] if x["id"] == b["id"])
    assert booking["status"] == "FAILED"

def test_payment_retry_success(client: TestClient, auth_headers, setup_data):
    b = create_booking(client, auth_headers, setup_data)
    client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "failed"})
    
    res2 = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "success"})
    assert res2.status_code == 201
    
    b_res = client.get(f"/bookings", headers=auth_headers)
    booking = next(x for x in b_res.json()["items"] if x["id"] == b["id"])
    assert booking["status"] == "CONFIRMED"

def test_payment_confirmed_booking(client: TestClient, auth_headers, setup_data):
    b = create_booking(client, auth_headers, setup_data)
    client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "success"})
    
    # Try again on confirmed booking
    res = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "success"})
    assert res.status_code == 409

def test_payment_cancelled_booking(client: TestClient, auth_headers, setup_data):
    b = create_booking(client, auth_headers, setup_data)
    client.post(f"/bookings/{b['id']}/cancel", headers=auth_headers)
    
    res = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "success"})
    assert res.status_code == 409

def test_webhook_missing_signature(client: TestClient):
    res = client.post("/payments/webhook/", json={})
    assert res.status_code == 401
    
def test_webhook_bad_signature(client: TestClient):
    res = client.post("/payments/webhook/", json={}, headers={"X-Signature": "bad"})
    assert res.status_code == 401

def test_webhook_non_ascii_signature(client: TestClient):
    res = client.post("/payments/webhook/", json={}, headers={b"X-Signature": "badñsig".encode("utf-8")})
    assert res.status_code == 401

def test_webhook_invalid_body(client: TestClient):
    payload = {"invalid": "yes"}
    sig = generate_signature(payload)
    res = client.post("/payments/webhook/", content=json.dumps(payload), headers={"X-Signature": sig})
    assert res.status_code == 422

def test_webhook_unknown_provider_ref(client: TestClient):
    payload = {"event_id": "e1", "provider_ref": "unknown", "status": "SUCCESS"}
    sig = generate_signature(payload)
    res = client.post("/payments/webhook/", content=json.dumps(payload), headers={"X-Signature": sig})
    assert res.status_code == 404

def test_webhook_success_confirms_booking(client: TestClient, auth_headers, setup_data):
    b = create_booking(client, auth_headers, setup_data)
    p_res = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "pending"})
    p_ref = p_res.json()["provider_ref"]
    
    payload = {"event_id": "e_success", "provider_ref": p_ref, "status": "SUCCESS"}
    sig = generate_signature(payload)
    w_res = client.post("/payments/webhook/", content=json.dumps(payload), headers={"X-Signature": sig})
    assert w_res.status_code == 200
    assert w_res.json()["status"] == "processed"
    
    b_res = client.get(f"/bookings", headers=auth_headers)
    booking = next(x for x in b_res.json()["items"] if x["id"] == b["id"])
    assert booking["status"] == "CONFIRMED"

def test_webhook_idempotency_same_event(client: TestClient, auth_headers, setup_data, db):
    b = create_booking(client, auth_headers, setup_data)
    p_res = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "pending"})
    p_ref = p_res.json()["provider_ref"]
    
    payload = {"event_id": "e_idem", "provider_ref": p_ref, "status": "SUCCESS"}
    body = json.dumps(payload)
    sig = hmac.new(settings.webhook_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    
    # 1st
    res1 = client.post("/payments/webhook/", content=body, headers={"X-Signature": sig})
    assert res1.json()["status"] == "processed"
    
    # 2nd
    res2 = client.post("/payments/webhook/", content=body, headers={"X-Signature": sig})
    assert res2.json()["status"] == "already_processed"
    
    # 3rd
    res3 = client.post("/payments/webhook/", content=body, headers={"X-Signature": sig})
    assert res3.json()["status"] == "already_processed"
    
    # assert 1 row in WebhookEvent
    assert db.query(WebhookEvent).filter(WebhookEvent.event_id == "e_idem").count() == 1
    # assert 1 payment
    assert db.query(Payment).filter(Payment.booking_id == b["id"]).count() == 1

def test_webhook_different_event_same_status(client: TestClient, auth_headers, setup_data):
    b = create_booking(client, auth_headers, setup_data)
    p_res = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "pending"})
    p_ref = p_res.json()["provider_ref"]
    
    payload1 = {"event_id": "e_diff1", "provider_ref": p_ref, "status": "FAILED"}
    client.post("/payments/webhook/", content=json.dumps(payload1), headers={"X-Signature": generate_signature(payload1)})
    
    payload2 = {"event_id": "e_diff2", "provider_ref": p_ref, "status": "FAILED"}
    res2 = client.post("/payments/webhook/", content=json.dumps(payload2), headers={"X-Signature": generate_signature(payload2)})
    assert res2.json()["status"] == "unchanged"

def test_webhook_failed_after_success(client: TestClient, auth_headers, setup_data):
    b = create_booking(client, auth_headers, setup_data)
    p_res = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "success"})
    p_ref = p_res.json()["provider_ref"]
    
    payload = {"event_id": "e_fail", "provider_ref": p_ref, "status": "FAILED"}
    res = client.post("/payments/webhook/", content=json.dumps(payload), headers={"X-Signature": generate_signature(payload)})
    assert res.json()["status"] == "ignored"

def test_webhook_success_after_cancelled(client: TestClient, auth_headers, setup_data, db):
    b = create_booking(client, auth_headers, setup_data)
    p_res = client.post("/payments/", headers=auth_headers, json={"booking_id": b["id"], "simulate": "pending"})
    p_ref = p_res.json()["provider_ref"]
    
    client.post(f"/bookings/{b['id']}/cancel", headers=auth_headers)
    
    payload = {"event_id": "e_succ_canc", "provider_ref": p_ref, "status": "SUCCESS"}
    client.post("/payments/webhook/", content=json.dumps(payload), headers={"X-Signature": generate_signature(payload)})
    
    db.expire_all()
    b_updated = db.query(Booking).get(b["id"])
    assert b_updated.status == "CANCELLED"

def test_db_unique_success_payment(db, setup_data, test_user):
    c_id, t_id = setup_data
    # direct DB insert
    booking = Booking(user_id=test_user.id, centre_id=c_id, test_id=t_id, appointment_at=datetime.now(timezone.utc)+timedelta(days=1), amount=10.0, status="CONFIRMED")
    db.add(booking)
    db.commit()
    
    p1 = Payment(booking_id=booking.id, amount=10.0, status="SUCCESS", provider_ref="pay_1")
    db.add(p1)
    db.commit()
    
    p2 = Payment(booking_id=booking.id, amount=10.0, status="SUCCESS", provider_ref="pay_2")
    db.add(p2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.fixture
def concurrency_db_engine():
    from app.tests.conftest import TEST_DATABASE_URL
    return create_engine(TEST_DATABASE_URL, pool_size=5, max_overflow=5)

def test_webhook_concurrency(concurrency_db_engine):
    # Setup data with committed engine
    SessionLocal = sessionmaker(bind=concurrency_db_engine)
    session = SessionLocal()
    
    # Needs a real user
    from app.security import hash_password
    from app.models.centre import Centre
    from app.models.test import Test
    from app.models.centre_test import CentreTest
    user = User(email="conc@eve.com", password_hash=hash_password("pw"), full_name="Conc")
    c = Centre(name="CC", location="LC", address="AC")
    t = Test(name="TC")
    session.add_all([user, c, t])
    session.commit()
    
    ct = CentreTest(centre_id=c.id, test_id=t.id, price=10.0)
    session.add(ct)
    session.commit()
    
    b = Booking(user_id=user.id, centre_id=c.id, test_id=t.id, appointment_at=datetime.now(timezone.utc)+timedelta(days=1), amount=10.0, status="PENDING")
    session.add(b)
    session.commit()
    booking_id = b.id
    
    p = Payment(booking_id=booking_id, amount=10.0, status="PENDING", provider_ref="pay_conc")
    session.add(p)
    session.commit()
    session.close()

    try:
        # Now fire 2 threads hitting webhook with the same event
        payload = {"event_id": "e_conc", "provider_ref": "pay_conc", "status": "SUCCESS"}
        body = json.dumps(payload).encode()
        sig = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        
        results = []
        barrier = threading.Barrier(2)
        
        from app.main import app
        from fastapi.testclient import TestClient
        
        SessionLocal = sessionmaker(bind=concurrency_db_engine)
        def override_get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()
                
        app.dependency_overrides[get_db] = override_get_db
        
        def fire():
            c = TestClient(app)
            barrier.wait()
            res = c.post("/payments/webhook/", content=body, headers={"X-Signature": sig})
            results.append(res.json().get("status"))

        t1 = threading.Thread(target=fire)
        t2 = threading.Thread(target=fire)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Assert
        assert sorted(results) == ["already_processed", "processed"]
        
        session = SessionLocal()
        assert session.query(WebhookEvent).filter(WebhookEvent.event_id == "e_conc").count() == 1
        assert session.query(Payment).filter(Payment.provider_ref == "pay_conc").count() == 1
        
        final_booking = session.query(Booking).filter(Booking.id == booking_id).first()
        assert final_booking.status == "CONFIRMED"
        session.close()
    finally:
        del app.dependency_overrides[get_db]
        # cleanup tables
        with concurrency_db_engine.connect() as conn:
            conn.execute(Base.metadata.tables['webhook_events'].delete())
            conn.execute(Base.metadata.tables['payments'].delete())
            conn.execute(Base.metadata.tables['bookings'].delete())
            conn.execute(Base.metadata.tables['users'].delete())
            conn.execute(Base.metadata.tables['centre_tests'].delete())
            conn.execute(Base.metadata.tables['tests'].delete())
            conn.execute(Base.metadata.tables['centres'].delete())
            conn.commit()


def test_webhook_concurrency_conflicting_events(concurrency_db_engine):
    # Setup data with committed engine
    SessionLocal = sessionmaker(bind=concurrency_db_engine)
    session = SessionLocal()
    
    from app.security import hash_password
    from app.models.centre import Centre
    from app.models.test import Test
    from app.models.centre_test import CentreTest
    user = User(email="conc2@eve.com", password_hash=hash_password("pw"), full_name="Conc2")
    c = Centre(name="CC2", location="LC2", address="AC2")
    t = Test(name="TC2")
    session.add_all([user, c, t])
    session.commit()
    
    ct = CentreTest(centre_id=c.id, test_id=t.id, price=10.0)
    session.add(ct)
    session.commit()
    
    b = Booking(user_id=user.id, centre_id=c.id, test_id=t.id, appointment_at=datetime.now(timezone.utc)+timedelta(days=1), amount=10.0, status="PENDING")
    session.add(b)
    session.commit()
    booking_id = b.id
    
    p = Payment(booking_id=booking_id, amount=10.0, status="PENDING", provider_ref="pay_conc2")
    session.add(p)
    session.commit()
    session.close()

    try:
        results = []
        barrier = threading.Barrier(2)
        
        from app.main import app
        from fastapi.testclient import TestClient
        
        SessionLocal = sessionmaker(bind=concurrency_db_engine)
        def override_get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()
                
        app.dependency_overrides[get_db] = override_get_db
        
        def fire(status_val, event_id):
            client = TestClient(app)
            payload = {"event_id": event_id, "provider_ref": "pay_conc2", "status": status_val}
            body = json.dumps(payload).encode()
            sig = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
            barrier.wait()
            res = client.post("/payments/webhook/", content=body, headers={"X-Signature": sig})
            results.append((status_val, res.json().get("status")))

        t1 = threading.Thread(target=fire, args=("SUCCESS", "e_conc_success"))
        t2 = threading.Thread(target=fire, args=("FAILED", "e_conc_failed"))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        session = SessionLocal()
        assert session.query(WebhookEvent).filter(WebhookEvent.provider_ref == "pay_conc2").count() == 2
        
        final_payment = session.query(Payment).filter(Payment.provider_ref == "pay_conc2").first()
        final_booking = session.query(Booking).filter(Booking.id == booking_id).first()
        
        # They should be consistent
        if final_payment.status == "SUCCESS":
            assert final_booking.status == "CONFIRMED"
        else:
            assert final_payment.status == "FAILED"
            assert final_booking.status == "FAILED"
            
        session.close()
    finally:
        del app.dependency_overrides[get_db]
        with concurrency_db_engine.connect() as conn:
            conn.execute(Base.metadata.tables['webhook_events'].delete())
            conn.execute(Base.metadata.tables['payments'].delete())
            conn.execute(Base.metadata.tables['bookings'].delete())
            conn.execute(Base.metadata.tables['users'].delete())
            conn.execute(Base.metadata.tables['centre_tests'].delete())
            conn.execute(Base.metadata.tables['tests'].delete())
            conn.execute(Base.metadata.tables['centres'].delete())
            conn.commit()
