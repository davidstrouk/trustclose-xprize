"""Thin Stripe adapter — untested I/O boundary (needs STRIPE_SECRET_KEY).

`create_checkout_url` opens a subscription Checkout session and returns its URL;
`paid_customer_from_event` verifies a webhook and returns the customer_id that just
subscribed (or None). No business logic lives here.
"""

import os

import stripe


def _api_key():
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]


def create_checkout_url(customer_id):
    _api_key()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": os.environ["STRIPE_PRICE_ID"], "quantity": 1}],
        success_url=os.environ.get("BILLING_SUCCESS_URL", "https://trustclose.app/billing/ok"),
        cancel_url=os.environ.get("BILLING_CANCEL_URL", "https://trustclose.app/billing/cancel"),
        client_reference_id=customer_id,
        metadata={"customer_id": customer_id},
    )
    return session.url


def paid_customer_from_event(payload, signature):
    _api_key()
    event = stripe.Webhook.construct_event(
        payload, signature, os.environ["STRIPE_WEBHOOK_SECRET"]
    )
    if event["type"] == "checkout.session.completed":
        return event["data"]["object"].get("client_reference_id")
    return None
