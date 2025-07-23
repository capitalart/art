#!/bin/bash

# ======================================================================================
# 🔁 ArtNarrator Gitflow Commander & Backup Engine 💥
#
# Version: 2.8
# Author: Robbie (Enhanced for ArtNarrator)
#
# This script automates the Git workflow, creates backups, and generates reports.
#
# ---
#
# Usage:
#   ./git-update-push.sh [options]
#
# Command Examples:
#   ./git-update-push.sh --full-auto      # Runs non-interactively
#   ./git-update-push.sh --dry-run        # Dry run (only shows commands)
#   ./git-update-push.sh --no-git         # Skips all Git operations
#   ./git-update-push.sh --no-zip         # Skips backup creation
#   ./git-update-push.sh --no-report      # Skips the report script
# ======================================================================================

# === [ SECTION 1: SETUP & CONFIGURATION ] ============================================
set -euo pipefail

# --- Project & Backup Configuration ---
PROJECT_ROOT_DIR="$(pwd)"
LOG_DIR="${PROJECT_ROOT_DIR}/logs"
BACKUP_DIR="${PROJECT_ROOT_DIR}/backups"

# --- Naming Conventions ---
NOW=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/git-update-push-${NOW}.log"
BACKUP_ZIP="$BACKUP_DIR/backup_${NOW}.zip"
DIFF_REPORT="$BACKUP_DIR/diff_report_${NOW}.md"
COMMIT_MSG_FILE=".codex-commit-msg.txt"

# --- Server Configuration ---
GUNICORN_PID_FILE="/tmp/artnarrator-gunicorn.pid"
GUNICORN_CMD="${PROJECT_ROOT_DIR}/venv/bin/gunicorn"
GUNICORN_BIND_ADDRESS="0.0.0.0:7777"
GUNICORN_WORKERS=4
GUNICORN_APP_MODULE="app:app"

# --- Colors for Logging ---
COL_RESET='\033[0m'
COL_INFO='\033[0;36m'
COL_SUCCESS='\033[0;32m'
COL_WARN='\033[0;33m'
COL_ERROR='\033[0;31m'

# === [ SECTION 2: SCRIPT FLAGS & DEFAULTS ] =========================================
AUTO_MODE=false
DRY_RUN=false
ENABLE_GIT=true
ENABLE_ZIP=true
ENABLE_REPORT_SCRIPT=true
ENABLE_RESTART=true

# === [ SECTION 3: FLAG PARSER ] =======================================================
for arg in "$@"; do
  case $arg in
    --full-auto)    AUTO_MODE=true; shift ;;
    --dry-run)      DRY_RUN=true; shift ;;
    --no-git)       ENABLE_GIT=false; shift ;;
    --no-zip)       ENABLE_ZIP=false; shift ;;
    --no-report)    ENABLE_REPORT_SCRIPT=false; shift ;;
    --no-restart)   ENABLE_RESTART=false; shift ;;
    *)              echo -e "${COL_ERROR}❌ Unknown option: $arg${COL_RESET}"; exit 1 ;;
  esac
done

# === [ SECTION 4: LOGGING & UTILITY FUNCTIONS ] =======================================
mkdir -p "$LOG_DIR"

log() {
  local type="$1"
  local msg="$2"
  local color="$COL_INFO"
  case "$type" in
    SUCCESS) color="$COL_SUCCESS" ;;
    WARN)    color="$COL_WARN" ;;
    ERROR)   color="$COL_ERROR" ;;
  esac
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') | ${color}${type^^}:${COL_RESET} ${msg}" | tee -a "$LOG_FILE"
}

die() {
  log "ERROR" "$1"
  exit 1
}

run_cmd() {
  log "EXEC" "$@"
  if ! $DRY_RUN; then
    eval "$@" >> "$LOG_FILE" 2>&1
  fi
}

check_dependencies() {
  log "INFO" "Checking for required tools..."
  local missing_deps=0
  for cmd in git zip sqlite3; do
    if ! command -v "$cmd" &> /dev/null; then
      log "ERROR" "Required command '$cmd' is not installed."
      missing_deps=$((missing_deps + 1))
    fi
  done
  if [ "$missing_deps" -gt 0 ]; then
    die "Aborting due to missing dependencies."
  fi
  log "SUCCESS" "All required tools are present."
}

# === [ SECTION 5: WORKFLOW FUNCTIONS ] ===============================================

# --- 5a: Git Operations ---
handle_git_operations() {
    if ! $ENABLE_GIT; then
        log "WARN" "Skipping all Git operations as per --no-git flag."
        return
    fi

    log "INFO" "Starting Git operations..."
    if [[ -z $(git status --porcelain) ]]; then
        log "SUCCESS" "Git working directory is clean. Nothing to commit."
        return
    fi

    run_cmd "git add ."

    local commit_msg
    if $AUTO_MODE; then
        if [[ -s "$COMMIT_MSG_FILE" ]]; then
            commit_msg=$(cat "$COMMIT_MSG_FILE")
            log "INFO" "Using automated commit message from $COMMIT_MSG_FILE."
        else
            commit_msg="Auto-commit: Routine system snapshot and updates on ${NOW}"
            log "INFO" "Using default automated commit message."
        fi
    else
        read -rp "📝 Enter commit message: " commit_msg
        if [[ -z "$commit_msg" ]]; then
            die "Commit message cannot be empty in interactive mode."
        fi
    fi

    run_cmd "git commit -m \"$commit_msg\""
    [[ -s "$COMMIT_MSG_FILE" ]] && rm -f "$COMMIT_MSG_FILE"

    log "INFO" "Pulling latest changes from origin/main..."
    run_cmd "git pull origin main --rebase" || die "git pull --rebase failed. Please resolve conflicts manually."

    log "INFO" "Pushing changes to origin/main..."
    run_cmd "git push origin main" || die "git push failed. Check remote repository and permissions."

    log "SUCCESS" "Git operations completed successfully."
}

