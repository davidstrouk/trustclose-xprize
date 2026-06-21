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


def reserve_questionnaire(customer_id, free_limit=None):
    """Atomically check entitlement and consume one free use if allowed.

    Runs in a Firestore transaction so two concurrent requests for the same unpaid
    customer cannot both pass the free-quota gate. Returns {"allowed", "is_paid"}.
    """
    from billing.entitlement import FREE_LIMIT, requires_payment

    limit = FREE_LIMIT if free_limit is None else free_limit
    db = _client()
    ref = db.collection("customers").document(customer_id)

    @firestore.transactional
    def _reserve(transaction):
        data = ref.get(transaction=transaction).to_dict() or {}
        used = int(data.get("questionnaires_used", 0))
        is_paid = bool(data.get("is_paid", False))
        if requires_payment(used, is_paid, limit):
            return {"allowed": False, "is_paid": is_paid}
        if not is_paid:
            transaction.set(ref, {"questionnaires_used": used + 1}, merge=True)
        return {"allowed": True, "is_paid": is_paid}

    return _reserve(db.transaction())


def mark_paid(customer_id, is_paid=True):
    _client().collection("customers").document(customer_id).set({"is_paid": is_paid}, merge=True)
