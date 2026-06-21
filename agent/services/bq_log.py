"""Thin BigQuery adapter — untested I/O boundary (needs GCP credentials).

Provides `log_decision(record)` used by the batch orchestrator as its `log` sink:
every answer-or-defer decision is appended to the agent_decisions evidence table —
the AI-Native-Operations audit trail the XPRIZE submission requires. No logic here.
"""

import os

from google.cloud import bigquery

_bq = None


def _client():
    global _bq
    if _bq is None:
        _bq = bigquery.Client()
    return _bq


def _table():
    dataset = os.environ.get("BIGQUERY_DATASET", "trustclose")
    return f"{os.environ['GCP_PROJECT_ID']}.{dataset}.agent_decisions"


def log_decision(record):
    _client().insert_rows_json(_table(), [record])
