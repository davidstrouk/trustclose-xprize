"""TDD for the billing entitlement gate (the free-first → paid wedge).

A customer answers FREE_LIMIT questionnaires for free; beyond that, an unpaid
customer must subscribe. Paid customers are always entitled.
"""

from billing.entitlement import FREE_LIMIT, requires_payment


def test_paid_customer_never_requires_payment():
    assert requires_payment(questionnaires_used=999, is_paid=True) is False


def test_within_free_quota_does_not_require_payment():
    assert requires_payment(questionnaires_used=0, is_paid=False) is False


def test_at_free_limit_requires_payment():
    assert requires_payment(questionnaires_used=FREE_LIMIT, is_paid=False) is True


def test_over_free_limit_requires_payment():
    assert requires_payment(questionnaires_used=FREE_LIMIT + 5, is_paid=False) is True
