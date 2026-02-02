
import os
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["USE_LLM_TRIAGE"] = "false"

from app.main import app
from app.db import engine, Base, SessionLocal
from app.models import User
from app.security import hash_password

@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    c = TestClient(app)
    db = SessionLocal()
    try:
        if not db.query(User).filter_by(email="patient@test.example.com").first():
            db.add(User(email="patient@test.example.com", password_hash=hash_password("password"), role="patient", clinic_id=1001))
        if not db.query(User).filter_by(email="clinician@test.example.com").first():
            db.add(User(email="clinician@test.example.com", password_hash=hash_password("password"), role="clinician", clinic_id=1001))
        db.commit()
    finally:
        db.close()
    yield c
