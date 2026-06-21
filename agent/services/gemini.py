"""Thin Vertex AI adapter — the ONLY I/O boundary in the answer pipeline.

Provides `generate(prompt) -> str` for `questionnaire.answerer.answer_question`.
No business logic lives here, so it is integration-tested against real Vertex AI
(requires GCP credentials) rather than unit-tested. The tested pipeline injects its
own `generate`, so this module is never imported by the test suite.

Verified google-genai (Vertex AI) syntax.
"""

import os

from google import genai  # noqa: E402  (optional dep; only needed in production wiring)
from google.genai import types

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=os.environ["GCP_PROJECT_ID"],
            location=os.environ.get("VERTEX_LOCATION", "us-central1"),
            http_options=types.HttpOptions(timeout=120_000),  # 120s, in milliseconds
        )
    return _client


def generate(prompt: str, model: str = "gemini-2.5-pro") -> str:
    resp = _get_client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,                       # deterministic for grounded answers
            response_mime_type="application/json",  # force clean JSON for the parser
        ),
    )
    return resp.text
