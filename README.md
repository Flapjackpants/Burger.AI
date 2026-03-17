# Burger.AI 🍔🤖

**2026 Cornell AI Hackathon Finalist**

Burger.AI is an automated Red Teaming platform designed to stress-test, evaluate, and secure financial AI agents. It acts as an adversarial "Red Team" that attacks your agent with sophisticated prompts, evaluates the responses for safety failures, and autonomously generates Python-based guardrails to patch vulnerabilities in real-time.

## 🚀 Quick Start

The easiest way to run the entire stack (Backend, Agents, and Client dashboard) is:

```bash
./run-all.sh
```

This script will:
1. Set up Python virtual environments and install dependencies.
2. Install Node.js dependencies for the client.
3. Launch the Backend (Red Team Engine), the Agent (Victim), and the Client (Dashboard).

---

## 🛠️ Configuration (Required)

To use the system, you must provide your own API keys. We have provided template files for you to copy.

### 1. Backend (Red Team Engine)
The backend generates attacks, evaluates responses, and writes guardrails.

1. Copy the example file:
   ```bash
   cp backend/.env.example backend/.env
   ```
2. Edit `backend/.env` and add your **OpenAI API Key**.
   - You can use the same key for `OPENAI_API_KEY_REDTEAM` (Attacker), `_EVAL` (Judge), and `_GUARD` (Defender).
   - Recommended model: `gpt-4o-mini` (cost-effective) or `gpt-4` (more capable).

### 2. Agents (The Victim)
This is the AI agent you are testing.

1. Copy the example file:
   ```bash
   cp agents/.env.example agents/.env
   ```
2. Edit `agents/.env` and add:
   - `OPENAI_API_KEY` (if testing GPT-based agents)
   - `ANTHROPIC_API_KEY` (if testing Claude-based agents)

### 3. Client (Dashboard)
The frontend dashboard.

1. Copy the example file:
   ```bash
   cp client/.env.example client/.env
   ```
   (The default settings usually work fine for local development).

---

## 🏗️ Architecture

The project consists of three main components:

1.  **Backend (`/backend`)**:
    *   **Red Team LLM**: Generates adversarial prompts (Sycophancy, Prompt Injection, PII Leaks).
    *   **Evaluator LLM**: A "Judge" that scores the agent's response and tool usage.
    *   **Guardrail LLM**: An "Engineer" that writes Python code to patch vulnerabilities found by the Evaluator.

2.  **Agents (`/agents`)**:
    *   Sample financial agents (e.g., `payment_agent.py`) capable of processing payments, checking balances, etc.
    *   These agents are the "targets" of the red teaming.

3.  **Client (`/client`)**:
    *   A React + Vite dashboard to visualize the attacks, safety scores, and generated guardrails.

## ⚠️ Note on Costs

This project uses LLMs for generating attacks and evaluating responses. **You must provide your own API keys.**
- The system is designed to use `gpt-4o-mini` by default to minimize costs.
- Heavy red-teaming sessions will consume tokens from your OpenAI/Anthropic accounts.

---

*Built for the 2026 Cornell AI Hackathon.*
