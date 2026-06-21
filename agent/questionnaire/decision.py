import math

ANSWER = "answer"
DEFER = "defer"
NEEDS_INPUT = "NEEDS YOUR INPUT"

DEFAULT_THRESHOLD = 0.6


def decide_action(can_answer, confidence, threshold=DEFAULT_THRESHOLD):
    # Never fabricate: an answer the evidence does not support always defers to a human.
    if not can_answer:
        return DEFER
    # A low-confidence answer defers rather than risk a wrong claim on a security questionnaire.
    if confidence < threshold:
        return DEFER
    return ANSWER


def _is_real_number(value):
    # bool is a subclass of int in Python; exclude it so True/False can't pass as confidence.
    # Reject NaN/Infinity too: json.loads accepts them and `nan < threshold` is False,
    # which would otherwise let a non-finite confidence slip through as an ANSWER.
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def evaluate_answer(model_response, threshold=DEFAULT_THRESHOLD):
    """Normalize a raw model response into a safe decision record.

    Malformed or partial model output (missing/typed-wrong fields) degrades to DEFER,
    and any deferred answer is blanked to NEEDS_INPUT so a wrong draft can never leak
    into the exported questionnaire.
    """
    can_answer = model_response.get("can_answer")
    confidence = model_response.get("confidence")
    answer = model_response.get("answer")
    citation = model_response.get("citation")

    # A grounded answer needs both non-empty answer text and a citation; without either,
    # an "ANSWER" would export an empty or uncited cell, so degrade to DEFER.
    grounded = _is_nonempty_text(answer) and _is_nonempty_text(citation)

    if not isinstance(can_answer, bool) or not _is_real_number(confidence) or not grounded:
        action = DEFER
    else:
        action = decide_action(can_answer, confidence, threshold)

    answering = action == ANSWER
    return {
        "action": action,
        "answer": answer if answering else NEEDS_INPUT,
        "citation": citation if answering else "",
        "confidence": confidence if _is_real_number(confidence) else 0.0,
    }
