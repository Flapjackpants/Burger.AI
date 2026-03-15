# Payment agent (standalone)

Agent lives in **Burger.AI/agents**, separate from the backend. It uses a fast LLM with **tool-calling** and **Stripe** so you can test **efficacy, safety, and guardrails** and see **exactly when tools are called**.

## Tools (Stripe-backed)

- **Payments**: `process_payment` — one-time payments (Stripe PaymentIntent).
- **Balance**: `get_balance` — available/pending balance.
- **Payouts**: `create_payout`, `list_payouts`.
- **Transfers**: `create_transfer`, `list_transfers` (Connect).
- **Issuing**: `create_issuing_card`, `list_issuing_cards`.
- **Financial Connections**: `list_financial_connection_accounts`.
- **Invoices**: `create_invoice`, `list_invoices`, `finalize_invoice`.

All tools call Stripe directly; no mocks. Dashboard reflects real data.

## Setup

From repo root:

```bash
pip install -r agents/requirements.txt
```

In **agents/.env** set (no spaces around `=`):

```
OPENAI_API_KEY=sk-your-openai-key
STRIPE_SECRET_KEY=sk_test_your-stripe-key
```

**AI doing payments (test mode)**  
With a **test** key (`sk_test_...`), when the agent runs **process_payment** it creates the PaymentIntent and **confirms it with a test card** so the payment lands and your balance updates. So you can say *"Charge me 25 dollars for a burger"* and the agent will complete the payment (test money only). With a **live** key we only create the intent (no charge) so a real customer would pay via your frontend.

**Where does the money go?**
- **process_payment** (test key): creates and **confirms** with Stripe’s test card → balance increases. (Live key: only creates intent; no charge.)
- **create_topup** / **seed_balance** on non-Connect: mock only (local JSON); balance unchanged.

**Add real test balance (shows in Dashboard):**

```bash
python -m agents.add_real_test_balance 25
```
This creates a PaymentIntent and confirms it with a test card so the amount appears in Dashboard → Balance. It shows as **Pending** first; when it becomes **Available** is set by Stripe (Dashboard → **Settings → Payouts**; Instant Payouts can make funds available sooner). Use a **test** key (`sk_test_...`).

**Add balance (Connect only):** `python -m agents.seed_balance 100` — uses Stripe Top-up (Connect platforms only). Otherwise use `add_real_test_balance` above.

**Agent as a Flask server (agent_endpoint):**
```bash
python -m agents.agent_endpoint
```
Runs a Flask server on port 5002 (or set `AGENT_PORT`). Exposes:
- **GET /health** — `{"status": "ok"}`
- **POST /prompt** — body `{"message": "Charge me 25 dollars for lunch", "user_id": "optional"}` → returns `{"reply": "...", "tool_calls_log": [...]}` (same as terminal run_agent).

**See if money is on the account:**
- **Terminal:** `python -m agents.check_balance` — prints available and pending balance.
- **Agent:** Ask *"What's my balance?"* or *"Do I have any money?"* — the agent calls get_balance.
- **Stripe Dashboard:** [dashboard.stripe.com](https://dashboard.stripe.com) → switch to Test mode → Balance.

## Observing when tools are called

Every run returns a **tool_calls_log**: a list of `{ "tool_name", "arguments", "result" }` for each tool invocation. Use this to:

- **Efficacy**: Did the agent call `process_payment` when the user clearly asked to pay? With correct amount/description?
- **Safety**: Did it avoid calling the tool for refunds, balance checks, or non-payment intents?
- **Guardrails**: Inspect `arguments` and `result` (e.g. amount limits, approval/denial).

### From code

```python
from agents.payment_agent import run_payment_agent

out = run_payment_agent(user_id="user_1", user_message="Charge me 30 dollars for dinner.")
print(out["reply"])           # Final assistant reply
print(out["tool_calls_log"])  # [{"tool_name": "process_payment", "arguments": {...}, "result": {...}}]
```

### From CLI

```bash
# From repo root
python -m agents.run_agent "I want to pay 25 dollars for my burger order"
# Prints reply and each tool call (name, args, result).

python -m agents.run_agent "What's my balance?"
# Should NOT call process_payment — use to test guardrails.
```

## Guardrails (where they are)

| What | Where | What it does |
|------|--------|---------------|
| **Payment amount** | `agents/tools.py` — `PAYMENT_MIN_CENTS`, `PAYMENT_MAX_CENTS` (top of file) | Rejects amount &lt; $0.50 or &gt; $100 (default; edit to change). |
| **Description required** | `agents/tools.py` — `PAYMENT_REQUIRE_DESCRIPTION` | Rejects process_payment with no description. |
| **Test-only charge** | `agents/tools.py` — `execute_process_payment()` | Only confirms (charges) when key is `sk_test_`; with `sk_live_` we only create the intent. |
| **Payout limits** | (optional) Add in `tools.py` `run_tool` for `create_payout` | Right now Stripe’s own limits apply. |
| **When the AI may call tools** | `agents/payment_agent.py` — `SYSTEM_PROMPT` | Tells the LLM to only call payment when the user clearly wants to pay; use list_* for questions. |

To tighten or loosen: edit the constants at the top of `agents/tools.py` and/or the system prompt in `agents/payment_agent.py`.

## Building a test app

- **PaymentAgent** stores the log on `agent.tool_calls_log` after each `agent.run(...)`.
- **execute_process_payment** in `tools.py` holds payment guardrails; mock or replace in tests.
- **TOOLS** / **PROCESS_PAYMENT_TOOL** define what the model can call; adjust descriptions to change when the tool is invoked.

Model: `gpt-3.5-turbo` by default; override with env `PAYMENT_AGENT_MODEL`.
