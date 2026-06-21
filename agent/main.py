import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile

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


# Synchronous on purpose: FastAPI runs sync path operations in a threadpool, so the blocking
# openpyxl/Gemini/Firestore/BigQuery calls below don't block the event loop or serialize requests.
@app.post("/questionnaires/answer")
def answer_questionnaire_endpoint(
    customer_id: str = Form(...),
    file: UploadFile = File(...),
    generate=Depends(get_generate),
    evidence_provider=Depends(get_evidence_provider),
    log_sink=Depends(get_logger),
):
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
