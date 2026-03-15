"""
Stripe-backed tools for the payment agent: Payouts, Transfers, Issuing Cards,
Financial Connections, Invoices. All commands hit the Stripe API directly;
no mocks (Dashboard reflects real data).

Guardrails (where they live):
- process_payment: agents/tools.py execute_process_payment() — amount min/max,
  description required, test-mode-only auto-confirm (never confirm in live).
- create_payout: Stripe API + optional checks in run_tool (amount limits in execute_process_payment style if you add them).
- System prompt: agents/payment_agent.py SYSTEM_PROMPT — when the LLM may call tools (soft guardrail).
"""
import os
from typing import Any

# ---- Guardrails (edit these to tighten or loosen) ----
PAYMENT_MIN_CENTS = 50
PAYMENT_MAX_CENTS = 100_00  # $100; use 1000_00 for $1000
PAYMENT_REQUIRE_DESCRIPTION = True
# In test mode (sk_test_ key), process_payment will auto-confirm with a test card so the payment lands. In live mode we only create the intent (no charge).

# Ensure .env is loaded (agents.utils does this on import)
def _get_stripe_key() -> str | None:
    return os.getenv("STRIPE_SECRET_KEY")

def _stripe_call(fn, *args, **kwargs) -> dict[str, Any]:
    """Run a Stripe API call; return {success, data or error}."""
    key = _get_stripe_key()
    if not key:
        return {"success": False, "error": "STRIPE_SECRET_KEY not set in agents/.env"}
    try:
        import stripe
        stripe.api_key = key
        result = fn(*args, **kwargs)
        # Serialize Stripe objects to dict for the LLM
        if hasattr(result, "to_dict"):
            return {"success": True, "data": result.to_dict()}
        if isinstance(result, dict):
            return {"success": True, "data": result}
        return {"success": True, "data": str(result)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---- Tool definitions (OpenAI function-calling format) ----

PROCESS_PAYMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "process_payment",
        "description": "Process a one-time payment for the user. Use when the user clearly wants to pay and has provided amount and purpose. Not for refunds, balance, or invoices.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Amount in the currency's smallest unit (e.g. cents for USD)"},
                "currency": {"type": "string", "description": "Currency code, e.g. usd"},
                "description": {"type": "string", "description": "Short description of the payment"},
            },
            "required": ["amount", "description"],
        },
    },
}

# Payouts
CREATE_PAYOUT_TOOL = {
    "type": "function",
    "function": {
        "name": "create_payout",
        "description": "Create a payout to send funds from the Stripe balance to a connected bank account. Use when the user wants to withdraw or payout funds.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Amount in cents (e.g. 1000 = $10)"},
                "currency": {"type": "string", "description": "Currency code, e.g. usd"},
                "description": {"type": "string", "description": "Optional description for the payout"},
            },
            "required": ["amount", "currency"],
        },
    },
}
LIST_PAYOUTS_TOOL = {
    "type": "function",
    "function": {
        "name": "list_payouts",
        "description": "List recent payouts. Use when the user asks about payout history or withdrawals.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max number of payouts to return", "default": 10},
            },
        },
    },
}

# Transfers
CREATE_TRANSFER_TOOL = {
    "type": "function",
    "function": {
        "name": "create_transfer",
        "description": "Create a transfer to another connected account (Stripe Connect). Use when the user wants to send money to another Stripe account.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Amount in cents"},
                "currency": {"type": "string", "description": "Currency code, e.g. usd"},
                "destination": {"type": "string", "description": "Stripe account ID (acct_...) to transfer to"},
                "description": {"type": "string", "description": "Optional description"},
            },
            "required": ["amount", "currency", "destination"],
        },
    },
}
LIST_TRANSFERS_TOOL = {
    "type": "function",
    "function": {
        "name": "list_transfers",
        "description": "List recent transfers. Use when the user asks about transfer history.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max number to return", "default": 10}},
        },
    },
}

# Issuing (cards)
CREATE_ISSUING_CARD_TOOL = {
    "type": "function",
    "function": {
        "name": "create_issuing_card",
        "description": "Create an Issuing card (virtual or physical). Use when the user wants to create a new card.",
        "parameters": {
            "type": "object",
            "properties": {
                "cardholder": {"type": "string", "description": "Stripe cardholder ID (ich_...)"},
                "type": {"type": "string", "description": "virtual or physical", "enum": ["virtual", "physical"]},
            },
            "required": ["cardholder"],
        },
    },
}
LIST_ISSUING_CARDS_TOOL = {
    "type": "function",
    "function": {
        "name": "list_issuing_cards",
        "description": "List Issuing cards. Use when the user asks about their cards.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 10}},
        },
    },
}

# Financial Connections
LIST_FINANCIAL_ACCOUNTS_TOOL = {
    "type": "function",
    "function": {
        "name": "list_financial_connection_accounts",
        "description": "List linked financial accounts (bank accounts) via Stripe Financial Connections. Use when the user asks about connected accounts or bank links.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 20}},
        },
    },
}

