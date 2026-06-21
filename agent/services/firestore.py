"""Thin Firestore adapter — untested I/O boundary (needs GCP credentials).

Provides `all_evidence_text(customer_id) -> str` for the answer pipeline. MVP strategy:
concatenate a customer's stored evidence for Gemini's long context (swap for retrieval
only when one customer's evidence outgrows the window). No business logic lives here.
"""

import os

from google.cloud import firestore

_db = None


def _client():
    global _db
    if _db is None:
        _db = firestore.Client(project=os.environ["GCP_PROJECT_ID"])
    return _db


def put_evidence(customer_id, doc_id, text):
    (
        _client()
        .collection("customers")
        .document(customer_id)
        .collection("evidence")
        .document(doc_id)
        .set({"text": text})
    )


def all_evidence_text(customer_id):
    docs = (
        _client().collection("customers").document(customer_id).collection("evidence").stream()
    )
    return "\n\n".join(d.to_dict().get("text", "") for d in docs)


def get_account(customer_id):
    data = _client().collection("customers").document(customer_id).get().to_dict() or {}
    return {
        "questionnaires_used": int(data.get("questionnaires_used", 0)),
        "is_paid": bool(data.get("is_paid", False)),
    }


def record_usage(customer_id):
    _client().collection("customers").document(customer_id).set(
        {"questionnaires_used": firestore.Increment(1)}, merge=True
    )


def mark_paid(customer_id, is_paid=True):
    _client().collection("customers").document(customer_id).set({"is_paid": is_paid}, merge=True)
