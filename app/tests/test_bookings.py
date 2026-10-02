import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.models.booking import BookingStatus
from app.services.booking_service import change_status
from app.models.booking import Booking
from fastapi import HTTPException



def test_unauthenticated(client: TestClient):
    assert client.post("/bookings", json={}).status_code == 401
    assert client.get("/bookings").status_code == 401
    assert client.get("/bookings/1").status_code == 401
    assert client.post("/bookings/1/cancel").status_code == 401

def test_create_booking_success_and_snapshot(client: TestClient, auth_headers, admin_headers, setup_data):
    c_id, t_id = setup_data
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    
    # Create booking
    res = client.post("/bookings", headers=auth_headers, json={
        "centre_id": c_id, "test_id": t_id, "appointment_at": future_time
    })
    assert res.status_code == 201
    booking = res.json()
    assert booking["status"] == "PENDING"
    assert booking["amount"] == "100.00"
    
    # Change centre price
    client.patch(f"/centres/{c_id}/tests/{t_id}", headers=admin_headers, json={"price": 150.0})
    
    # Existing booking amount is unchanged
    res2 = client.get(f"/bookings/{booking['id']}", headers=auth_headers)
    assert res2.json()["amount"] == "100.00"

def test_create_booking_invalid_refs(client: TestClient, auth_headers, admin_headers, setup_data):
    c_id, t_id = setup_data
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    
    # Unknown centre
    assert client.post("/bookings", headers=auth_headers, json={"centre_id": 999, "test_id": t_id, "appointment_at": future_time}).status_code == 404
    # Unknown test
    assert client.post("/bookings", headers=auth_headers, json={"centre_id": c_id, "test_id": 999, "appointment_at": future_time}).status_code == 404
    
    # Create new test not offered by centre
    t2 = client.post("/tests", headers=admin_headers, json={"name": "TB2"}).json()
    assert client.post("/bookings", headers=auth_headers, json={"centre_id": c_id, "test_id": t2["id"], "appointment_at": future_time}).status_code == 404

def test_create_booking_validation(client: TestClient, auth_headers, setup_data):
    c_id, t_id = setup_data
    past_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    naive_time = datetime.now().isoformat()
    
    assert client.post("/bookings", headers=auth_headers, json={"centre_id": c_id, "test_id": t_id, "appointment_at": past_time}).status_code == 422
    assert client.post("/bookings", headers=auth_headers, json={"centre_id": c_id, "test_id": t_id, "appointment_at": naive_time}).status_code == 422
    assert client.post("/bookings", headers=auth_headers, json={"centre_id": c_id, "test_id": t_id}).status_code == 422

def test_duplicate_active_booking(client: TestClient, auth_headers, setup_data):
    c_id, t_id = setup_data
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    
    res1 = client.post("/bookings", headers=auth_headers, json={
        "centre_id": c_id, "test_id": t_id, "appointment_at": future_time
    })
    assert res1.status_code == 201
    
    # duplicate
    res2 = client.post("/bookings", headers=auth_headers, json={
        "centre_id": c_id, "test_id": t_id, "appointment_at": future_time
    })
    assert res2.status_code == 409
    
    # cancel first
    client.post(f"/bookings/{res1.json()['id']}/cancel", headers=auth_headers)
    
    # create again
    res3 = client.post("/bookings", headers=auth_headers, json={
        "centre_id": c_id, "test_id": t_id, "appointment_at": future_time
    })
    assert res3.status_code == 201

