
import json, os
from datetime import datetime
from sqlalchemy.orm import Session
from .models import AuditEvent

AUDIT_PATH = os.getenv("AUDIT_PATH", "audit.log.jsonl")

def log_event(db: Session, event_type: str, actor_user_id=None, target_type=None, target_id=None, meta=None):
    meta = meta or {}
    evt = AuditEvent(event_type=event_type, actor_user_id=actor_user_id,
                     target_type=target_type, target_id=str(target_id) if target_id is not None else None,
                     meta_json=meta, created_at=datetime.utcnow())
    db.add(evt); db.commit()
    record = {"ts": datetime.utcnow().isoformat()+"Z", "event_type": event_type,
              "actor_user_id": actor_user_id, "target_type": target_type,
              "target_id": str(target_id) if target_id is not None else None,
              "meta": meta}
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
