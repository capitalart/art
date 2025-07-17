#!/bin/bash

# =====================================================
# 🔄 ART Narrator Git Pull + Rundown + Backup
# 💥 Robbie Mode™ Gitflow Sync Commander (Pull First)
#
# Usage:
#   ./git-update-pull.sh --full-auto      # Does everything
#   ./git-update-pull.sh --no-zip         # Skip local ZIP backup
#   ./git-update-pull.sh --no-cloud       # Skip rclone upload to Google Drive
#   ./git-update-pull.sh --no-retention   # Skip retention cleanup in Google Drive
#
# === Pulls first, then logs, snapshots, backups, cloud syncs ===
# =====================================================

set -euo pipefail

# === [ SECTION 1: INIT & PATHS ] =====================
LOG_DIR="git-update-push-logs"
BACKUP_DIR="backups"
mkdir -p "$LOG_DIR" "$BACKUP_DIR"

NOW=$(date '+%Y-%m-%d-%H-%M-%p')
LOG_FILE="$LOG_DIR/git-update-pull-${NOW}.log"
BACKUP_ZIP="$BACKUP_DIR/${NOW}_pull_backup.zip"
DIFF_RAW="$BACKUP_DIR/pull-diff-raw.txt"
DIFF_REPORT="$BACKUP_DIR/pull-backup-diff-REPORT.md"
GDRIVE_REMOTE="gdrive-local"
GDRIVE_FOLDER="capitalart-backups"

# === [ SECTION 2: DEFAULT FLAGS ] ====================
AUTO_MODE=false
ENABLE_ZIP=true
ENABLE_CLOUD=true
ENABLE_RETENTION=true

# === [ SECTION 3: FLAG PARSER ] ======================
for arg in "$@"; do
  case $arg in
    --auto|--full-auto) AUTO_MODE=true ;;
    --no-zip)           ENABLE_ZIP=false ;;
    --no-cloud)         ENABLE_CLOUD=false ;;
    --no-retention)     ENABLE_RETENTION=false ;;
    *) echo "❌ Unknown option: $arg"; exit 1 ;;
  esac
done

# === [ SECTION 4: LOG FUNCTION ] =====================
function log() {
  local msg="$1"
  local ts
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  echo "[$ts] $msg" | tee -a "$LOG_FILE"
}

log "=== 🟣 ART Narrator Git Pull + Rundown Started ==="

# === [ SECTION 5: GIT PULL FIRST ] ===================
log "🔄 Pulling latest from origin/main..."
git pull origin main --rebase 2>>"$LOG_FILE" || {
  log "❌ git pull --rebase failed."
  exit 1
}

# === [ SECTION 6: RUN Total Rundown ] ===============
if [ -f "./art_narrator_total_rundown.py" ]; then
  log "🧠 Running ART Narrator Total Rundown..."
  python3 art_narrator_total_rundown.py >> "$LOG_FILE" 2>&1 || log "⚠️ Rundown script failed."
else
  log "ℹ️ Rundown script not found."
fi

# === [ SECTION 7: BACKUP ZIP CREATION ] =============
if $ENABLE_ZIP; then
  log "📦 Creating backup ZIP archive..."
  zip -r "$BACKUP_ZIP" . \
    -x ".git/*" \
    -x "*.git*" \
    -x "__pycache__/*" \
    -x "node_modules/*" \
    -x "venv/*" \
    -x "outputs/*" \
    -x "inputs/*" \
    -x ".cache/*" \
    -x ".mypy_cache/*" \
    -x ".pytest_cache/*" \
    -x "$BACKUP_DIR/*" \
    -x "$LOG_DIR/*" \
    -x "*.DS_Store" \
    -x "*.pyc" \
    -x "*.pyo" \
    -x ".env" \
    -x "*.sqlite3" >> "$LOG_FILE"
  log "✅ Backup ZIP created: $BACKUP_ZIP"
else
  log "⏭️ Skipping ZIP backup (flag --no-zip)"
fi

# === [ SECTION 8: DIFF REPORT ] ======================
log "📄 Generating markdown diff report..."
git diff --name-status HEAD~1 HEAD > "$DIFF_RAW"

{
  echo "# 🗂️ Diff Report (Post-Pull) — $(date '+%Y-%m-%d %H:%M %p')"
  echo "Backup file: \`$BACKUP_ZIP\`"
  echo ""
  echo "## 📂 Changed Files:"
  if [[ -s "$DIFF_RAW" ]]; then
    cat "$DIFF_RAW"
  else
    echo "_No changes since last pull_"
  fi
} > "$DIFF_REPORT"
log "✅ Markdown diff report saved: $DIFF_REPORT"

# === [ SECTION 9: CLOUD BACKUP ] =====================
if $ENABLE_CLOUD; then
  log "☁️ Uploading to Google Drive ($GDRIVE_REMOTE:$GDRIVE_FOLDER)..."
  if command -v rclone >/dev/null 2>&1; then
    if rclone copy "$BACKUP_ZIP" "$GDRIVE_REMOTE:$GDRIVE_FOLDER" >> "$LOG_FILE" 2>&1; then
      log "✅ Uploaded to Drive folder: $GDRIVE_FOLDER"
    else
      log "❌ Rclone upload failed."
    fi
  else
    log "⚠️ rclone not found — skipping upload."
  fi
else
  log "⏭️ Skipping cloud upload (flag --no-cloud)"
fi

# === [ SECTION 10: RETENTION (MAX 20 FILES) ] ========
if $ENABLE_RETENTION && $ENABLE_CLOUD; then
  log "🧹 Applying cloud retention policy (max 20 backups)..."
  if command -v rclone >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
    OLD_FILES=$(rclone lsjson "$GDRIVE_REMOTE:$GDRIVE_FOLDER" \
   | jq -r '.[] | select(.IsDir == false) | "\(.ModTime) \(.Path)"' \
   | sort \
   | tail -n +21 | cut -d' ' -f2-)

    if [[ -n "$OLD_FILES" ]]; then
      while IFS= read -r file; do
        log "🗑️ Deleting old backup: $file"
        rclone delete "$GDRIVE_REMOTE:$GDRIVE_FOLDER/$file" >> "$LOG_FILE" 2>&1 || true
      done <<< "$OLD_FILES"
      log "✅ Cloud cleanup complete."
    else
      log "ℹ️ Less than 30 cloud files — no cleanup needed."
    fi
  else
    log "⚠️ jq or rclone not found — skipping retention."
  fi
else
  log "⏭️ Skipping cloud retention (flag --no-retention or --no-cloud)"
fi

# === [ DONE ] ========================================
log "🎉 All done, Robbie! Pull, Rundown, ZIP, Cloud, and Diff complete. 💚"
