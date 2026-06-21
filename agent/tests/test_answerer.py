"""TDD for the T-05 answer pipeline.

The Gemini call is injected as `generate(prompt) -> str`, so the whole pipeline
(prompt -> model output -> safe decision record) is tested with zero SDK mocking.
The real SDK lives behind a trivial adapter (services/gemini.py).
"""

import json

from questionnaire.answerer import answer_question
from questionnaire.decision import ANSWER, DEFER, NEEDS_INPUT


def _fixed_generator(payload):
    def generate(_prompt):
        return payload

    return generate


def test_grounds_answer_from_model_output():
    generate = _fixed_generator(
        json.dumps(
            {
                "can_answer": True,
                "confidence": 0.95,
                "answer": "Yes, AES-256 at rest",
                "citation": "SOC2 4.1",
            }
        )
    )
    result = answer_question("Do you encrypt data at rest?", "<SOC2: AES-256 at rest>", generate)
    assert result["action"] == ANSWER
    assert result["answer"] == "Yes, AES-256 at rest"


def test_defers_when_model_output_is_unparseable():
    # If Gemini returns non-JSON, defer — never fabricate from garbage.
    generate = _fixed_generator("Sorry, I cannot help with that.")
    result = answer_question("Do you encrypt data at rest?", "<evidence>", generate)
    assert result["action"] == DEFER
    assert result["answer"] == NEEDS_INPUT


def test_passes_question_and_evidence_to_the_generator():
    seen = {}

    def generate(prompt):
        seen["prompt"] = prompt
        return json.dumps({"can_answer": False, "confidence": 0.0})

    answer_question("Is data encrypted?", "EVIDENCE-XYZ", generate)
    assert "Is data encrypted?" in seen["prompt"]
    assert "EVIDENCE-XYZ" in seen["prompt"]
