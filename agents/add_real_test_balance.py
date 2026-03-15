#!/usr/bin/env python3
"""
Add REAL test money to your Stripe balance (TEST MODE ONLY).
Uses Stripe's fake test card (pm_card_visa) — never a real card.
Requires STRIPE_SECRET_KEY to start with sk_test_ in agents/.env.

Run from repo root:  python -m agents.add_real_test_balance  [amount_dollars]
"""
import os
import sys

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
__import__("agents.utils")

def main():
    import stripe
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        print("STRIPE_SECRET_KEY not set in agents/.env")
        return 1
    if not key.startswith("sk_test_"):
        print("BLOCKED: Use only a TEST key (sk_test_...) in agents/.env. Live keys (sk_live_...) charge real money.")
        return 1
    stripe.api_key = key
    amount_dollars = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    amount_cents = int(round(amount_dollars * 100))
    if amount_cents < 50:
        print("Use at least 0.50 (50 cents)")
        return 1
    try:
        pi = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            capture_method="automatic",
            description="Test balance funding",
        )
        if getattr(pi, "livemode", True):
            print("BLOCKED: PaymentIntent is in LIVE mode. Use a test key (sk_test_...) in agents/.env.")
            return 1
        stripe.PaymentIntent.confirm(
            pi.id,
            payment_method="pm_card_visa",
        )
        print(f"Done. ${amount_dollars:.2f} was charged and added to your balance (you'll see it under Incoming/Pending).")
        print("")
        print("To get funds into 'Available' (not just Incoming):")
        print("  1. Dashboard → Settings → Payouts")
        print("  2. Check 'Payout schedule' and, if offered, 'Next-day settlement' or faster settlement.")
        print("  3. In test mode, Available may stay $0; Stripe often keeps test funds in Pending.")
        print("  Run:  python -m agents.check_balance")
        return 0
    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
