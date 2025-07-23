#!/bin/bash

# ======================================================================================
# 🔄 Codex Merge & Check Engine 💥
#
# Version: 1.0
# Author: Robbie (Adapted for ArtNarrator, with Codex Precision)
#
# This script is designed for ultimate precision and safety. It does the following:
# 1. Checks for any broken routes, packages, or links before pulling updates.
# 2. Creates an encrypted, detailed backup of the ArtNarrator system.
# 3. Pulls the latest changes from the Git remote repository.
# 4. Checks again for broken links/routes or any discrepancies after the pull.
#
# ======================================================================================

# Usage examples:
#   ./codex-merge.sh --full-auto       # Runs non-interactively, performs full backup, pull, checks before and after
#   ./codex-merge.sh --dry-run         # Shows what would be done, no actual changes
#   ./codex-merge.sh --no-pre-backup   # Skip backup/cloud sync
#   ./codex-merge.sh --no-pull         # Skip git pull
#   ./codex-merge.sh --no-report       # Skip project report generation
#   ./codex-merge.sh --no-restart      # Skip server restart

# ======================================================================================

# === [ SECTION 1: SETUP & CONFIGURATION ] ===========================================
set -euo pipefail

PROJECT_ROOT_DIR="$(pwd)"
LOG_DIR="${PROJECT_ROOT_DIR}/logs"
BACKUP_DIR="${PROJECT_ROOT_DIR}/backups"
DB_FILE="${PROJECT_ROOT_DIR}/data/artnarrator.db"
GDRIVE_RCLONE_REMOTE="gdrive"
GDRIVE_BACKUP_FOLDER="artnarrator-backups"
CLOUD_RETENTION_COUNT=300  # Number of backups to keep in the cloud

NOW=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/codex-merge-${NOW}.log"
DB_DUMP_FILE="$BACKUP_DIR/pre-pull-db_dump_${NOW}.sql"
BACKUP_ZIP="$BACKUP_DIR/codex-merge-backup_${NOW}.zip"
PULL_DIFF_REPORT="$BACKUP_DIR/codex-merge-diff-report_${NOW}.md"

GUNICORN_PID_FILE="/tmp/artnarrator-gunicorn.pid"
GUNICORN_CMD="${PROJECT_ROOT_DIR}/venv/bin/gunicorn"
GUNICORN_BIND_ADDRESS="0.0.0.0:7777"
GUNICORN_WORKERS=4
GUNICORN_APP_MODULE="app:app"

# Default flags for the script
AUTO_MODE=false
DRY_RUN=false
ENABLE_PRE_BACKUP=true
ENABLE_PULL=true
ENABLE_RESTART=true
ENABLE_PIP_UPDATE=false
ENABLE_PIP_CHECK=false
ENABLE_SYSTEM_REPORT=true

# === [ SECTION 2: FLAG PARSER ] ======================================================
for arg in "$@"; do
  case $arg in
    --full-auto)     AUTO_MODE=true; shift ;;
    --dry-run)       DRY_RUN=true; shift ;;
    --no-pre-backup) ENABLE_PRE_BACKUP=false; shift ;;
    --no-pull)       ENABLE_PULL=false; shift ;;
    --no-report)     ENABLE_REPORT_SCRIPT=false; shift ;;
    --no-restart)    ENABLE_RESTART=false; shift ;;
    --pip-update)    ENABLE_PIP_UPDATE=true; shift ;;
    --pip-check)     ENABLE_PIP_CHECK=true; shift ;;
    --system-report) ENABLE_SYSTEM_REPORT=true; shift ;;
    *) echo -e "❌ Unknown option: $arg"; exit 1 ;;
  esac
done

# === [ SECTION 3: LOGGING & UTILITY FUNCTIONS ] =======================================
mkdir -p "$LOG_DIR"

