from fastapi import Depends, FastAPI, File, Form, Response, UploadFile

from questionnaire.batch import answer_questionnaire
from questionnaire.xlsx import export_xlsx, parse_xlsx

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

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


@app.post("/questionnaires/answer")
async def answer_questionnaire_endpoint(
    customer_id: str = Form(...),
    file: UploadFile = File(...),
    generate=Depends(get_generate),
    evidence_provider=Depends(get_evidence_provider),
    log=Depends(get_logger),
):
    file_bytes = await file.read()
    questions = parse_xlsx(file_bytes)
    evidence_text = evidence_provider(customer_id)
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
