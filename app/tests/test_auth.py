from fastapi.testclient import TestClient

def test_signup_success(client: TestClient):
    response = client.post("/auth/signup", json={
        "email": "Test@example.com",
        "password": "password123",
        "full_name": "Test User"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data
    assert "password_hash" not in data

def test_signup_duplicate_email(client: TestClient):
    payload = {
        "email": "test@example.com",
        "password": "password123",
        "full_name": "Test User"
    }
    client.post("/auth/signup", json=payload)
    
    payload["email"] = "TEST@example.com"
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"

def test_signup_invalid_email(client: TestClient):
    response = client.post("/auth/signup", json={
        "email": "not-an-email",
        "password": "password123",
        "full_name": "Test User"
    })
    assert response.status_code == 422

def test_signup_short_password(client: TestClient):
    response = client.post("/auth/signup", json={
        "email": "test2@example.com",
        "password": "short",
        "full_name": "Test User"
    })
    assert response.status_code == 422

def test_login_success(client: TestClient):
    client.post("/auth/signup", json={
        "email": "login@example.com",
        "password": "password123",
        "full_name": "Test User"
    })
    
    response = client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_wrong_password(client: TestClient):
    client.post("/auth/signup", json={
        "email": "login2@example.com",
        "password": "password123",
        "full_name": "Test User"
    })
    
    response = client.post("/auth/login", json={
        "email": "login2@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

def test_login_unknown_email(client: TestClient):
    response = client.post("/auth/login", json={
        "email": "unknown@example.com",
        "password": "password123"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

def test_get_me_success(client: TestClient):
    client.post("/auth/signup", json={
        "email": "me@example.com",
        "password": "password123",
        "full_name": "Test User"
    })
    login_resp = client.post("/auth/login", json={
        "email": "me@example.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"
    assert "password_hash" not in data

def test_get_me_no_token(client: TestClient):
    response = client.get("/auth/me")
    assert response.status_code == 401

def test_get_me_garbage_token(client: TestClient):
    response = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401

def test_get_me_expired_token(client: TestClient):
    from app.security import create_access_token
    from app.config import settings
    orig_expiry = settings.access_token_expire_minutes
    settings.access_token_expire_minutes = -1
    token = create_access_token(1)
    settings.access_token_expire_minutes = orig_expiry
    
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

def test_signup_long_password(client: TestClient):
    response = client.post("/auth/signup", json={
        "email": "long@example.com",
        "password": "a" * 73,
        "full_name": "Test User"
    })
    assert response.status_code == 422
    assert "Password must not exceed 72 bytes" in response.text

def test_login_long_password(client: TestClient):
    response = client.post("/auth/login", json={
        "email": "long@example.com",
        "password": "a" * 73
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
