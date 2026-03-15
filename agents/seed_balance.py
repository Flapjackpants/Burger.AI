#!/usr/bin/env python3
"""
Try to add balance via Stripe Top-up (Connect accounts only).
For standard accounts use:  python -m agents.add_real_test_balance 25
Run from repo root:  python -m agents.seed_balance  [amount_dollars]
"""
import os
import sys

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
__import__("agents.utils")

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
        print(f"Topped up ${amount_dollars:.2f} to your Stripe balance. Check Dashboard → Balance.")
        return 0
    except stripe.error.StripeError as e:
        if "Connect" in str(e):
            print("Stripe top-ups require a Connect platform. Use:  python -m agents.add_real_test_balance 25")
        else:
            print(f"Stripe error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
