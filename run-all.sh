#!/usr/bin/env bash
# Run and deploy all three parts: backend server, agents endpoint, client.
# Creates and activates virtual environments for Python projects when missing;
# installs client deps when node_modules is missing. Backend and agents run in
# background; client runs in foreground (Ctrl+C stops client and cleans up others).

set -e
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Clear ports 5001 and 5002 so we can bind on startup (e.g. after a previous run or crash)
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
lsof -ti:5002 | xargs kill -9 2>/dev/null || true

BACKEND_PID=""
AGENTS_PID=""

cleanup() {
  echo ""
  echo "[run-all] Shutting down..."
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    echo "[run-all] Backend (PID $BACKEND_PID) stopped."
  fi
  if [[ -n "$AGENTS_PID" ]] && kill -0 "$AGENTS_PID" 2>/dev/null; then
    kill "$AGENTS_PID" 2>/dev/null || true
    echo "[run-all] Agents (PID $AGENTS_PID) stopped."
  fi
  exit 0
}
trap cleanup INT TERM

# --- Backend (Flask server, port 5001) ---
BACKEND_DIR="$REPO_ROOT/backend"
# Prefer existing backendVenv, else use .venv
if [[ -d "$BACKEND_DIR/backendVenv" ]]; then
  BACKEND_VENV="$BACKEND_DIR/backendVenv"
elif [[ -d "$BACKEND_DIR/.venv" ]]; then
  BACKEND_VENV="$BACKEND_DIR/.venv"
else
  BACKEND_VENV="$BACKEND_DIR/.venv"
  echo "[run-all] Creating backend virtual environment at $BACKEND_VENV"
  python3 -m venv "$BACKEND_VENV"
fi
BACKEND_REQ="$BACKEND_DIR/requirements.txt"
[[ ! -f "$BACKEND_REQ" ]] && BACKEND_REQ="$REPO_ROOT/requirements.txt"
echo "[run-all] Activating backend venv and ensuring dependencies..."
source "$BACKEND_VENV/bin/activate"
pip install -q -r "$BACKEND_REQ"
deactivate 2>/dev/null || true

# --- Agents (agent endpoint, port 5002) ---
AGENTS_DIR="$REPO_ROOT/agents"
AGENTS_VENV="$AGENTS_DIR/.venv"
if [[ ! -d "$AGENTS_VENV" ]]; then
  echo "[run-all] Creating agents virtual environment at $AGENTS_VENV"
  python3 -m venv "$AGENTS_VENV"
fi
echo "[run-all] Activating agents venv and ensuring dependencies..."
source "$AGENTS_VENV/bin/activate"
pip install -q -r "$AGENTS_DIR/requirements.txt"
deactivate 2>/dev/null || true

# --- Client (Node/Vite, install if needed) ---
CLIENT_DIR="$REPO_ROOT/client"
if [[ ! -d "$CLIENT_DIR/node_modules" ]] || [[ "$CLIENT_DIR/package.json" -nt "$CLIENT_DIR/node_modules" ]]; then
  echo "[run-all] Installing client dependencies (npm install)..."
  (cd "$CLIENT_DIR" && npm install)
fi

# --- Start backend in background ---
echo "[run-all] Starting backend server (port 5001)..."
(cd "$BACKEND_DIR" && source "$BACKEND_VENV/bin/activate" && python run.py) &
BACKEND_PID=$!

# --- Start agents endpoint in background (port 5002 to match backend DEFAULT_LLM_LINK) ---
echo "[run-all] Starting agents endpoint (port 5002)..."
(cd "$REPO_ROOT" && source "$AGENTS_VENV/bin/activate" && AGENT_PORT=5002 python -m agents.agent_endpoint) &
AGENTS_PID=$!

# Give servers a moment to bind
sleep 2

# --- Start client in foreground ---
echo "[run-all] Starting client (Vite dev server)..."
echo "[run-all] Press Ctrl+C to stop the client and shut down backend and agents."
(cd "$CLIENT_DIR" && npm run dev) || true

cleanup
