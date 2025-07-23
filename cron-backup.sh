#!/bin/bash

# ======================================================================================
# 🛡️ ArtNarrator Automated Backup Engine 🛡️
#
# Version: 1.1
# Author: Robbie (Adapted for ArtNarrator, Enhanced by Gemini)
#
# This script is designed to be run exclusively by cron for automated backups.
# It performs NO Git operations and NO server restarts. Its sole purpose is to:
# 1. Create a secure backup of the application code and database.
# 2. Upload the backup to a cloud remote (Google Drive).
# 3. Apply a retention policy to the cloud backups.
#
# ---
#
# Usage (for cron jobs):
#   /path/to/cron-backup.sh >> /path/to/logs/cron.log 2>&1
#
# Usage (for manual testing):
#   ./cron-backup.sh
#   ./cron-backup.sh --dry-run
#
# ======================================================================================

# === [ SECTION 1: SCRIPT SETUP & CONFIGURATION ] ======================================
set -euo pipefail

# --- Project & Backup Configuration ---
# Change to the ArtNarrator directory to ensure all paths are correct
cd /home/art/art || exit 1

PROJECT_ROOT_DIR="$(pwd)"
LOG_DIR="${PROJECT_ROOT_DIR}/logs"
BACKUP_DIR="${PROJECT_ROOT_DIR}/backups"

# --- Naming Conventions ---
NOW=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/cron-backup-${NOW}.log"
BACKUP_ZIP="$BACKUP_DIR/backup_${NOW}.zip"

# --- Cloud Configuration ---
GDRIVE_RCLONE_REMOTE="gdrive"
GDRIVE_BACKUP_FOLDER="artnarrator-backups"
CLOUD_RETENTION_COUNT=300  # Number of backups to keep in the cloud

# --- Colors for Logging ---
COL_RESET='\033[0m'
COL_INFO='\033[0;36m'
COL_SUCCESS='\033[0;32m'
COL_WARN='\033[0;33m'
COL_ERROR='\033[0;31m'

# --- Flag Parsing ---
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

# === [ SECTION 2: LOGGING & UTILITY FUNCTIONS ] =======================================
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
    for cmd in zip sqlite3 rclone; do
        if ! command -v "$cmd" &> /dev/null; then
            die "Required command '$cmd' is not installed. Aborting."
        fi
    done
    log "SUCCESS" "All required tools are present."
}

# === [ SECTION 3: SCRIPT WORKFLOW FUNCTIONS ] =========================================

create_backup_archive() {

    log "INFO" "Creating full project backup ZIP archive..."
    run_cmd "zip -r -q '$BACKUP_ZIP' . \
        -x '.git/*' -x 'venv/*' -x 'node_modules/*' -x '__pycache__/*' \
        -x 'backups/*' -x 'logs/*' -x 'git-update-push-logs/*' -x 'dev-logs/*' \
        -x 'reports/*' -x '*.DS_Store' -x '.env' -x 'inputs/*' -x 'outputs/*' \
        -x 'exports/*' -x 'art-uploads/*' -x 'audit/*' \
        -x 'assets/*' -x 'descriptions/*' -x 'gdws_content/*' -x 'mnt/*'"
    log "SUCCESS" "Backup ZIP created: $BACKUP_ZIP"
}

sync_to_cloud() {
    log "INFO" "Uploading backup to Google Drive ($GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER)..."
    run_cmd "rclone copy '$BACKUP_ZIP' '$GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER' --progress" || log "ERROR" "Rclone upload failed. Check rclone configuration and network."

    log "INFO" "Applying cloud retention policy (keeping last $CLOUD_RETENTION_COUNT backups)..."
    local files_to_delete
    files_to_delete=$(rclone lsf "$GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER" --format "tp" | sort -r | tail -n +$((CLOUD_RETENTION_COUNT + 1)) | cut -d';' -f2)

    if [[ -n "$files_to_delete" ]]; then
        log "WARN" "The following old backups will be deleted from the cloud:"
        echo "$files_to_delete" | tee -a "$LOG_FILE"
        while IFS= read -r file; do
            run_cmd "rclone delete '$GDRIVE_RCLONE_REMOTE:$GDRIVE_BACKUP_FOLDER/$file'"
        done <<< "$files_to_delete"
        log "SUCCESS" "Cloud retention policy applied."
    else
        log "INFO" "Fewer than $CLOUD_RETENTION_COUNT backups in the cloud. No cleanup needed."
    fi
}

# === [ SECTION 4: MAIN EXECUTION ] ====================================================
main() {
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"
    log "INFO" "=== 🛡️ ArtNarrator Automated Backup Initialized ==="
    if $DRY_RUN; then
        log "WARN" "Dry run mode is enabled. No actual changes will be made."
    fi

    check_dependencies
    create_backup_archive
    sync_to_cloud

    # Clean up the local backup files after successful upload
    log "INFO" "Cleaning up local backup files..."
    run_cmd "rm -f '$BACKUP_ZIP'"

    log "SUCCESS" "🎉 Automated backup workflow completed successfully. 💚"
}

# Kick off the main function
main
