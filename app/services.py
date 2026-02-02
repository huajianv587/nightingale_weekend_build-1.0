
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, List
from .models import MemoryItem, Ticket
from .nlp.memory import extract_memory_facts
from .config import USE_LLM_TRIAGE
from .llm.ollama import ollama_generate

def upsert_memory(db: Session, patient_id: int, message_id: int, text: str, source_is_clinician: bool=False):
    facts = extract_memory_facts(text)
    for f in facts:
        kind=f["kind"]; value=f["value"].strip(); status=f["status"]; timeline=f.get("timeline_text")
        start,end=f["span"]
        if kind=="chief_complaint":
            prev=db.query(MemoryItem).filter_by(patient_id=patient_id, kind="chief_complaint", status="active").all()
            for p in prev: p.status="resolved"
            db.add(MemoryItem(patient_id=patient_id, kind=kind, value=value, status="active",
                              timeline_text=timeline, provenance_message_id=message_id,
                              provenance_start=start, provenance_end=end, updated_at=datetime.utcnow()))
            continue
        if kind=="medication" and status=="stopped":
            act=db.query(MemoryItem).filter_by(patient_id=patient_id, kind="medication", value=value, status="active").all()
            for a in act:
                a.status="stopped"; a.timeline_text=timeline or a.timeline_text
                a.provenance_message_id=message_id; a.provenance_start=start; a.provenance_end=end
            if not act:
                db.add(MemoryItem(patient_id=patient_id, kind="medication", value=value, status="stopped",
                                  timeline_text=timeline, provenance_message_id=message_id,
                                  provenance_start=start, provenance_end=end, updated_at=datetime.utcnow()))
            continue
        ex=db.query(MemoryItem).filter_by(patient_id=patient_id, kind=kind, value=value, status="active").first()
        if ex:
            ex.updated_at=datetime.utcnow()
            ex.provenance_message_id=message_id; ex.provenance_start=start; ex.provenance_end=end
            continue
        db.add(MemoryItem(patient_id=patient_id, kind=kind, value=value, status="active",
                          timeline_text=timeline, provenance_message_id=message_id,
                          provenance_start=start, provenance_end=end, updated_at=datetime.utcnow()))
    db.commit()

def profile_snapshot(db: Session, patient_id: int) -> Dict:
    items=db.query(MemoryItem).filter_by(patient_id=patient_id).all()
    out={"chief_complaint":None,"symptoms":[],"medications":[],"allergies":[]}
    cc=[i for i in items if i.kind=="chief_complaint" and i.status=="active"]
    if cc:
        cc.sort(key=lambda x: x.updated_at, reverse=True)
        out["chief_complaint"]=cc[0].value
    for i in items:
        if i.kind=="symptom" and i.status=="active":
            out["symptoms"].append({"value":i.value,"timeline":i.timeline_text,"prov":prov(i)})
        if i.kind=="medication":
            out["medications"].append({"value":i.value,"status":i.status,"timeline":i.timeline_text,"prov":prov(i)})
        if i.kind=="allergy" and i.status=="active":
            out["allergies"].append({"value":i.value,"prov":prov(i)})
    return out

def prov(i: MemoryItem) -> Dict:
    return {"message_id": i.provenance_message_id, "start": i.provenance_start, "end": i.provenance_end}

async def triage_summary(db: Session, patient_id: int, trigger: str) -> List[str]:
    snap=profile_snapshot(db, patient_id)
    bullets=[]
    if snap.get("chief_complaint"): bullets.append(f"Chief complaint: {snap['chief_complaint']}")
    if snap.get("symptoms"): bullets.append("Symptoms: " + ", ".join([s["value"] for s in snap["symptoms"]][:5]))
    if snap.get("medications"):
        bullets.append("Meds: " + ", ".join([f"{m['value']} ({m['status']})" for m in snap["medications"]][:5]))
    if snap.get("allergies"): bullets.append("Allergies: " + ", ".join([a["value"] for a in snap["allergies"]][:5]))
    bullets.append("Trigger: " + trigger[:120])
    bullets=bullets[:5]
    if not USE_LLM_TRIAGE:
        return bullets
    prompt=("You assist clinic triage. 3-5 bullets. No diagnosis, no med changes, no treatment plans. "
            f"Patient message: {trigger}\nProfile JSON: {snap}\nReturn bullets only, one per line.")
    try:
        resp=await ollama_generate(prompt)
        lines=[ln.strip("-• ").strip() for ln in resp.splitlines() if ln.strip()]
        lines=[ln for ln in lines if len(ln)<=160][:5]
        return lines if lines else bullets
    except Exception:
        return bullets

async def create_ticket(db: Session, clinic_id: int, patient_id: int, thread_id: int, triggering_message_id: int, risk_level: str, triggering_text: str):
    summary=await triage_summary(db, patient_id, triggering_text)
    snap=profile_snapshot(db, patient_id)
    t=Ticket(clinic_id=clinic_id, patient_id=patient_id, thread_id=thread_id,
             status="open", triggering_message_id=triggering_message_id,
             risk_level=risk_level, triage_summary_json=summary, profile_snapshot_json=snap,
             created_at=datetime.utcnow(), closed_at=None)
    db.add(t); db.commit(); db.refresh(t)
    return t