def test_user_isolation_and_404(client: TestClient, auth_headers, setup_data):
    c_id, t_id = setup_data
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    
    b = client.post("/bookings", headers=auth_headers, json={
        "centre_id": c_id, "test_id": t_id, "appointment_at": future_time
    }).json()
    
    # Create user B
    client.post("/auth/signup", json={"email": "b@eve.com", "password": "password", "full_name": "B"})
    token_b = client.post("/auth/login", json={"email": "b@eve.com", "password": "password"}).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # User B accessing User A's booking
    assert client.get(f"/bookings/{b['id']}", headers=headers_b).status_code == 404
    assert client.post(f"/bookings/{b['id']}/cancel", headers=headers_b).status_code == 404
    
    # Unknown id
    assert client.get("/bookings/9999", headers=auth_headers).status_code == 404
    
    # Non-numeric id
    assert client.get("/bookings/abc", headers=auth_headers).status_code == 422

def test_list_bookings(client: TestClient, auth_headers, setup_data):
    c_id, t_id = setup_data
    
    for i in range(1, 4):
        client.post("/bookings", headers=auth_headers, json={
            "centre_id": c_id, "test_id": t_id, "appointment_at": (datetime.now(timezone.utc) + timedelta(days=i)).isoformat()
        })
    
    # Add one cancelled
    b = client.post("/bookings", headers=auth_headers, json={
        "centre_id": c_id, "test_id": t_id, "appointment_at": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    }).json()
    client.post(f"/bookings/{b['id']}/cancel", headers=auth_headers)
    
    res = client.get("/bookings?page=1&page_size=2", headers=auth_headers)
    assert len(res.json()["items"]) == 2
    
    res_status = client.get("/bookings?status=CANCELLED", headers=auth_headers)
    assert len(res_status.json()["items"]) == 1
    
    assert client.get("/bookings?status=INVALID", headers=auth_headers).status_code == 422

def test_cancel_booking(client: TestClient, auth_headers, setup_data):
    c_id, t_id = setup_data
    b = client.post("/bookings", headers=auth_headers, json={
        "centre_id": c_id, "test_id": t_id, "appointment_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    }).json()
    
    res = client.post(f"/bookings/{b['id']}/cancel", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"
    
    # Cancel twice
    res2 = client.post(f"/bookings/{b['id']}/cancel", headers=auth_headers)
    assert res2.status_code == 409

def test_cancel_past_booking(client: TestClient, auth_headers, setup_data, db):
    c_id, t_id = setup_data
    b = client.post("/bookings", headers=auth_headers, json={
        "centre_id": c_id, "test_id": t_id, "appointment_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    }).json()
    
    booking = db.get(Booking, b["id"])
    booking.appointment_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    
    res = client.post(f"/bookings/{b['id']}/cancel", headers=auth_headers)
    assert res.status_code == 409

from unittest.mock import patch

def test_duplicate_active_booking_integrity_error(client: TestClient, auth_headers, setup_data):
    c_id, t_id = setup_data
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    
    res1 = client.post("/bookings", headers=auth_headers, json={
        "centre_id": c_id, "test_id": t_id, "appointment_at": future_time
    })
    assert res1.status_code == 201
    
    with patch("app.services.booking_service.find_active_duplicate", return_value=None):
        res2 = client.post("/bookings", headers=auth_headers, json={
            "centre_id": c_id, "test_id": t_id, "appointment_at": future_time
        })
        assert res2.status_code == 409

# State machine unit tests
ALLOWED_TRANSITIONS = {
    BookingStatus.PENDING: [BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.CANCELLED],
    BookingStatus.FAILED: [BookingStatus.CONFIRMED, BookingStatus.CANCELLED],
    BookingStatus.CONFIRMED: [BookingStatus.CANCELLED],
    BookingStatus.CANCELLED: []
}

ALL_STATUSES = [BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.CANCELLED]

@pytest.mark.parametrize("start", ALL_STATUSES)
@pytest.mark.parametrize("end", ALL_STATUSES)
def test_state_machine_transitions(start, end):
    b = Booking(status=start.value)
    
    if end in ALLOWED_TRANSITIONS[start]:
        change_status(b, end)
        assert b.status == end.value
    else:
        with pytest.raises(HTTPException) as exc:
            change_status(b, end)
        assert exc.value.status_code == 409