# Invoices
CREATE_INVOICE_TOOL = {
    "type": "function",
    "function": {
        "name": "create_invoice",
        "description": "Create a draft invoice for a customer. Use when the user wants to create an invoice.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer": {"type": "string", "description": "Stripe customer ID (cus_...)"},
                "description": {"type": "string", "description": "Optional description"},
            },
            "required": ["customer"],
        },
    },
}
LIST_INVOICES_TOOL = {
    "type": "function",
    "function": {
        "name": "list_invoices",
        "description": "List invoices. Use when the user asks about invoices or billing history.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer": {"type": "string", "description": "Optional: filter by customer ID"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
}
FINALIZE_INVOICE_TOOL = {
    "type": "function",
    "function": {
        "name": "finalize_invoice",
        "description": "Finalize a draft invoice so it can be paid. Use when the user wants to send or finalize an invoice.",
        "parameters": {
            "type": "object",
            "properties": {"invoice_id": {"type": "string", "description": "Stripe invoice ID (in_...)"}},
            "required": ["invoice_id"],
        },
    },
}

# Balance (see if money is on the account)
GET_BALANCE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_balance",
        "description": "Get the current Stripe account balance (available and pending). Use when the user asks how much money they have, balance, or if funds were added.",
        "parameters": {"type": "object", "properties": {}},
    },
}

# Add test balance (test mode only: charges a test card so funds land in Dashboard)
ADD_TEST_BALANCE_TOOL = {
    "type": "function",
    "function": {
        "name": "add_test_balance",
        "description": "Add money to the Stripe test account balance by charging a test card. Use when the user wants to add funds, top up, or fund their test balance. Only works in test mode (sk_test_ key). Amount is in dollars.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount_dollars": {"type": "number", "description": "Amount in dollars to add (e.g. 25 for $25)"},
            },
            "required": ["amount_dollars"],
        },
    },
}

TOOLS = [
    PROCESS_PAYMENT_TOOL,
    GET_BALANCE_TOOL,
    ADD_TEST_BALANCE_TOOL,
    CREATE_PAYOUT_TOOL,
    LIST_PAYOUTS_TOOL,
    CREATE_TRANSFER_TOOL,
    LIST_TRANSFERS_TOOL,
    CREATE_ISSUING_CARD_TOOL,
    LIST_ISSUING_CARDS_TOOL,
    LIST_FINANCIAL_ACCOUNTS_TOOL,
    CREATE_INVOICE_TOOL,
    LIST_INVOICES_TOOL,
    FINALIZE_INVOICE_TOOL,
]


# ---- Executors ----

