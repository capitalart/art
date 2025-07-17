#!/bin/bash

# === [ ArtNarrator: Dev Cycle Script – Robust Logging ] ===
# Automates: git pull, applies patches, installs, lints, tests, logs everything.
# If all pass, launches Flask app. Logs are saved in dev-logs/dev_cycle-YYYYMMDD-HHMMSS.log.

set -euo pipefail  # Exit on error, error on unset var, propagate failures in pipes

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PATCH_DIR="$PROJECT_ROOT/patches"
VENV_DIR="$PROJECT_ROOT/venv"
PYTHON="$VENV_DIR/bin/python"
FLASK_APP="app.py"
PORT=7777
LOGS_DIR="$PROJECT_ROOT/dev-logs"
NOW="$(date +'%Y%m%d-%H%M%S')"
LOG_FILE="$LOGS_DIR/dev_cycle-$NOW.log"

mkdir -p "$LOGS_DIR"
cd "$PROJECT_ROOT"

# --- Helper for logging and error reporting ---
log()  { echo "$@" | tee -a "$LOG_FILE"; }
err()  { echo "[ERROR] $@" | tee -a "$LOG_FILE" >&2; }
run()  { log ">>> $@"; "$@" 2>&1 | tee -a "$LOG_FILE"; }

# --- Error trap for anything that fails ---
trap 'err "Dev cycle failed at step: $BASH_COMMAND (exit code: $?)"; log "See full log: $LOG_FILE"; exit 1' ERR

log "=== [Dev Cycle] $(date) ==="
log "Running in $PROJECT_ROOT"
log "Saving logs to $LOG_FILE"
log "Python: $PYTHON"
log "-----------------------------------------"

log "1. GIT: Checkout and pull main branch"
run git checkout main
run git pull origin main

log "2. PATCH: Apply all .patch files in patches/"
if [ -d "$PATCH_DIR" ]; then
  for patch in "$PATCH_DIR"/*.patch; do
    [ -e "$patch" ] || continue
    log "   > Applying $patch ..."
    if git apply --3way "$patch"; then
      log "   > Applied $patch OK."
    else
      err "   > Failed to apply $patch! See above for details."
      exit 2
    fi
  done
else
  log "   > No patches directory found, skipping."
fi

log "3. PYTHON: Activate virtualenv, install dependencies"
source "$VENV_DIR/bin/activate"
run pip install -r requirements.txt

log "4. LINT: Black and Ruff (format, lint)"
run black . --check --diff
run ruff .

log "5. TEST: Pytest with coverage"
run pytest --maxfail=3 --disable-warnings --cov=.

log "6. STATUS: Git commit summary and coverage"
run git log -n 10 --oneline --graph
run coverage report || true

log "-----------------------------------------"
log "All checks PASSED! Ready to launch ArtNarrator Flask app."
log "Starting Flask at http://localhost:$PORT/ (Ctrl+C to stop)"
log "-----------------------------------------"

# If all passes, launch Flask app (will show in console, also logs)
run $PYTHON $FLASK_APP

log "=== [Dev Cycle] Finished cleanly at $(date) ==="
log "See logs at: $LOG_FILE"

# --- End script (no need for explicit exit 0) ---