# --- 5b: Backup and Reporting ---
create_backup_archive() {
    if $ENABLE_ZIP; then
        log "INFO" "Creating full project backup ZIP archive..."
        run_cmd "zip -r -q '$BACKUP_ZIP' . \
            -x '.git/*' \
            -x 'venv/*' \
            -x 'node_modules/*' \
            -x '__pycache__/*' \
            -x 'backups/*' \
            -x 'logs/*' \
            -x 'git-update-push-logs/*' \
            -x 'dev-logs/*' \
            -x 'reports/*' \
            -x '*.DS_Store' \
            -x '.env' \
            -x 'inputs/*' \
            -x 'outputs/*' \
            -x 'exports/*' \
            -x 'art-uploads/*' \
            -x 'audit/*' \
            -x 'assets/*' \
            -x 'descriptions/*' \
            -x 'gdws_content/*' \
            -x 'mnt/*'"
        log "SUCCESS" "Backup ZIP created: $BACKUP_ZIP"
    else
        log "WARN" "Skipping ZIP archive creation as per --no-zip flag."
    fi

    log "INFO" "Generating markdown diff report..."
    local diff_content
    if git rev-parse -q --verify HEAD~1 >/dev/null 2>&1; then
        diff_content=$(git diff --name-status HEAD~1 HEAD)
    else
        diff_content="Initial commit or no parent commit found."
    fi

    {
        echo "# 🗂️ Diff Report — $(date '+%Y-%m-%d %H:%M %p')"
        echo ""
        echo "This report shows the file changes included in this commit and backup."
        echo ""
        echo "## Summary"
        echo "- **Commit Message:** \`$(git log -1 --pretty=%B)\`"
        echo "- **Backup Archive:** \`$(basename "$BACKUP_ZIP")\`"
        echo ""
        echo "## Changed Files"
        echo '```'
        if [[ -n "$diff_content" ]]; then
            echo "$diff_content"
        else
            echo "No file changes detected in the last commit."
        fi
        echo '```'
    } > "$DIFF_REPORT"
    log "SUCCESS" "Markdown diff report saved: $DIFF_REPORT"
}

# --- 5c: Run ArtNarrator Report ---
run_artnarrator_report() {
    if ! $ENABLE_REPORT_SCRIPT; then
        log "WARN" "Skipping ArtNarrator report script as per --no-report flag."
        return
    fi

    log "INFO" "Running ArtNarrator system report script..."
    if [ -f "./artnarrator-report.sh" ]; then
        run_cmd "./artnarrator-report.sh" || log "WARN" "The ArtNarrator report script encountered an error."
        log "SUCCESS" "ArtNarrator report script finished."
    else
        log "WARN" "ArtNarrator report script ('artnarrator-report.sh') not found. Skipping."
    fi
}

# --- 5d: Server Restart ---
restart_gunicorn_server() {
    if ! $ENABLE_RESTART; then
        log "WARN" "Skipping Gunicorn restart as per --no-restart flag."
        return
    fi

    log "INFO" "Initiating Gunicorn server restart..."
    run_cmd "find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null"
    run_cmd "find . -type f -name '*.pyc' -delete"

    if [ -f "$GUNICORN_PID_FILE" ]; then
        log "INFO" "Found existing Gunicorn PID file. Attempting graceful restart..."
        local pid
        pid=$(cat "$GUNICORN_PID_FILE")
        run_cmd "kill -HUP $pid"
        sleep 2
        if ps -p "$pid" > /dev/null; then
            log "SUCCESS" "Gunicorn gracefully reloaded with new code (PID: $pid)."
            return
        else
            log "WARN" "Gunicorn process with PID $pid was not found. Proceeding with full restart."
            rm -f "$GUNICORN_PID_FILE"
        fi
    fi

    log "INFO" "Performing a full stop-and-start of Gunicorn."
    pkill -f "$GUNICORN_APP_MODULE" || log "INFO" "No running Gunicorn processes to kill."
    sleep 2

    log "INFO" "Starting new Gunicorn instance..."
    local gunicorn_start_cmd="nohup $GUNICORN_CMD --workers $GUNICORN_WORKERS --bind $GUNICORN_BIND_ADDRESS --pid $GUNICORN_PID_FILE $GUNICORN_APP_MODULE"
    run_cmd "$gunicorn_start_cmd &"
    sleep 3

    if [ -f "$GUNICORN_PID_FILE" ] && ps -p "$(cat $GUNICORN_PID_FILE)" > /dev/null; then
        log "SUCCESS" "Gunicorn server restarted successfully (PID: $(cat $GUNICORN_PID_FILE))."
    else
        die "Gunicorn failed to start. Check logs for details."
    fi
}


# === [ SECTION 6: MAIN EXECUTION ] ====================================================
main() {
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"
    log "INFO" "=== 🟢 ArtNarrator Sync & Update Script Initialized ==="
    if $DRY_RUN; then
        log "WARN" "Dry run mode is enabled. No actual changes will be made."
    fi

    check_dependencies
    handle_git_operations
    create_backup_archive
    run_artnarrator_report
    restart_gunicorn_server

    log "SUCCESS" "🎉 All done, Robbie! Workflow completed successfully. 💚"
}

# Kick off the main function
main
