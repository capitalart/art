#!/bin/bash

# ======================================================================================
# 🔄 ArtNarrator Git Sync & Pre-Pull Backup Engine 🎨
#
# Version: 1.0
# Author: Robbie (adapted for ArtNarrator, July 2025, with ChatGPT)
#
# This script is designed to run after a PR/merge on the remote Git repo.
# It safely backs up the current state BEFORE pulling in new changes, for easy rollback.
#
# Workflow:
# 1. Backs up the current ArtNarrator code and database
# 2. Uploads this "pre-pull" backup to Google Drive (rclone)
# 3. Pulls latest code from the remote
# 4. Generates a Markdown report of what changed
# 5. Restarts the Gunicorn server to apply new code
#
# Usage examples:
#   ./git-update-pull.sh --full-auto      # Runs non-interactively
#   ./git-update-pull.sh --dry-run        # Only shows what would be done
#   ./git-update-pull.sh --no-pre-backup  # Skip backup/cloud sync
#   ./git-update-pull.sh --no-pull        # Skip git pull
#   ./git-update-pull.sh --no-report      # Skip project report
#   ./git-update-pull.sh --no-restart     # Skip server restart
# ======================================================================================

# === [ SECTION 1: SETUP & CONFIGURATION ] =============================================
set -euo pipefail

PROJECT_ROOT_DIR="$(pwd)"
LOG_DIR="${PROJECT_ROOT_DIR}/logs"
BACKUP_DIR="${PROJECT_ROOT_DIR}/backups"
DB_FILE="${PROJECT_ROOT_DIR}/data/artnarrator.db" # <<== Edit if your DB is elsewhere!
REPORT_SCRIPT="artnarrator-report.py"
GDRIVE_RCLONE_REMOTE="gdrive"
GDRIVE_BACKUP_FOLDER="artnarrator-backups"
CLOUD_RETENTION_COUNT=300

NOW=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/git-update-pull-${NOW}.log"
DB_DUMP_FILE="$BACKUP_DIR/pre-pull-db_dump_${NOW}.sql"
BACKUP_ZIP="$BACKUP_DIR/pre-pull-backup_${NOW}.zip"
PULL_DIFF_REPORT="$BACKUP_DIR/pull-diff-report_${NOW}.md"

# Gunicorn/Server config
GUNICORN_PID_FILE="/tmp/artnarrator-gunicorn.pid"
GUNICORN_CMD="${PROJECT_ROOT_DIR}/venv/bin/gunicorn"
GUNICORN_BIND_ADDRESS="0.0.0.0:7777" # <<== Edit if your port is different!
GUNICORN_WORKERS=4
GUNICORN_APP_MODULE="app:app" # <<== Edit if your WSGI entry is different!

# Colors for logging
COL_RESET='\033[0m'
COL_INFO='\033[0;36m'
COL_SUCCESS='\033[0;32m'
COL_WARN='\033[0;33m'
COL_ERROR='\033[0;31m'

# === [ SECTION 2: SCRIPT FLAGS & DEFAULTS ] ===========================================
AUTO_MODE=false
DRY_RUN=false
ENABLE_PRE_BACKUP=true
ENABLE_PULL=true
ENABLE_REPORT_SCRIPT=true
ENABLE_RESTART=true

# === [ SECTION 3: FLAG PARSER ] ======================================================
for arg in "$@"; do
  case $arg in
    --full-auto)     AUTO_MODE=true; shift ;;
    --dry-run)       DRY_RUN=true; shift ;;
    --no-pre-backup) ENABLE_PRE_BACKUP=false; shift ;;
    --no-pull)       ENABLE_PULL=false; shift ;;
    --no-report)     ENABLE_REPORT_SCRIPT=false; shift ;;
    --no-restart)    ENABLE_RESTART=false; shift ;;
    *) echo -e "${COL_ERROR}❌ Unknown option: $arg${COL_RESET}"; exit 1 ;;
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
  for cmd in git zip sqlite3 rclone; do
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

# --- 5a: Pre-Pull Backup ---
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
    -x '*.pyo'"
log "SUCCESS" "Pre-pull backup ZIP created: $BACKUP_ZIP"

  # --- Cloud Sync ---
  log "INFO" "Uploading pre-pull backup to Google Drive..."
  run_cmd "rclone copy '$BACKUP_ZIP' '$GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER' --progress" || log "ERROR" "Rclone upload failed. Check rclone configuration and network."
}

