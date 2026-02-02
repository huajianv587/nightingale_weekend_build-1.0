
import hashlib
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import RequestFingerprint
from .audit import log_event

def stable_hash(v: str) -> str:
    return hashlib.sha256((v or "unknown").encode("utf-8")).hexdigest()

def check_and_record_ip(db: Session, ip: str, strike_on_every_request: bool=False):
    h=stable_hash(ip)
    fp=db.query(RequestFingerprint).filter_by(kind="ip", fingerprint_hash=h).first()
    now=datetime.utcnow()
    if not fp:
        fp=RequestFingerprint(kind="ip", fingerprint_hash=h, strikes=0, blocked_until=None, last_seen=now)
        db.add(fp); db.commit()
    if fp.blocked_until and fp.blocked_until > now:
        return False, fp.blocked_until
    if strike_on_every_request:
        fp.strikes += 1
        fp.last_seen = now
        if fp.strikes >= 200:
            fp.blocked_until = now + timedelta(minutes=10)
            log_event(db, "abuse_block", target_type="ip_hash", target_id=h[:12], meta={"strikes":fp.strikes})
        db.commit()
    return True, None
