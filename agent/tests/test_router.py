"""TDD for the FastAPI router.

Uses TestClient + FastAPI dependency-override so the full HTTP path
(upload -> parse -> answer -> export) is exercised with fakes injected only at the
I/O boundary (Gemini, the evidence source, the log sink). No SDK, no network.
"""

import io
import json

import openpyxl
from fastapi.testclient import TestClient

from main import app, get_generate, get_evidence_provider, get_logger


def _xlsx(questions):
    wb = openpyxl.Workbook()
    ws = wb.active
    for i, q in enumerate(questions, start=1):
        ws[f"A{i}"] = q
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _post(client, book, customer_id="acme"):
    return client.post(
        "/questionnaires/answer",
        data={"customer_id": customer_id},
        files={
            "file": (
                "q.xlsx",
                book,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )


def test_endpoint_passes_customer_id_to_evidence_provider():
    seen = {}

    def evidence(customer_id):
        seen["customer_id"] = customer_id
        return "evidence"

    app.dependency_overrides[get_generate] = lambda: (
        lambda _p: json.dumps({"can_answer": False, "confidence": 0.0})
    )
    app.dependency_overrides[get_evidence_provider] = lambda: evidence
    app.dependency_overrides[get_logger] = lambda: (lambda _record: None)
    try:
        client = TestClient(app)
        resp = _post(client, _xlsx(["Do you have MFA?"]), customer_id="acme-42")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert seen["customer_id"] == "acme-42"


def test_endpoint_returns_completed_xlsx_with_counts_and_logs_decisions():
    logged = []

    def fake_generate(prompt):
        if "encrypt" in prompt:
            return json.dumps(
                {"can_answer": True, "confidence": 0.95, "answer": "Yes, AES-256", "citation": "SOC2"}
            )
        return json.dumps({"can_answer": False, "confidence": 0.1})

    app.dependency_overrides[get_generate] = lambda: fake_generate
    app.dependency_overrides[get_evidence_provider] = lambda: (lambda _cid: "<evidence>")
    app.dependency_overrides[get_logger] = lambda: logged.append
    try:
        client = TestClient(app)
        resp = _post(client, _xlsx(["Do you encrypt data at rest?", "Do you do annual pentests?"]))
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.headers["x-total"] == "2"
    assert resp.headers["x-answered"] == "1"
    assert resp.headers["x-deferred"] == "1"

    ws = openpyxl.load_workbook(io.BytesIO(resp.content)).active
    assert ws["B1"].value == "Yes, AES-256"
    assert ws["B2"].value == "NEEDS YOUR INPUT"  # deferred row flagged for a human
    assert len(logged) == 2  # full evidence trail captured
