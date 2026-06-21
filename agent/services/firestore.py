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
