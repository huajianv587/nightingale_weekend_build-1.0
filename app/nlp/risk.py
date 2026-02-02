
from datetime import datetime
HIGH=["crushing chest pain","radiating","shortness of breath","can't breathe","vomiting blood","severe bleeding","suicidal"]
MED=["worsening","getting worse","high fever","fever","pregnant","severe pain","confused","dizzy","tightness"]

def assess_risk(text: str):
    t=text.lower()
    for kw in HIGH:
        if kw in t or ("chest pain" in t and "crushing" in t):
            return {"risk_level":"high","risk_reason":f"Detected high-risk indicator: '{kw if kw in t else 'chest pain'}'.",
                    "risk_provenance": datetime.utcnow().isoformat()+"Z"}
    for kw in MED:
        if kw in t:
            return {"risk_level":"medium","risk_reason":f"Detected potentially concerning indicator: '{kw}'.",
                    "risk_provenance": datetime.utcnow().isoformat()+"Z"}
    return {"risk_level":"low","risk_reason":"No high-risk indicators detected.",
            "risk_provenance": datetime.utcnow().isoformat()+"Z"}