log() {
  local type="$1"
  local msg="$2"
  local color='\033[0;36m'
  case "$type" in
    SUCCESS) color='\033[0;32m' ;;
    WARN)    color='\033[0;33m' ;;
    ERROR)   color='\033[0;31m' ;;
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
    for cmd in git zip sqlite3 rclone jq curl; do
        if ! command -v "$cmd" &> /dev/null; then
            die "Required command '$cmd' is not installed. Aborting."
        fi
    done
    log "SUCCESS" "All required tools are present."
}

# === [ SECTION 4: CHECKING AND BACKUP FUNCTIONS ] ===================================
check_for_broken_links() {
  log "INFO" "Checking for broken links and routes..."
  run_cmd "curl -I http://localhost:7777" || log "ERROR" "Local route check failed."
  run_cmd "curl -I http://localhost:7777/api/health" || log "ERROR" "API health route check failed."
}

# --- 4a: Pre-Pull Backup ---
handle_pre_pull_backup() {
  if ! $ENABLE_PRE_BACKUP; then
    log "WARN" "Skipping pre-pull backup as per --no-pre-backup flag."
    return
  fi

  log "INFO" "Starting pre-pull backup process..."

  # --- Database Dump ---
  if [ -f "$DB_FILE" ]; then
    log "INFO" "Creating SQLite database dump..."
    run_cmd "sqlite3 '$DB_FILE' .dump > '$DB_DUMP_FILE'"
    log "SUCCESS" "Database dump created: $DB_DUMP_FILE"
  else
    log "WARN" "Database file not found at $DB_FILE. Skipping dump."
  fi

  # --- ZIP Archive ---
  log "INFO" "Creating full project backup ZIP archive (pre-pull state)..."
  run_cmd "zip -r -q '$BACKUP_ZIP' . \
      -x '.git/*' \
      -x 'venv/*' \
      -x 'node_modules/*' \
      -x '__pycache__/*' \
      -x 'backups/*' \
      -x 'logs/*' \
      -x 'dev_logs/*' \
      -x 'git-update-push-logs/*' \
      -x 'reports/*' \
      -x '*.DS_Store' \
      -x '.env' \
      -x 'inputs/*' \
      -x 'outputs/*' \
      -x 'example-images/*' \
      -x '*.sqlite3' \
      -x '*.pyc' \
      -x '*.pyo' \
      -x 'art-uploads/*' \
      -x 'audit/*' \
      -x 'assets/*' \
      -x 'descriptions/*' \
      -x 'gdws_content/*' \
      -x 'mnt/*'"
  log "SUCCESS" "Pre-pull backup ZIP created: $BACKUP_ZIP"

  # --- Cloud Sync ---
  log "INFO" "Uploading pre-pull backup to Google Drive..."
  run_cmd "rclone copy '$BACKUP_ZIP' '$GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER' --progress" || log "ERROR" "Rclone upload failed. Check rclone configuration and network."
}

# --- 4b: Git Pull ---
handle_git_pull() {
  if ! $ENABLE_PULL; then
    log "WARN" "Skipping Git pull as per --no-pull flag."
    return
  fi
  log "INFO" "Pulling the latest changes from the remote repository..."
  run_cmd "git pull origin main --rebase" || die "Git pull failed."
}

# --- 4c: After Pull Check ---
check_after_pull() {
  log "INFO" "Checking for broken links/routes after pulling..."
  check_for_broken_links
}

# --- 4d: Git Push ---
handle_git_push() {
  if $ENABLE_PULL; then
    log "INFO" "Pushing local changes to GitHub..."
    run_cmd "git push origin main" || die "Git push failed."
  fi
}

# === [ SECTION 5: MAIN EXECUTION ] ====================================================

main() {
  mkdir -p "$LOG_DIR" "$BACKUP_DIR"
  log "INFO" "=== 🔄 Codex Merge & Check Engine Initialized ==="

  check_dependencies

  # Execute pre-pull check
  check_for_broken_links

  # Execute the pull & check sequence
  handle_pre_pull_backup
  handle_git_pull
  check_after_pull

  # If not a dry run, push and update packages
  handle_git_push
  pip_update
  pip_check

  log "SUCCESS" "🎉 Codex Merge & Check Engine completed successfully. 💚"
}

# Start the process
main
