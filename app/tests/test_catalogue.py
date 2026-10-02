import pytest
from fastapi.testclient import TestClient

def test_public_reads(client: TestClient):
    res_tests = client.get("/tests")
    assert res_tests.status_code == 200
    res_centres = client.get("/centres")
    assert res_centres.status_code == 200

def test_auth_on_writes(client: TestClient, auth_headers):
    # anonymous
    assert client.post("/tests", json={"name": "T1"}).status_code == 401
    assert client.post("/centres", json={"name": "C1", "location": "L1", "address": "A1"}).status_code == 401
    assert client.post("/centres/1/tests", json={"test_id": 1, "price": 10.0}).status_code == 401
    assert client.patch("/centres/1/tests/1", json={"price": 20.0}).status_code == 401
    
    # normal user
    assert client.post("/tests", headers=auth_headers, json={"name": "T1"}).status_code == 403
    assert client.post("/centres", headers=auth_headers, json={"name": "C1", "location": "L1", "address": "A1"}).status_code == 403
    assert client.post("/centres/1/tests", headers=auth_headers, json={"test_id": 1, "price": 10.0}).status_code == 403
    assert client.patch("/centres/1/tests/1", headers=auth_headers, json={"price": 20.0}).status_code == 403

def test_admin_creates_test_and_centre(client: TestClient, admin_headers):
    res_t = client.post("/tests", headers=admin_headers, json={"name": "Test A", "description": "Desc"})
    assert res_t.status_code == 201
    assert res_t.json()["name"] == "Test A"
    
    res_c = client.post("/centres", headers=admin_headers, json={"name": "Centre A", "location": "City X", "address": "123 St"})
    assert res_c.status_code == 201
    assert res_c.json()["name"] == "Centre A"

def test_duplicate_test_name(client: TestClient, admin_headers):
    client.post("/tests", headers=admin_headers, json={"name": "Unique Test"})
    res = client.post("/tests", headers=admin_headers, json={"name": "Unique Test"})
    assert res.status_code == 409

def test_add_test_to_centre(client: TestClient, admin_headers):
    c = client.post("/centres", headers=admin_headers, json={"name": "C2", "location": "L2", "address": "A2"}).json()
    t = client.post("/tests", headers=admin_headers, json={"name": "T2"}).json()
    
    res = client.post(f"/centres/{c['id']}/tests", headers=admin_headers, json={"test_id": t["id"], "price": 15.50})
    assert res.status_code == 201
    assert res.json()["price"] == "15.50"

def test_duplicate_offering(client: TestClient, admin_headers):
    c = client.post("/centres", headers=admin_headers, json={"name": "C3", "location": "L3", "address": "A3"}).json()
    t = client.post("/tests", headers=admin_headers, json={"name": "T3"}).json()
    
    client.post(f"/centres/{c['id']}/tests", headers=admin_headers, json={"test_id": t["id"], "price": 15.50})
    res = client.post(f"/centres/{c['id']}/tests", headers=admin_headers, json={"test_id": t["id"], "price": 20.00})
    assert res.status_code == 409

def test_price_validation(client: TestClient, admin_headers):
    c = client.post("/centres", headers=admin_headers, json={"name": "C4", "location": "L4", "address": "A4"}).json()
    t = client.post("/tests", headers=admin_headers, json={"name": "T4"}).json()
    
    # 0 price
    res = client.post(f"/centres/{c['id']}/tests", headers=admin_headers, json={"test_id": t["id"], "price": 0})
    assert res.status_code == 422
    
    # negative price
    res = client.post(f"/centres/{c['id']}/tests", headers=admin_headers, json={"test_id": t["id"], "price": -5})
    assert res.status_code == 422
    
    # 3-decimal-place
    res = client.post(f"/centres/{c['id']}/tests", headers=admin_headers, json={"test_id": t["id"], "price": 10.123})
    assert res.status_code == 422

def test_unknown_ids(client: TestClient, admin_headers):
    c = client.post("/centres", headers=admin_headers, json={"name": "C5", "location": "L5", "address": "A5"}).json()
    t = client.post("/tests", headers=admin_headers, json={"name": "T5"}).json()
    
    # unknown centre on get
    assert client.get("/centres/9999").status_code == 404
    
    # unknown centre on add test
    assert client.post("/centres/9999/tests", headers=admin_headers, json={"test_id": t["id"], "price": 10}).status_code == 404
    
    # unknown test on add test
    assert client.post(f"/centres/{c['id']}/tests", headers=admin_headers, json={"test_id": 9999, "price": 10}).status_code == 404
    
    # unknown test on patch
    assert client.patch(f"/centres/{c['id']}/tests/9999", headers=admin_headers, json={"price": 10}).status_code == 404

def test_pagination(client: TestClient, admin_headers):
    for i in range(15):
        client.post("/tests", headers=admin_headers, json={"name": f"Paginated Test {i}"})
    
    res = client.get("/tests?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 10
    assert data["total"] >= 15
    assert data["page"] == 1
    assert data["page_size"] == 10
    
    res2 = client.get("/tests?page=2&page_size=10")
    assert res2.status_code == 200
    assert len(res2.json()["items"]) >= 5

def test_location_filter(client: TestClient, admin_headers):
    client.post("/centres", headers=admin_headers, json={"name": "F1", "location": "Seattle", "address": "123"})
    client.post("/centres", headers=admin_headers, json={"name": "F2", "location": "Seaside", "address": "123"})
    client.post("/centres", headers=admin_headers, json={"name": "F3", "location": "New York", "address": "123"})
    
    res = client.get("/centres?location=sea")
    assert res.status_code == 200
    items = res.json()["items"]
    names = [c["name"] for c in items]
    assert "F1" in names
    assert "F2" in names
    assert "F3" not in names

def test_price_update(client: TestClient, admin_headers):
    c = client.post("/centres", headers=admin_headers, json={"name": "C6", "location": "L6", "address": "A6"}).json()
    t = client.post("/tests", headers=admin_headers, json={"name": "T6"}).json()
    
    client.post(f"/centres/{c['id']}/tests", headers=admin_headers, json={"test_id": t["id"], "price": 10.0})
    
    res = client.patch(f"/centres/{c['id']}/tests/{t['id']}", headers=admin_headers, json={"price": 25.5})
    assert res.status_code == 200
    assert res.json()["price"] == "25.50"
    
    res_get = client.get(f"/centres/{c['id']}")
    assert res_get.json()["tests"][0]["price"] == "25.50"