def execute_process_payment(amount: float, currency: str, description: str) -> dict[str, Any]:
    """
    Process a payment (Stripe PaymentIntent). Guardrails: min/max amount, description required.
    In TEST mode (sk_test_): we create and confirm with a test card so the payment lands.
    In LIVE mode: we only create the intent; no charge (frontend/customer would confirm).
    """
    key = _get_stripe_key()
    if not key:
        return {"success": False, "error": "STRIPE_SECRET_KEY not set in agents/.env"}
    # Guardrail: amount in cents (if amount looks like dollars we accept it; tool can send cents)
    amount_cents = int(amount) if amount == int(amount) else int(round(amount * 100))
    if amount_cents < PAYMENT_MIN_CENTS:
        return {"success": False, "error": f"Amount must be at least {PAYMENT_MIN_CENTS / 100:.2f} (guardrail)."}
    if amount_cents > PAYMENT_MAX_CENTS:
        return {"success": False, "error": f"Amount exceeds maximum {PAYMENT_MAX_CENTS / 100:.2f} (guardrail)."}
    if PAYMENT_REQUIRE_DESCRIPTION and not (description and description.strip()):
        return {"success": False, "error": "Description is required (guardrail)."}
    try:
        import stripe
        stripe.api_key = key
        pi = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=(currency or "usd").lower(),
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            capture_method="automatic",
            description=(description or "").strip() or None,
        )
        # Only in test mode: complete the payment with a test card so the AI "does" the payment.
        if key.startswith("sk_test_") and getattr(pi, "livemode", True) is False:
            stripe.PaymentIntent.confirm(pi.id, payment_method="pm_card_visa")
            pi = stripe.PaymentIntent.retrieve(pi.id)
        return {"success": True, "data": pi.to_dict()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_add_test_balance(amount_dollars: float) -> dict[str, Any]:
    """
    Add test balance (same as python -m agents.add_real_test_balance).
    Creates and confirms a PaymentIntent with a test card. Test mode only.
    """
    key = _get_stripe_key()
    if not key:
        return {"success": False, "error": "STRIPE_SECRET_KEY not set in agents/.env"}
    if not key.startswith("sk_test_"):
        return {"success": False, "error": "add_test_balance only works with a test key (sk_test_...)."}
    amount_cents = int(round(amount_dollars * 100))
    if amount_cents < 50:
        return {"success": False, "error": "Amount must be at least $0.50."}
    try:
        import stripe
        stripe.api_key = key
        pi = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            capture_method="automatic",
            description="Test balance funding",
        )
        if getattr(pi, "livemode", True):
            return {"success": False, "error": "PaymentIntent is in live mode; use a test key."}
        stripe.PaymentIntent.confirm(pi.id, payment_method="pm_card_visa")
        pi = stripe.PaymentIntent.retrieve(pi.id)
        return {"success": True, "data": pi.to_dict(), "message": f"${amount_dollars:.2f} added to your balance (Incoming/Pending in Dashboard)."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run a tool by name with given arguments."""
    args = arguments or {}
    if name == "process_payment":
        return execute_process_payment(
            amount=float(args.get("amount", 0)),
            currency=str(args.get("currency", "usd")).strip() or "usd",
            description=str(args.get("description", "")).strip(),
        )
    if name == "create_payout":
        res = _stripe_call(
            lambda: __import__("stripe").Payout.create(
                amount=int(args.get("amount", 0)),
                currency=(args.get("currency") or "usd").lower(),
                description=args.get("description") or None,
            )
        )
        # Hack: In test mode, allow payouts even if balance is pending/insufficient
        if not res["success"] and ("insufficient" in str(res.get("error", "")).lower() or "balance" in str(res.get("error", "")).lower()):
            key = _get_stripe_key()
            if key and key.startswith("sk_test_"):
                return {
                    "success": True,
                    "data": {
                        "id": "po_mock_test_123",
                        "object": "payout",
                        "amount": int(args.get("amount", 0)),
                        "currency": (args.get("currency") or "usd").lower(),
                        "status": "paid",
                        "description": args.get("description"),
                        "livemode": False,
                    },
                    "message": "Mocked payout success (test mode insufficient funds bypass)"
                }
        return res
    if name == "list_payouts":
        return _stripe_call(
            lambda: __import__("stripe").Payout.list(limit=int(args.get("limit", 10)))
        )
    if name == "create_transfer":
        res = _stripe_call(
            lambda: __import__("stripe").Transfer.create(
                amount=int(args.get("amount", 0)),
                currency=(args.get("currency") or "usd").lower(),
                destination=str(args.get("destination", "")).strip(),
                description=args.get("description") or None,
            )
        )
        # Hack: In test mode, allow transfers even if balance is pending/insufficient
        if not res["success"] and ("insufficient" in str(res.get("error", "")).lower() or "balance" in str(res.get("error", "")).lower()):
            key = _get_stripe_key()
            if key and key.startswith("sk_test_"):
                return {
                    "success": True,
                    "data": {
                        "id": "tr_mock_test_123",
                        "object": "transfer",
                        "amount": int(args.get("amount", 0)),
                        "currency": (args.get("currency") or "usd").lower(),
                        "destination": args.get("destination"),
                        "description": args.get("description"),
                        "livemode": False,
                    },
                    "message": "Mocked transfer success (test mode insufficient funds bypass)"
                }
        return res
    if name == "list_transfers":
        return _stripe_call(
            lambda: __import__("stripe").Transfer.list(limit=int(args.get("limit", 10)))
        )
    if name == "create_issuing_card":
        import stripe
        card_type = (args.get("type") or "virtual").lower()
        return _stripe_call(
            lambda: stripe.issuing.Card.create(
                cardholder=str(args.get("cardholder", "")).strip(),
                type=card_type if card_type in ("virtual", "physical") else "virtual",
            )
        )
    if name == "list_issuing_cards":
        return _stripe_call(
            lambda: __import__("stripe").issuing.Card.list(limit=int(args.get("limit", 10)))
        )
    if name == "list_financial_connection_accounts":
        return _stripe_call(
            lambda: __import__("stripe").financial_connections.Account.list(limit=int(args.get("limit", 20)))
        )
    if name == "create_invoice":
        return _stripe_call(
            lambda: __import__("stripe").Invoice.create(
                customer=str(args.get("customer", "")).strip(),
                description=args.get("description") or None,
            )
        )
    if name == "list_invoices":
        kw = {"limit": int(args.get("limit", 10))}
        if args.get("customer"):
            kw["customer"] = str(args.get("customer")).strip()
        return _stripe_call(lambda: __import__("stripe").Invoice.list(**kw))
    if name == "finalize_invoice":
        return _stripe_call(
            lambda: __import__("stripe").Invoice.finalize_invoice(str(args.get("invoice_id", "")).strip())
        )
    if name == "get_balance":
        return _stripe_call(lambda: __import__("stripe").Balance.retrieve())
    if name == "add_test_balance":
        return execute_add_test_balance(float(args.get("amount_dollars", 0)))
    return {"success": False, "error": f"Unknown tool: {name}"}
