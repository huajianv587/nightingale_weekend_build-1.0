
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db import engine, Base, get_db, SessionLocal
from .models import User, Thread, Message, Ticket
from .security import hash_password, verify_password, create_token, decode_token
from .audit import log_event
from .fingerprint import check_and_record_ip
from .realtime import manager
from .nlp.redaction import redact_no_phi
from .nlp.risk import assess_risk
from .services import upsert_memory, profile_snapshot, create_ticket
from .voice.asr_client import transcribe_audio

# 你的 LLM 接口：确保这里函数名就是 generate_reply(messages: List[dict]) -> str
from app.llm_client import generate_reply


# -------------------------
# App init (必须在所有 @app.xxx 之前)
# -------------------------
app = FastAPI(title="Nightingale Closed Loop")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

import time
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

@app.on_event("startup")
def on_startup():
    # 等待 MySQL 真正可连接（避免 compose 刚启动就 create_all 导致 app 崩溃）
    last_err = None
    for _ in range(30):  # 最多等 30 秒
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            Base.metadata.create_all(bind=engine)
            return
        except OperationalError as e:
            last_err = e
            time.sleep(1)
    raise last_err


DEMO_CLINIC_ID = 1001


# -------------------------
# Pydantic schemas
# -------------------------
class SignupIn(BaseModel):
    email: str
    password: str
    role: str  # patient|clinician


class LoginIn(BaseModel):
    email: str
    password: str


class SendMessageIn(BaseModel):
    text: str


class ClinicianReplyIn(BaseModel):
    ticket_id: int
    text: str


# -------------------------
# Helpers
# -------------------------
def seed_demo(db: Session):
    # demo 账号：patient / clinician
    if not db.query(User).filter_by(email="patient@demo.example.com").first():
        db.add(User(
            email="patient@demo.example.com",
            password_hash=hash_password("password"),
            role="patient",
            clinic_id=DEMO_CLINIC_ID
        ))
    if not db.query(User).filter_by(email="clinician@demo.example.com").first():
        db.add(User(
            email="clinician@demo.example.com",
            password_hash=hash_password("password"),
            role="clinician",
            clinic_id=DEMO_CLINIC_ID
        ))
    db.commit()


@app.middleware("http")
async def middleware(request: Request, call_next):
    db = SessionLocal()
    try:
        ip = request.client.host if request.client else "unknown"
        ok, blocked_until = check_and_record_ip(db, ip, strike_on_every_request=False)
        if not ok:
            raise HTTPException(status_code=429, detail=f"Blocked until {blocked_until.isoformat()}Z")
        seed_demo(db)
    finally:
        db.close()
    return await call_next(request)


def auth_user(token: str, db: Session) -> User:
    try:
        payload = decode_token(token)
        uid = int(payload["sub"])
        u = db.query(User).filter_by(id=uid).first()
        if not u:
            raise HTTPException(status_code=401, detail="Invalid token user")
        return u
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def ensure_thread(db: Session, patient: User) -> Thread:
    th = db.query(Thread).filter_by(patient_id=patient.id).first()
    if th:
        return th
    th = Thread(
        patient_id=patient.id,
        clinic_id=patient.clinic_id or DEMO_CLINIC_ID,
        created_at=datetime.utcnow()
    )
    db.add(th)
    db.commit()
    db.refresh(th)
    return th


def cite_span(message_id: int, start: int, end: int) -> Dict[str, Any]:
    return {"type": "message_span", "message_id": message_id, "start": start, "end": end}


def serialize_message(m: Message) -> Dict[str, Any]:
    return {
        "id": m.id,
        "thread_id": m.thread_id,
        "sender_role": m.sender_role,
        "content": m.content,
        "confidence": m.confidence,
        "risk_level": m.risk_level,
        "risk_reason": m.risk_reason,
        "created_at": m.created_at.isoformat() + "Z",
        "citations": m.citations_json or [],
        "is_ground_truth": bool(m.is_ground_truth),
    }


def serialize_ticket(t: Ticket) -> Dict[str, Any]:
    return {
        "id": t.id,
        "clinic_id": t.clinic_id,
        "patient_id": t.patient_id,
        "thread_id": t.thread_id,
        "status": t.status,
        "triggering_message_id": t.triggering_message_id,
        "risk_level": t.risk_level,
        "triage_summary": t.triage_summary_json,
        "profile_snapshot": t.profile_snapshot_json,
        "created_at": t.created_at.isoformat() + "Z",
    }


def build_llm_messages(db: Session, thread_id: int, limit: int = 12) -> List[Dict[str, str]]:
    """
    从 DB 取上下文，拼给 LLM。优先用 redacted_for_llm。
    注意：LLM 的 role 建议用 system/user/assistant，这里做个映射。
    """
    recent = (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.id.asc())
        .all()
    )

    def map_role(r: str) -> str:
        if r == "patient":
            return "user"
        if r == "assistant":
            return "assistant"
        if r == "clinician":
            return "system"
        return "system"

    llm_messages: List[Dict[str, str]] = []
    for m in recent[-limit:]:
        content = (getattr(m, "redacted_for_llm", None) or m.content or "").strip()
        if not content:
            continue
        llm_messages.append({"role": map_role(m.sender_role), "content": content})

    return llm_messages


