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
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def evaluate_answer(model_response, threshold=DEFAULT_THRESHOLD):
    """Normalize a raw model response into a safe decision record.

    Malformed or partial model output (missing/typed-wrong fields) degrades to DEFER,
    and any deferred answer is blanked to NEEDS_INPUT so a wrong draft can never leak
    into the exported questionnaire.
    """
    can_answer = model_response.get("can_answer")
    confidence = model_response.get("confidence")

    if not isinstance(can_answer, bool) or not _is_real_number(confidence):
        action = DEFER
    else:
        action = decide_action(can_answer, confidence, threshold)

    answering = action == ANSWER
    return {
        "action": action,
        "answer": model_response.get("answer", "") if answering else NEEDS_INPUT,
        "citation": model_response.get("citation", "") if answering else "",
        "confidence": confidence if _is_real_number(confidence) else 0.0,
    }
