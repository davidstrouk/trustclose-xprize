"""TDD for the batch orchestrator (T-05).

Runs a full questionnaire through the answer-or-defer pipeline. The Gemini call
(`generate`) and the evidence-log sink (`log`) are both injected, so the whole
orchestration is testable without the SDK or BigQuery.
"""

import json

from questionnaire.batch import answer_questionnaire
from questionnaire.decision import ANSWER, DEFER, NEEDS_INPUT


def _generator_for(answers_by_substring):
    """Return a generate(prompt) that picks canned JSON by matching the question text."""

    def generate(prompt):
        for needle, payload in answers_by_substring.items():
            if needle in prompt:
                return json.dumps(payload)
        return "not json"  # unknown question -> unparseable -> defer

    return generate


def test_answers_each_question_and_preserves_identity():
    questions = [
        {"row": 2, "question": "Do you encrypt data at rest?"},
        {"row": 3, "question": "Do you have an incident response plan?"},
    ]
    generate = _generator_for(
        {
            "encrypt data at rest": {
                "can_answer": True,
                "confidence": 0.95,
                "answer": "Yes, AES-256",
                "citation": "SOC2 4.1",
            },
            "incident response plan": {
                "can_answer": True,
                "confidence": 0.9,
                "answer": "Yes",
                "citation": "IRP v2",
            },
        }
    )

    run = answer_questionnaire(questions, "<evidence>", generate)

    assert run["total"] == 2
    assert run["answered"] == 2
    assert run["deferred"] == 0
    assert run["results"][0]["row"] == 2
    assert run["results"][0]["question"] == "Do you encrypt data at rest?"
    assert run["results"][0]["answer"] == "Yes, AES-256"


def test_counts_answered_and_deferred_for_a_mix():
    questions = [
        {"row": 2, "question": "Do you encrypt data at rest?"},
        {"row": 3, "question": "Do you do annual penetration testing?"},
    ]
    generate = _generator_for(
        {
            "encrypt data at rest": {
                "can_answer": True,
                "confidence": 0.95,
                "answer": "Yes, AES-256",
                "citation": "SOC2",
            },
            "penetration testing": {"can_answer": False, "confidence": 0.2, "answer": "maybe"},
        }
    )

    run = answer_questionnaire(questions, "<evidence>", generate)

    assert run["answered"] == 1
    assert run["deferred"] == 1
    deferred = [r for r in run["results"] if r["action"] == DEFER][0]
    assert deferred["answer"] == NEEDS_INPUT


def test_logs_one_decision_per_question_to_the_evidence_sink():
    questions = [
        {"row": 2, "question": "Do you encrypt data at rest?"},
        {"row": 3, "question": "Do you do annual penetration testing?"},
    ]
    generate = _generator_for(
        {
            "encrypt data at rest": {
                "can_answer": True,
                "confidence": 0.95,
                "answer": "Yes",
                "citation": "SOC2",
            },
            "penetration testing": {"can_answer": False, "confidence": 0.2},
        }
    )
    logged = []

    answer_questionnaire(questions, "<evidence>", generate, log=logged.append)

    assert len(logged) == 2
    assert {entry["action"] for entry in logged} == {ANSWER, DEFER}
    assert logged[0]["question"] == "Do you encrypt data at rest?"


def test_a_throwing_generator_defers_that_question_without_killing_the_run():
    questions = [
        {"row": 2, "question": "Do you encrypt data at rest?"},
        {"row": 3, "question": "Boom question"},
    ]

    def generate(prompt):
        if "Boom" in prompt:
            raise RuntimeError("Vertex API timeout")
        return json.dumps(
            {"can_answer": True, "confidence": 0.95, "answer": "Yes", "citation": "SOC2"}
        )

    run = answer_questionnaire(questions, "<evidence>", generate)

    assert run["answered"] == 1
    assert run["deferred"] == 1
    boom = [r for r in run["results"] if r["row"] == 3][0]
    assert boom["action"] == DEFER
    assert boom["answer"] == NEEDS_INPUT


def test_empty_questionnaire_returns_a_zeroed_run():
    logged = []
    run = answer_questionnaire([], "<evidence>", lambda _p: "{}", log=logged.append)
    assert run == {"results": [], "total": 0, "answered": 0, "deferred": 0}
    assert logged == []
