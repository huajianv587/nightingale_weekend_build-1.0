
import re
from typing import List, Dict, Tuple

MED_TAKE_RE = re.compile(r"\b(i\s+(?:take|am taking|use)\s+)([A-Za-z][A-Za-z0-9\- ]{1,40})\b", re.IGNORECASE)
MED_STOP_RE = re.compile(r"\b(i\s+(?:stopped|stop|no longer take)\s+)([A-Za-z][A-Za-z0-9\- ]{1,40})(?:\s+(.*))?$", re.IGNORECASE)
ALLERGY_RE = re.compile(r"\b(i\s+(?:am|i'm|im)\s+allergic\s+to\s+)([A-Za-z][A-Za-z0-9\- ]{1,40})\b", re.IGNORECASE)
SYMPTOM_RE = re.compile(r"\b(i\s+have\s+)([a-z][a-z \-]{2,60})\b", re.IGNORECASE)

def _span(text: str, phrase: str) -> Tuple[int,int]:
    idx = text.lower().find(phrase.lower())
    if idx < 0: return (0, min(len(text), 20))
    return (idx, min(len(text), idx+len(phrase)))

def extract_memory_facts(text: str) -> List[Dict]:
    facts=[]
    m=SYMPTOM_RE.search(text)
    if m:
        symptom=m.group(2).strip().strip(".")
        s,e=_span(text,m.group(0))
        facts.append({"kind":"chief_complaint","value":symptom,"status":"active","timeline_text":None,"span":(s,e)})
        facts.append({"kind":"symptom","value":symptom,"status":"active","timeline_text":None,"span":(s,e)})
    for m in MED_TAKE_RE.finditer(text):
        med=m.group(2).strip().strip(".")
        s,e=_span(text,m.group(0))
        facts.append({"kind":"medication","value":med,"status":"active","timeline_text":None,"span":(s,e)})
    m=MED_STOP_RE.search(text)
    if m:
        med=m.group(2).strip().strip(".")
        timeline=(m.group(3) or "").strip()[:120] or None
        s,e=_span(text,m.group(0))
        facts.append({"kind":"medication","value":med,"status":"stopped","timeline_text":timeline,"span":(s,e)})
    for m in ALLERGY_RE.finditer(text):
        a=m.group(2).strip().strip(".")
        s,e=_span(text,m.group(0))
        facts.append({"kind":"allergy","value":a,"status":"active","timeline_text":None,"span":(s,e)})
    return facts
