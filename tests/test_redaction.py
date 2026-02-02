
from app.nlp.redaction import redact_no_phi

def test_redaction():
    inp = "My name is John Doe and my IC is S1234567A."
    out = redact_no_phi(inp)
    assert "[REDACTED]" in out
    assert "S1234567A" not in out
    assert "John Doe" not in out
