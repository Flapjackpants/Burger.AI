# Burger.AI

**2026 Cornell AI Hackathon Finalist**

Burger.AI is an automated Red Teaming platform designed to stress-test, evaluate, and secure financial AI agents. It acts as an adversarial "Red Team" that attacks your agent with sophisticated prompts, evaluates the responses for safety failures, and autonomously generates guardrails to patch vulnerabilities in real-time.

## Motivation

Currently, the tools available for making AI guardrails are heavily focused on pre-filter and post-filter text moderation, which is a severely neglected space when it comes to *agentic* AIs. 

There is a massive "Intent-Action Gap" where malicious or unintended actions can easily masquerade as routine tool calls, bypassing standard safety controls without requiring "toxic" text. When real money and lives are on the line—whether in finance, healthcare, or military applications—relying on pure text filters is insufficient. 

## Key Features & Solution

To address this, Burger.AI introduces an "Execution Governor" that intercepts the agent's actions, rather than just its words. 

* **Pre-Tool Hook**: This feature validates the JSON payload against dynamic policies before execution to block dangerous logic.
* **Post-Tool Hook**: This feature sanitizes the tool output before the agent sees it, redacts PII (like passwords and SSNs), and prevents tool-output-based prompt injections that lead to context drift.

## UI Usage & Dashboard

The Burger.AI platform features a multi-faceted dashboard to track agentic safety. 

![Burger.AI Dashboard UI](images/failure.png)

It allows users to monitor in-depth testing based on OWASP standards, visualizing vulnerabilities such as:
* Sycophancy
* Prompt Injection
* Role-Play Drift
* PII Leak
* Hallucination
* Jailbreak

## Evaluation Results & Failure Reduction

In standard benchmarks, industry models failed consistently when attacked with non-toxic, logic-based exploits. Burger.AI significantly reduces these failures by filtering for logic rather than feelings. Below are the evaluations of Sonnet 4.6 before and after adding generated guardrails:

![Testing Results & Failure Reduction Graph](images/anthropic_pre.png)
![Testing Results & Failure Reduction Graph](images/anthropic_post.png)

* **Anthropic-Sonnet 4.6**: Averaged a ~36% pass rate without agentic guardrails.
* **OpenAI ChatGPT-4 mini**: Averaged a ~59% pass rate.
* **Post-guardrail, both models**: Averaged a 98% success rate across multiple trials, effectively addressing the gap in coverage within industry tools.

---

## Quick Start

The easiest way to run the entire stack (Backend, Agents, and Client dashboard) is:

```bash
./run-all.sh
```

This script will:
1. Set up Python virtual environments and install dependencies.
2. Install Node.js dependencies for the client.
3. Launch the Backend (Red Team Engine), the Agent (Victim), and the Client (Dashboard).

---

## Configuration (Required)

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

## Architecture

The project consists of three main components:

1.  **Backend (`/backend`)**:
    * **Red Team LLM**: Generates adversarial prompts (Sycophancy, Prompt Injection, PII Leaks).
    * **Evaluator LLM**: A "Judge" that scores the agent's response and tool usage.
    * **Guardrail LLM**: An "Engineer" that writes Python code to patch vulnerabilities found by the Evaluator.

2.  **Agents (`/agents`)**:
    * Sample financial agents (e.g., `payment_agent.py`) capable of processing payments, checking balances, etc.
    * These agents are the "targets" of the red teaming.

3.  **Client (`/client`)**:
    * A React + Vite dashboard to visualize the attacks, safety scores, and generated guardrails.

## Note on Costs

This project uses LLMs for generating attacks and evaluating responses. **You must provide your own API keys.**
- The system is designed to use `gpt-4o-mini` by default to minimize costs.
- Heavy red-teaming sessions will consume tokens from your OpenAI/Anthropic accounts.

## Credits & Acknowledgements 

This project was built for the **2026 Cornell AI Hackathon** and was selected as a finalist.

**Team:**

* **Daniel Lee** (linkedin.com/in/daniel-lee-55688730a)
* **Maxwell Li** (linkedin.com/in/maxwell-kaiyang-li/)
* **Jimmy Mulosmani** (linkedin.com/in/trashgim-jimmy-mulosmani-035767245)
* **Andrew Zhang** (linkedin.com/in/andrew-zhang-b7b867390/)

**Special Thanks:**
To our mentors, sponsors, and the Hackathon Team who helped make this project possible: 
* Ami Stuart
* Vignesh Subbiah
* Aaron Yim
* Lucas Fedronic
