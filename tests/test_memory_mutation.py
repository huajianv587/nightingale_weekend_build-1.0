
def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["token"]

def test_memory_mutation(client):
    token = login(client, "patient@test.example.com", "password")
    client.post(f"/api/patient/message?token={token}", json={"text":"I take Advil."})
    prof = client.get(f"/api/patient/messages?token={token}").json()["profile"]
    assert any(m["value"].lower().startswith("advil") and m["status"]=="active" for m in prof["medications"])

    client.post(f"/api/patient/message?token={token}", json={"text":"Actually I stopped Advil last week."})
    prof2 = client.get(f"/api/patient/messages?token={token}").json()["profile"]
    assert any(m["value"].lower().startswith("advil") and m["status"]=="stopped" for m in prof2["medications"])
    assert any(m.get("prov",{}).get("message_id") for m in prof2["medications"])
