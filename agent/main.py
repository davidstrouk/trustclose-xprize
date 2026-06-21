import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile

from billing.entitlement import requires_payment
from questionnaire.batch import answer_questionnaire
from questionnaire.xlsx import QuestionnaireParseError, export_xlsx, parse_xlsx

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — openpyxl loads the whole workbook, so cap the upload

app = FastAPI(title="TrustClose")


# Dependency providers — overridden in tests; lazily import the real I/O adapters in prod
# so the app stays importable without the GCP SDKs installed.
def get_generate():
    from services.gemini import generate

    return generate


def get_evidence_provider():
    from services.firestore import all_evidence_text

    return all_evidence_text


def get_logger():
    from services.bq_log import log_decision

    return log_decision


def get_account():
    from services.firestore import get_account as _get_account

    return _get_account


def get_usage_recorder():
    from services.firestore import record_usage

    return record_usage


def get_checkout_link():
    from services.stripe_billing import create_checkout_url

    return create_checkout_url


def get_webhook_parser():
    from services.stripe_billing import paid_customer_from_event

    return paid_customer_from_event


def get_mark_paid():
    from services.firestore import mark_paid

    return mark_paid


# Synchronous on purpose: FastAPI runs sync path operations in a threadpool, so the blocking
# openpyxl/Gemini/Firestore/BigQuery calls below don't block the event loop or serialize requests.
@app.post("/questionnaires/answer")
def answer_questionnaire_endpoint(
    customer_id: str = Form(...),
    file: UploadFile = File(...),
    generate=Depends(get_generate),
    evidence_provider=Depends(get_evidence_provider),
    log_sink=Depends(get_logger),
    account_provider=Depends(get_account),
    record_usage=Depends(get_usage_recorder),
    checkout_link=Depends(get_checkout_link),
):
    # NOTE: the read here and the record_usage() increment below are not atomic, so concurrent
    # requests for the same unpaid customer can both pass the gate (bounded: free limit is small).
    # The authoritative fix is a Firestore transaction (atomic check-and-increment), landing with
    # the live-billing wiring where it can be integration-tested against real Firestore.
    account = account_provider(customer_id)
    if requires_payment(account["questionnaires_used"], account["is_paid"]):
        raise HTTPException(
            status_code=402,
            detail={
                "message": "Free quota used — subscribe to answer more questionnaires.",
                "checkout_url": checkout_link(customer_id),
            },
        )

    file_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Questionnaire file too large (max 10 MB).")
    try:
        questions = parse_xlsx(file_bytes)
    except QuestionnaireParseError as exc:
        raise HTTPException(
            status_code=400, detail="Upload is not a valid .xlsx questionnaire."
        ) from exc
    evidence_text = evidence_provider(customer_id)

    run_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()

    def log(record):
        log_sink({**record, "run_id": run_id, "customer_id": customer_id, "created_at": created_at})

    run = answer_questionnaire(questions, evidence_text, generate, log=log)
    completed = export_xlsx(file_bytes, run["results"])
    record_usage(customer_id)
    return Response(
        content=completed,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "X-Total": str(run["total"]),
            "X-Answered": str(run["answered"]),
            "X-Deferred": str(run["deferred"]),
            "Content-Disposition": 'attachment; filename="completed.xlsx"',
        },
    )


@app.post("/billing/checkout")
def billing_checkout(
    customer_id: str = Form(...),
    checkout_link=Depends(get_checkout_link),
):
    return {"checkout_url": checkout_link(customer_id)}


@app.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    parse_event=Depends(get_webhook_parser),
    mark_paid=Depends(get_mark_paid),
):
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        customer_id = parse_event(payload, signature)
    except Exception as exc:
        # construct_event raises on an invalid signature/payload — return 400 so Stripe
        # stops retrying and the failure is logged as client-side, not a server error.
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook.") from exc
    if customer_id:
        mark_paid(customer_id)
    return {"received": True}
