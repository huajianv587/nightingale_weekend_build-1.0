
def signup(client, email, role):
    r = client.post("/api/auth/signup", json={"email": email, "password":"password", "role": role})
    assert r.status_code == 200
    return r.json()["token"]

def test_access_control(client):
    token_a = signup(client, "patientA@test.example.com", "patient")
    token_b = signup(client, "patientB@test.example.com", "patient")

    assert client.get(f"/api/patient/messages?token={token_a}").status_code == 200
    # patient cannot access clinician queue
    assert client.get(f"/api/clinician/tickets?token={token_b}").status_code in (401,403)
