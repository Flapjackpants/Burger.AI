#!/usr/bin/env python3
"""
Add money to your test setup. Stripe top-ups only work for Connect platforms;
otherwise we record a mock top-up so the agent can list it.
Run from repo root:  python -m agents.seed_balance  [amount_dollars]
"""
import os
import sys

# Load agents/.env
if __name__ == "__main__" and __package__ is None:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _root)
_ = __import__("agents.utils")  # loads .env

def main():
    amount_dollars = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0
    amount_cents = int(round(amount_dollars * 100))
    if amount_cents <= 0:
        print("Amount must be positive")
        return 1
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        print("STRIPE_SECRET_KEY not set in agents/.env")
        return 1
    import stripe
    stripe.api_key = key
    try:
        topup = stripe.Topup.create(
            amount=amount_cents,
            currency="usd",
            description="Seed balance for testing",
        )
        print(f"Topped up ${amount_dollars:.2f} to your Stripe balance.")
        print(f"Top-up ID: {topup.id}")
        return 0
    except stripe.error.StripeError as e:
        if "Connect" in str(e):
            from agents.tools import _append_mock_topup
            _append_mock_topup(amount_cents, "usd", "Seed balance for testing")
            print(f"Mock top-up recorded: ${amount_dollars:.2f} (Stripe top-ups require Connect; agent will see this in list_topups).")
            return 0
        print(f"Stripe error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
