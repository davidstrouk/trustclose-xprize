"""TDD for the answer-or-defer decision gate (T-05).

This is the consequential decision in TrustClose: for each questionnaire
question the agent must decide whether to ANSWER (grounded in evidence) or
DEFER to a human. The cardinal rule is "never fabricate" — when in doubt, defer.
"""

from questionnaire.decision import (
    decide_action,
    evaluate_answer,
    ANSWER,
    DEFER,
    NEEDS_INPUT,
)


def test_answers_when_model_is_confident_and_can_answer():
    assert decide_action(can_answer=True, confidence=0.95) == ANSWER


def test_defers_when_model_cannot_answer_even_if_confident():
    # The cardinal rule: if the evidence does not support an answer, never fabricate one.
    assert decide_action(can_answer=False, confidence=0.99) == DEFER


def test_defers_when_confidence_below_threshold():
    assert decide_action(can_answer=True, confidence=0.4) == DEFER


def test_answers_exactly_at_threshold():
    # 0.6 is the accept boundary — at-threshold should answer, not defer.
    assert decide_action(can_answer=True, confidence=0.6) == ANSWER


def test_evaluate_defers_when_model_fields_missing():
    # Malformed/partial model output must degrade to defer, never to a fabricated answer.
    result = evaluate_answer({"answer": "Yes, AES-256"})
    assert result["action"] == DEFER


def test_evaluate_blanks_the_draft_when_deferring():
    # A wrong/unsupported draft must never leak into the exported questionnaire.
    result = evaluate_answer(
        {"can_answer": False, "confidence": 0.9, "answer": "Yes (hallucinated)"}
    )
    assert result["answer"] == NEEDS_INPUT


def test_evaluate_passes_through_a_grounded_answer():
    result = evaluate_answer(
        {
            "can_answer": True,
            "confidence": 0.95,
            "answer": "Yes, AES-256 at rest",
            "citation": "SOC2 4.1",
        }
    )
    assert result["action"] == ANSWER
    assert result["answer"] == "Yes, AES-256 at rest"
    assert result["citation"] == "SOC2 4.1"


def test_evaluate_defers_on_malformed_confidence():
    result = evaluate_answer({"can_answer": True, "confidence": "high", "answer": "Yes"})
    assert result["action"] == DEFER


def test_evaluate_defers_on_non_finite_confidence():
    # json.loads accepts NaN/Infinity; NaN < threshold is False and must not slip through as ANSWER.
    nan = float("nan")
    result = evaluate_answer({"can_answer": True, "confidence": nan, "answer": "Yes", "citation": "SOC2"})
    assert result["action"] == DEFER


def test_evaluate_defers_when_answer_text_is_missing():
    # can_answer=True + high confidence but NO answer text would export an empty "answered" cell.
    result = evaluate_answer({"can_answer": True, "confidence": 0.95, "citation": "SOC2"})
    assert result["action"] == DEFER
    assert result["answer"] == NEEDS_INPUT


def test_evaluate_defers_when_citation_is_missing():
    # An answer with no citation isn't grounded — defer rather than present an uncited claim.
    result = evaluate_answer({"can_answer": True, "confidence": 0.95, "answer": "Yes"})
    assert result["action"] == DEFER
