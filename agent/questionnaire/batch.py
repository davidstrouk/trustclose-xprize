from questionnaire.answerer import answer_question
from questionnaire.decision import ANSWER, DEFER, NEEDS_INPUT

_DEFERRED = {"action": DEFER, "answer": NEEDS_INPUT, "citation": "", "confidence": 0.0}


def answer_questionnaire(questions, evidence_text, generate, log=None):
    results = []
    answered = 0
    for q in questions:
        try:
            ans = answer_question(q["question"], evidence_text, generate)
        except Exception:
            # One flaky question must never crash the batch or fabricate an answer.
            ans = dict(_DEFERRED)
        record = {"row": q["row"], "question": q["question"], **ans}
        if record["action"] == ANSWER:
            answered += 1
        if log is not None:
            try:
                log(record)
            except Exception:
                # The audit log is best-effort: a sink failure (e.g. BigQuery) must not
                # abort answering the customer's questionnaire.
                pass
        results.append(record)
    total = len(results)
    return {"results": results, "total": total, "answered": answered, "deferred": total - answered}