# --- 5b: Git Pull ---
handle_git_pull() {
  if ! $ENABLE_PULL; then
    log "WARN" "Skipping Git pull as per --no-pull flag."
    return
  fi

  log "INFO" "Preparing to pull updates from remote repository..."

  # Check for uncommitted changes
  if [[ -n $(git status --porcelain) ]]; then
    die "Working directory is not clean. Please commit or stash your changes before pulling."
  fi

  local pre_pull_hash
  pre_pull_hash=$(git rev-parse HEAD)
  log "INFO" "Current version (HEAD) is $pre_pull_hash"

  log "INFO" "Pulling latest changes from origin/main..."
  run_cmd "git pull origin main --rebase" || die "git pull --rebase failed. Please resolve conflicts manually."

  local post_pull_hash
  post_pull_hash=$(git rev-parse HEAD)
  log "SUCCESS" "Successfully pulled updates. New version (HEAD) is $post_pull_hash"

  # --- Diff Report (Post-Pull) ---
  log "INFO" "Generating report of changes pulled from remote..."
  local diff_content
  diff_content=$(git diff --name-status "$pre_pull_hash" "$post_pull_hash")
  {
    echo "# 🗂️ Git Pull Report — $(date '+%Y-%m-%d %H:%M %p')"
    echo ""
    echo "This report shows the file changes that were just pulled from the remote repository."
    echo ""
    echo "## Update Summary"
    echo "- **Previous Version:** \`$pre_pull_hash\`"
    echo "- **New Version:** \`$post_pull_hash\`"
    echo ""
    echo "## Files Updated"
    echo '```'
    if [[ -n "$diff_content" ]]; then
      echo "$diff_content"
    else
      echo "No new changes were pulled from the remote."
    fi
    echo '```'
  } > "$PULL_DIFF_REPORT"
  log "SUCCESS" "Pull diff report saved: $PULL_DIFF_REPORT"
}

# --- 5c: System Report ---
run_artnarrator_report() {
  if ! $ENABLE_REPORT_SCRIPT; then
    log "WARN" "Skipping ArtNarrator report script as per --no-report flag."
    return
  fi

  if [ -f "./$REPORT_SCRIPT" ]; then
    log "INFO" "Running ArtNarrator system report script..."
    run_cmd "python3 $REPORT_SCRIPT" || log "WARN" "The ArtNarrator report script encountered an error."
    log "SUCCESS" "System report script finished."
  else
    log "WARN" "ArtNarrator report script ('$REPORT_SCRIPT') not found. Skipping."
  fi
}

# --- 5d: Server Restart ---
restart_gunicorn_server() {
  if ! $ENABLE_RESTART; then
    log "WARN" "Skipping Gunicorn restart as per --no-restart flag."
    return
  fi

  log "INFO" "Initiating Gunicorn server restart to apply updates..."

  if [ -f "$GUNICORN_PID_FILE" ]; then
    log "INFO" "Found existing Gunicorn PID file. Attempting to stop the old server..."
    OLD_PID=$(cat "$GUNICORN_PID_FILE")
    if ps -p "$OLD_PID" > /dev/null; then
      run_cmd "kill $OLD_PID"
      log "INFO" "Sent stop signal to Gunicorn process $OLD_PID. Waiting for it to terminate..."
      for _ in {1..10}; do
        if ! ps -p "$OLD_PID" > /dev/null; then
          log "SUCCESS" "Old Gunicorn process has terminated."
          break
        fi
        sleep 1
      done
      if ps -p "$OLD_PID" > /dev/null; then
        log "WARN" "Gunicorn process $OLD_PID did not stop gracefully. Sending force kill."
        run_cmd "kill -9 $OLD_PID"
      fi
    else
      log "WARN" "PID $OLD_PID from PID file does not correspond to a running process. It might be stale."
    fi
    run_cmd "rm -f '$GUNICORN_PID_FILE'"
  else
    log "INFO" "No Gunicorn PID file found. Assuming server is not running."
  fi

  log "INFO" "Starting new Gunicorn server in daemon mode..."
  run_cmd "$GUNICORN_CMD --bind $GUNICORN_BIND_ADDRESS --workers $GUNICORN_WORKERS --daemon --pid '$GUNICORN_PID_FILE' $GUNICORN_APP_MODULE"

  sleep 2

  if [ -f "$GUNICORN_PID_FILE" ]; then
    NEW_PID=$(cat "$GUNICORN_PID_FILE")
    if ps -p "$NEW_PID" > /dev/null; then
      log "SUCCESS" "Gunicorn server restarted successfully. New PID is $NEW_PID."
    else
      die "Failed to start Gunicorn. PID file was created but no process found with PID $NEW_PID."
    fi
  else
    die "Failed to start Gunicorn. No PID file was created."
  fi
}

# === [ SECTION 6: main EXECUTION ] ==================================================
main() {
  mkdir -p "$BACKUP_DIR"
  log "INFO" "=== 🎨  ArtNarrator Sync & Update Script Initialized ==="
  if $DRY_RUN; then
    log "WARN" "Dry run mode is enabled. No actual changes will be made."
  fi

  check_dependencies
  handle_pre_pull_backup
  handle_git_pull
  run_artnarrator_report
  restart_gunicorn_server

  log "SUCCESS" "🎉 All done! ArtNarrator is updated and running. 💚"
}

main
