
def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["token"]

def test_grounding_has_citation(client):
    token = login(client, "patient@test.example.com", "password")
    client.post(f"/api/patient/message?token={token}", json={"text":"I have a headache."})
    msgs = client.get(f"/api/patient/messages?token={token}").json()["messages"]
    assistant = [m for m in msgs if m["sender_role"]=="assistant"][-1]
    assert assistant["citations"] and len(assistant["citations"]) >= 1