# -------------------------
# Pages
# -------------------------
@app.get("/patient", response_class=HTMLResponse)
def patient_ui(request: Request):
    return templates.TemplateResponse("patient.html", {"request": request})


@app.get("/clinician", response_class=HTMLResponse)
def clinician_ui(request: Request):
    return templates.TemplateResponse("clinician.html", {"request": request})


# -------------------------
# Auth
# -------------------------
@app.post("/api/auth/signup")
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if body.role not in ("patient", "clinician"):
        raise HTTPException(status_code=400, detail="role must be patient|clinician")
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(status_code=400, detail="email exists")

    clinic_id = DEMO_CLINIC_ID
    u = User(email=body.email, password_hash=hash_password(body.password), role=body.role, clinic_id=clinic_id)
    db.add(u)
    db.commit()
    db.refresh(u)

    token = create_token(u.id, u.role, u.clinic_id)
    log_event(db, "signup", actor_user_id=u.id, target_type="user", target_id=u.id, meta={"role": u.role})
    return {"token": token, "user": {"id": u.id, "email": u.email, "role": u.role, "clinic_id": u.clinic_id}}


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=body.email).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")

    token = create_token(u.id, u.role, u.clinic_id)
    log_event(db, "login", actor_user_id=u.id, target_type="user", target_id=u.id, meta={"role": u.role})
    return {"token": token, "user": {"id": u.id, "email": u.email, "role": u.role, "clinic_id": u.clinic_id}}


# -------------------------
# Patient APIs
# -------------------------
@app.get("/api/patient/thread")
def get_thread(token: str, db: Session = Depends(get_db)):
    u = auth_user(token, db)
    if u.role != "patient":
        raise HTTPException(status_code=403, detail="patient only")
    th = ensure_thread(db, u)
    return {"thread_id": th.id, "clinic_id": th.clinic_id}


@app.get("/api/patient/messages")
def get_messages(token: str, db: Session = Depends(get_db)):
    u = auth_user(token, db)
    if u.role != "patient":
        raise HTTPException(status_code=403, detail="patient only")
    th = ensure_thread(db, u)
    msgs = db.query(Message).filter_by(thread_id=th.id).order_by(Message.created_at.asc()).all()
    return {"messages": [serialize_message(m) for m in msgs], "profile": profile_snapshot(db, u.id)}


@app.post("/api/patient/message")
async def post_message(body: SendMessageIn, token: str, db: Session = Depends(get_db)):
    u = auth_user(token, db)
    if u.role != "patient":
        raise HTTPException(status_code=403, detail="patient only")

    th = ensure_thread(db, u)
    text = (body.text or "").strip()
    if not text:
        return {"ok": True, "escalation_required": False, "risk": {"risk_level": "low", "risk_reason": ""}, "profile": profile_snapshot(db, u.id)}

    # 1) 风险评估 + 写入 patient message
    risk = assess_risk(text)
    pm = Message(
        thread_id=th.id,
        sender_role="patient",
        content=text,
        redacted_for_llm=redact_no_phi(text),
        risk_level=risk["risk_level"],
        risk_reason=risk["risk_reason"],
        risk_provenance=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)

    upsert_memory(db, u.id, pm.id, text, source_is_clinician=False)

    # ✅ 关键：把“患者自己的消息”也推送到 thread WS，这样前端不用刷新就能看到自己刚发的
    await manager.broadcast_thread(
        th.id,
        {
            "type": "new_message",
            "message": serialize_message(pm),
            "profile": profile_snapshot(db, u.id),
            "escalation_required": False,
        },
    )

    escalation_required = risk["risk_level"] in ("medium", "high")
    ticket_id = None

    # 2) 升级：创建 ticket + 给安全提示
    if escalation_required:
        t = await create_ticket(
            db,
            th.clinic_id or u.clinic_id or DEMO_CLINIC_ID,
            u.id,
            th.id,
            pm.id,
            "high" if risk["risk_level"] == "high" else "medium",
            text,
        )
        ticket_id = t.id
        await manager.broadcast_clinic(t.clinic_id, {"type": "ticket_created", "ticket_id": t.id})

        assistant_text = "I can’t safely give advice on this. I’ve alerted the clinic so a clinician can review."
        a = Message(
            thread_id=th.id,
            sender_role="assistant",
            content=assistant_text,
            confidence="high",
            risk_level=risk["risk_level"],
            risk_reason=risk["risk_reason"],
            risk_provenance=datetime.utcnow(),
            citations_json=[cite_span(pm.id, 0, min(len(text), 30))],
            created_at=datetime.utcnow(),
        )
        db.add(a)
        db.commit()
        db.refresh(a)

        await manager.broadcast_thread(
            th.id,
            {
                "type": "new_message",
                "message": serialize_message(a),
                "profile": profile_snapshot(db, u.id),
                "escalation_required": True,
                "ticket_id": ticket_id,
            },
        )
        return {"ok": True, "escalation_required": True, "ticket_id": ticket_id, "risk": risk, "profile": profile_snapshot(db, u.id)}

    # 3) 非升级：调用 LLM（带上下文）
    llm_messages = build_llm_messages(db, th.id, limit=12)

    try:
        assistant_text = (generate_reply(llm_messages) or "").strip()
    except Exception as e:
        assistant_text = ""

    if not assistant_text:
        assistant_text = "I’m here. Could you tell me more about what you’re feeling and when it started?"

    a = Message(
        thread_id=th.id,
        sender_role="assistant",
        content=assistant_text,
        confidence="med",
        risk_level=risk["risk_level"],
        risk_reason=risk["risk_reason"],
        risk_provenance=datetime.utcnow(),
        citations_json=[cite_span(pm.id, 0, min(len(text), 30))],
        created_at=datetime.utcnow(),
    )
    db.add(a)
    db.commit()
    db.refresh(a)

    await manager.broadcast_thread(
        th.id,
        {
            "type": "new_message",
            "message": serialize_message(a),
            "profile": profile_snapshot(db, u.id),
            "escalation_required": False,
        },
    )
    return {"ok": True, "escalation_required": False, "risk": risk, "profile": profile_snapshot(db, u.id)}


