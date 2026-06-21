"""Local dev launcher — runs the REAL FastAPI app with the I/O boundary stubbed.

No GCP needed: the injected Gemini/evidence/log providers are overridden with local
stubs so the full router -> parse -> answer-or-defer -> export path runs over real HTTP.
The 'generate' stub is deliberately grounded (answers only when the evidence supports
the question), so deferrals are real, not faked.

    ../../.venv/bin/python run_local.py   # serves on http://127.0.0.1:8077
"""

import json

import uvicorn

from main import (
    app,
    get_checkout_link,
    get_evidence_provider,
    get_generate,
    get_logger,
    get_reserve,
)

EVIDENCE = {
    "acme": (
        "SOC2 Type II report. All customer data is encrypted at rest using AES-256. "
        "Multi-factor authentication (MFA) is enforced for all employee accounts. "
        "Daily automated backups are taken and retained for 30 days."
    ),
}


def local_generate(prompt: str) -> str:
    question = prompt.rsplit("QUESTION:", 1)[-1].lower()
    # Scan only the evidence section (before "QUESTION:"), not the question itself —
    # otherwise a keyword in the question alone would falsely satisfy the grounding check.
    evidence = prompt.rsplit("QUESTION:", 1)[0].lower()

    if "encrypt" in question and "aes-256" in evidence:
        return json.dumps(
            {
                "can_answer": True,
                "confidence": 0.96,
                "answer": "Yes - all customer data is encrypted at rest with AES-256.",
                "citation": "SOC2 Type II: AES-256 at rest",
            }
        )
    if ("mfa" in question or "multi-factor" in question) and (
        "mfa" in evidence or "multi-factor" in evidence
    ):
        return json.dumps(
            {
                "can_answer": True,
                "confidence": 0.9,
                "answer": "Yes - MFA is enforced for all employee accounts.",
                "citation": "SOC2 Type II: MFA enforced",
            }
        )
    if "backup" in question and "backup" in evidence:
        return json.dumps(
            {
                "can_answer": True,
                "confidence": 0.88,
                "answer": "Yes - daily automated backups are retained for 30 days.",
                "citation": "SOC2 Type II: daily backups",
            }
        )
    # No supporting evidence -> defer to a human, never fabricate.
    return json.dumps({"can_answer": False, "confidence": 0.2})


def local_evidence_provider():
    return lambda customer_id: EVIDENCE.get(customer_id, "")


def local_log_sink():
    def log(record):
        print(
            f"[evidence-log] {record['action'].upper():6} conf={record['confidence']:.2f} "
            f":: {record['question'][:48]!r}"
        )

    return log


# In-memory billing state so the local demo shows the free-first -> 402 flow with no GCP/Stripe.
_LOCAL_USAGE = {}


def local_reserve():
    from billing.entitlement import FREE_LIMIT

    def reserve(customer_id):
        used = _LOCAL_USAGE.get(customer_id, 0)
        if used >= FREE_LIMIT:
            return {"allowed": False, "is_paid": False}
        _LOCAL_USAGE[customer_id] = used + 1
        return {"allowed": True, "is_paid": False}

    return reserve


def local_checkout_link():
    return lambda customer_id: f"https://stripe.local/checkout/{customer_id}"


app.dependency_overrides[get_generate] = lambda: local_generate
app.dependency_overrides[get_evidence_provider] = local_evidence_provider
app.dependency_overrides[get_logger] = local_log_sink
app.dependency_overrides[get_reserve] = local_reserve
app.dependency_overrides[get_checkout_link] = local_checkout_link


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8077, log_level="warning")
