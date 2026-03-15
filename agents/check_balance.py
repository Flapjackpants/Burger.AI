#!/usr/bin/env python3
"""
Print your Stripe account balance (available and pending).
Run from repo root:  python -m agents.check_balance
"""
import os
import sys

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
__import__("agents.utils")  # load .env

def main():
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        print("STRIPE_SECRET_KEY not set in agents/.env")
        return 1
    import stripe
    stripe.api_key = key
    try:
        bal = stripe.Balance.retrieve()
        print("Stripe account balance")
        print("  Mode:", "live" if bal.livemode else "test")
        print("  Available (payable now):")
        for x in (bal.available or []):
            print(f"    {x.amount / 100:,.2f} {x.currency.upper()}")
        if not (bal.available or []):
            print("    (none)")
        print("  Pending (not yet available):")
        for x in (bal.pending or []):
            print(f"    {x.amount / 100:,.2f} {x.currency.upper()}")
        if not (bal.pending or []):
            print("    (none)")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
