
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Enum, Boolean, ForeignKey, JSON, UniqueConstraint, Index
from datetime import datetime
from .db import Base

ROLE_ENUM=("patient","clinician")
SENDER_ENUM=("patient","assistant","clinician","system")
RISK_ENUM=("low","medium","high")
CONF_ENUM=("low","med","high")
MEM_KIND=("chief_complaint","symptom","medication","allergy")
MEM_STATUS=("active","stopped","resolved","unknown")
TICKET_STATUS=("open","closed")
FP_KIND=("ip","device","phone")

class User(Base):
    __tablename__="users"
    id=Column(BigInteger, primary_key=True)
    email=Column(String(255), unique=True, nullable=False)
    password_hash=Column(String(255), nullable=False)
    role=Column(Enum(*ROLE_ENUM, name="role_enum"), nullable=False)
    clinic_id=Column(BigInteger, nullable=True)
    created_at=Column(DateTime, default=datetime.utcnow, nullable=False)

class Thread(Base):
    __tablename__="threads"
    id=Column(BigInteger, primary_key=True)
    patient_id=Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    clinic_id=Column(BigInteger, nullable=True)
    created_at=Column(DateTime, default=datetime.utcnow, nullable=False)

class Message(Base):
    __tablename__="messages"
    id=Column(BigInteger, primary_key=True)
    thread_id=Column(BigInteger, ForeignKey("threads.id", ondelete="CASCADE"), index=True, nullable=False)
    sender_role=Column(Enum(*SENDER_ENUM, name="sender_enum"), nullable=False)
    content=Column(Text, nullable=False)
    redacted_for_llm=Column(Text, nullable=True)
    confidence=Column(Enum(*CONF_ENUM, name="conf_enum"), nullable=True)
    risk_level=Column(Enum(*RISK_ENUM, name="risk_enum"), nullable=True)
    risk_reason=Column(String(255), nullable=True)
    risk_provenance=Column(DateTime, nullable=True)
    citations_json=Column(JSON, nullable=True)
    is_ground_truth=Column(Boolean, default=False, nullable=False)
    audio_asset_id=Column(String(255), nullable=True)
    audio_transcript_id=Column(String(255), nullable=True)
    created_at=Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__=(Index("idx_messages_thread_created","thread_id","created_at"),)

class MemoryItem(Base):
    __tablename__="memory_items"
    id=Column(BigInteger, primary_key=True)
    patient_id=Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kind=Column(Enum(*MEM_KIND, name="mem_kind_enum"), nullable=False)
    value=Column(String(255), nullable=False)
    status=Column(Enum(*MEM_STATUS, name="mem_status_enum"), default="active", nullable=False)
    timeline_text=Column(String(255), nullable=True)
    provenance_message_id=Column(BigInteger, nullable=False)
    provenance_start=Column(Integer, default=0, nullable=False)
    provenance_end=Column(Integer, default=0, nullable=False)
    updated_at=Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Ticket(Base):
    __tablename__="tickets"
    id=Column(BigInteger, primary_key=True)
    clinic_id=Column(BigInteger, index=True, nullable=False)
    patient_id=Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    thread_id=Column(BigInteger, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    status=Column(Enum(*TICKET_STATUS, name="ticket_status_enum"), default="open", index=True, nullable=False)
    triggering_message_id=Column(BigInteger, nullable=False)
    risk_level=Column(Enum("medium","high", name="ticket_risk_enum"), nullable=False)
    triage_summary_json=Column(JSON, nullable=False)
    profile_snapshot_json=Column(JSON, nullable=False)
    created_at=Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at=Column(DateTime, nullable=True)
    __table_args__=(Index("idx_tickets_clinic_status","clinic_id","status","created_at"),)

class AuditEvent(Base):
    __tablename__="audit_events"
    id=Column(BigInteger, primary_key=True)
    event_type=Column(String(64), nullable=False)
    actor_user_id=Column(BigInteger, nullable=True)
    target_type=Column(String(64), nullable=True)
    target_id=Column(String(64), nullable=True)
    meta_json=Column(JSON, nullable=True)
    created_at=Column(DateTime, default=datetime.utcnow, nullable=False)

class RequestFingerprint(Base):
    __tablename__="request_fingerprints"
    id=Column(BigInteger, primary_key=True)
    kind=Column(Enum(*FP_KIND, name="fp_kind_enum"), nullable=False)
    fingerprint_hash=Column(String(64), nullable=False)
    strikes=Column(Integer, default=0, nullable=False)
    blocked_until=Column(DateTime, nullable=True)
    last_seen=Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__=(UniqueConstraint("kind","fingerprint_hash", name="uniq_kind_hash"),)
