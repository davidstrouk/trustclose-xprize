import json

from questionnaire.decision import evaluate_answer, DEFER, NEEDS_INPUT

_PROMPT = (
    "You answer security questionnaires using ONLY the provided evidence.\n"
    'Return JSON: {{"answer", "citation", "confidence" (0-1), "can_answer" (bool)}}.\n'
    "If the evidence does not support an answer, set can_answer=false. Never fabricate.\n\n"
    "EVIDENCE:\n{evidence}\n\nQUESTION: {question}"
)

_DEFERRED = {"action": DEFER, "answer": NEEDS_INPUT, "citation": "", "confidence": 0.0}


def answer_question(question, evidence_text, generate):
    """Run one questionnaire question through the answer-or-defer pipeline.

    `generate(prompt) -> str` is injected (the real Gemini call lives behind it),
    so this pipeline is fully testable without the SDK. Any unparseable or non-object
    model output safely degrades to a deferred, blanked record.
    """
    prompt = _PROMPT.format(evidence=evidence_text, question=question)
    try:
        model_response = json.loads(generate(prompt))
    except (json.JSONDecodeError, TypeError):
        return dict(_DEFERRED)
    if not isinstance(model_response, dict):
        return dict(_DEFERRED)
    return evaluate_answer(model_response)
