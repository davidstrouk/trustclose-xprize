"""Thin Stripe adapter — untested I/O boundary (needs STRIPE_SECRET_KEY).

`create_checkout_url` opens a subscription Checkout session and returns its URL;
`paid_status_from_event` verifies a webhook and returns (customer_id, is_paid) for the
events that grant or revoke access (or None to ignore). No business logic lives here.
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
        # Tag the subscription too, so later subscription.* events carry our customer id.
        subscription_data={"metadata": {"customer_id": customer_id}},
    )
    return session.url


def paid_status_from_event(payload, signature):
    """Return (customer_id, is_paid) for a grant/revoke event, or None to ignore."""
    _api_key()
    event = stripe.Webhook.construct_event(
        payload, signature, os.environ["STRIPE_WEBHOOK_SECRET"]
    )
    event_type = event["type"]
    obj = event["data"]["object"]
    if event_type == "checkout.session.completed":
        return (obj.get("client_reference_id"), True)
    if event_type == "customer.subscription.deleted":
        customer_id = (obj.get("metadata") or {}).get("customer_id")
        return (customer_id, False) if customer_id else None
    return None
