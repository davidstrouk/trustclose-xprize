# TrustClose

An AI agent that answers inbound **security questionnaires** for SMB SaaS — grounding every
answer in your own evidence (SOC 2, policies, prior answers) and **deferring what it can't
prove instead of fabricating it**.

Built for the **Build with Gemini XPRIZE** — Gemini on Vertex AI + FastAPI, operated as an
AI-native service.

## The core guarantee: answer or defer

For each question the agent decides, *per question*, whether the evidence supports a grounded
answer (with a citation) or whether to flag `NEEDS YOUR INPUT`. A confident wrong answer on a
security questionnaire is worse than no answer — so low-confidence or unsupported questions
always defer to a human, and every decision is logged (the audit trail).

## Architecture

```
POST /questionnaires/answer   (upload .xlsx + customer_id)
  → parse_xlsx            normalized questions
  → answer_questionnaire  per-question answer-or-defer (Gemini), evidence-logged
  → export_xlsx           completed questionnaire in the original layout
```

| Module | Responsibility |
|---|---|
| `questionnaire/decision.py` | answer-or-defer gate (never-fabricate) |
| `questionnaire/answerer.py` | per-question Gemini pipeline (LLM injected) |
| `questionnaire/batch.py` | full-questionnaire orchestrator + evidence trail |
| `questionnaire/xlsx.py` | parse / export round-trip |
| `main.py` | FastAPI endpoint |
| `services/{gemini,firestore,bq_log}.py` | thin I/O adapters (Vertex AI, Firestore, BigQuery) |

External I/O (Gemini / Firestore / BigQuery) is **dependency-injected**, so the whole pipeline
is test-driven and the suite runs with no network or credentials.

## Run

```bash
python -m venv .venv && . .venv/bin/activate
pip install fastapi uvicorn python-multipart openpyxl google-genai pytest

pytest agent                       # the test suite (no network)

python agent/run_local.py          # local server with a stubbed LLM → http://127.0.0.1:8077

# against real Gemini (Vertex AI):
export GCP_PROJECT_ID=<project> VERTEX_LOCATION=us-central1 GOOGLE_CLOUD_QUOTA_PROJECT=<project>
```