@app.post("/api/patient/message_audio")
async def post_message_audio(token: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    u = auth_user(token, db)
    if u.role != "patient":
        raise HTTPException(status_code=403, detail="patient only")

    audio = await file.read()
    asr = await transcribe_audio(audio, file.filename or "audio")
    transcript = (asr.get("transcript") or "").strip() or "[unintelligible audio]"

    # 复用文字入口：会走风险评估、LLM、以及 WS 推送
    return await post_message(SendMessageIn(text=transcript), token, db)


# -------------------------
# Clinician APIs
# -------------------------
@app.get("/api/clinician/tickets")
def clinician_tickets(token: str, db: Session = Depends(get_db)):
    u = auth_user(token, db)
    if u.role != "clinician":
        raise HTTPException(status_code=403, detail="clinician only")

    clinic_id = u.clinic_id or DEMO_CLINIC_ID
    ts = db.query(Ticket).filter_by(clinic_id=clinic_id, status="open").order_by(Ticket.created_at.desc()).all()
    return {"tickets": [serialize_ticket(t) for t in ts], "clinic_id": clinic_id}


@app.post("/api/clinician/reply")
async def clinician_reply(body: ClinicianReplyIn, token: str, db: Session = Depends(get_db)):
    u = auth_user(token, db)
    if u.role != "clinician":
        raise HTTPException(status_code=403, detail="clinician only")

    t = db.query(Ticket).filter_by(id=body.ticket_id).first()
    if not t or t.clinic_id != (u.clinic_id or DEMO_CLINIC_ID):
        raise HTTPException(status_code=404, detail="ticket not found")

    text = (body.text or "").strip()
    if not text:
        return {"ok": True}

    m = Message(
        thread_id=t.thread_id,
        sender_role="clinician",
        content=text,
        confidence="high",
        risk_level=t.risk_level,
        risk_reason="Clinician reply",
        risk_provenance=datetime.utcnow(),
        citations_json=[],
        is_ground_truth=True,
        created_at=datetime.utcnow(),
    )
    db.add(m)

    t.status = "closed"
    t.closed_at = datetime.utcnow()

    db.commit()
    db.refresh(m)

    upsert_memory(db, t.patient_id, m.id, text, source_is_clinician=True)

    # ✅ 推送给 patient 线程：病人端立刻能看到医生回复
    await manager.broadcast_thread(
        t.thread_id,
        {
            "type": "new_message",
            "message": serialize_message(m),
            "profile": profile_snapshot(db, t.patient_id),
            "escalation_required": False,
        },
    )

    await manager.broadcast_clinic(t.clinic_id, {"type": "ticket_closed", "ticket_id": t.id})
    return {"ok": True}


# -------------------------
# WebSockets
# -------------------------
@app.websocket("/ws/thread/{thread_id}")
async def ws_thread(ws: WebSocket, thread_id: int, token: str):
    db = SessionLocal()
    try:
        u = auth_user(token, db)
        if u.role != "patient":
            raise WebSocketDisconnect()
        th = ensure_thread(db, u)
        if th.id != thread_id:
            raise WebSocketDisconnect()

        await manager.connect_thread(thread_id, ws)
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    finally:
        db.close()


@app.websocket("/ws/clinic/{clinic_id}")
async def ws_clinic(ws: WebSocket, clinic_id: int, token: str):
    db = SessionLocal()
    try:
        u = auth_user(token, db)
        if u.role != "clinician" or (u.clinic_id or DEMO_CLINIC_ID) != clinic_id:
            raise WebSocketDisconnect()

        await manager.connect_clinic(clinic_id, ws)
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    finally:
        db.close()
