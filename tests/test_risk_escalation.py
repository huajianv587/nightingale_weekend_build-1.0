
def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["token"]

def test_risk_escalation(client):
    token = login(client, "patient@test.example.com", "password")
    r = client.post(f"/api/patient/message?token={token}", json={"text":"I have crushing chest pain."})
    assert r.status_code == 200
    data = r.json()
    assert data["risk"]["risk_level"] == "high"
    assert data["escalation_required"] is True
    assert data["ticket_id"] is not None
