FREE_LIMIT = 1  # questionnaires a customer may answer for free before subscribing


def requires_payment(questionnaires_used, is_paid, free_limit=FREE_LIMIT):
    """Whether the customer must pay before answering another questionnaire.

    Paid customers are always entitled; unpaid customers are entitled until they
    have used their free quota.
    """
    if is_paid:
        return False
    return questionnaires_used >= free_limit
