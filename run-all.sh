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
CLIENT_PID=""

cleanup() {
  echo ""
  echo "[run-all] Shutting down..."
  # Kill process groups (negative PID) so child processes (python, node) are stopped too.
  if [[ -n "$CLIENT_PID" ]] && kill -0 "$CLIENT_PID" 2>/dev/null; then
    kill -9 -"$CLIENT_PID" 2>/dev/null || kill -9 "$CLIENT_PID" 2>/dev/null || true
    echo "[run-all] Client (PID $CLIENT_PID) stopped."
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill -9 -"$BACKEND_PID" 2>/dev/null || kill -9 "$BACKEND_PID" 2>/dev/null || true
    echo "[run-all] Backend (PID $BACKEND_PID) stopped."
  fi
  if [[ -n "$AGENTS_PID" ]] && kill -0 "$AGENTS_PID" 2>/dev/null; then
    kill -9 -"$AGENTS_PID" 2>/dev/null || kill -9 "$AGENTS_PID" 2>/dev/null || true
    echo "[run-all] Agents (PID $AGENTS_PID) stopped."
  fi
  # Ensure nothing is left on our ports (handles orphaned children)
  lsof -ti:5001 | xargs kill -9 2>/dev/null || true
  lsof -ti:5002 | xargs kill -9 2>/dev/null || true
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

# Wait until backend and agent are accepting TCP connections (avoids "Connection refused")
# Use TCP port check (nc) so we don't depend on HTTP/curl; give servers a moment to bind first
sleep 2
echo "[run-all] Waiting for backend (5001) and agent (5002) to accept connections..."
max_wait=30
for i in $(seq 1 "$max_wait"); do
  backend_ok=0
  agent_ok=0
  nc -z 127.0.0.1 5001 2>/dev/null && backend_ok=1 || true
  nc -z 127.0.0.1 5002 2>/dev/null && agent_ok=1 || true
  if [ "$backend_ok" -eq 1 ] && [ "$agent_ok" -eq 1 ]; then
    echo "[run-all] Backend and agent are up (ports 5001 and 5002 open) after ${i}s."
    break
  fi
  [ "$i" -eq "$max_wait" ] && echo "[run-all] WARNING: Timeout. Backend(5001)=$backend_ok Agent(5002)=$agent_ok. Check the process output above for errors."
  sleep 1
done

# --- Start client in background so Ctrl+C is handled by this script ---
echo "[run-all] Starting client (Vite dev server)..."
echo "[run-all] Press Ctrl+C once to stop client, backend, and agents."
(cd "$CLIENT_DIR" && npm run dev) &
CLIENT_PID=$!

# Wait for client (foreground). When user presses Ctrl+C, shell receives INT and trap runs cleanup.
wait $CLIENT_PID 2>/dev/null || true
cleanup
