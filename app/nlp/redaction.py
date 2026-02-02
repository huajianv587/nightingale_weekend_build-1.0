
import re
NRIC_RE = re.compile(r"\b[STFG]\d{7}[A-Z]\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(\+?65[\s-]?)?\b([689]\d{7})\b")
NAME_PHRASE_RE = re.compile(r"\b(my name is|i am|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")

def redact_no_phi(text: str) -> str:
    t = text
    t = NRIC_RE.sub("[REDACTED]", t)
    t = PHONE_RE.sub("[REDACTED]", t)
    t = NAME_PHRASE_RE.sub(lambda m: m.group(1) + " [REDACTED]", t)
    t = re.sub(r"\bJohn Doe\b", "[REDACTED]", t)
    return t
