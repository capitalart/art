#!/bin/bash

# =====================================================
# 🔁 ART Narrator Git Update + Commit + Push + Backup
# 💥 Robbie Mode™ Gitflow Commander + Backup Engine + Cloud Upload + Gunicorn Full Cachebuster
# 
# Usage:
#   ./git-update-push.sh --full-auto      # Does everything
#   ./git-update-push.sh --just git       # Skip everything else
#   ./git-update-push.sh --no-zip         # Skip local ZIP backup
#   ./git-update-push.sh --no-cloud       # Skip rclone upload to Google Drive
#   ./git-update-push.sh --no-retention   # Skip retention cleanup in Google Drive
#   ./git-update-push.sh --no-git         # Skip git pull/push sync
#
# === Deploys, Purges All Caches, and Reloads Gunicorn ===
# === Add to crontab for nightly auto-backups if desired ===
# =====================================================

set -euo pipefail

# === [ SECTION 1: INIT & PATHS ] =====================
LOG_DIR="git-update-push-logs"
BACKUP_DIR="backups"
mkdir -p "$LOG_DIR" "$BACKUP_DIR"

NOW=$(date '+%Y-%m-%d-%H-%M-%p')
LOG_FILE="$LOG_DIR/git-update-push-${NOW}.log"
BACKUP_ZIP="$BACKUP_DIR/${NOW}_backup.zip"
DIFF_RAW="$BACKUP_DIR/diff-raw.txt"
DIFF_REPORT="$BACKUP_DIR/backup-diff-REPORT.md"
COMMIT_MSG_FILE=".codex-commit-msg.txt"
GDRIVE_REMOTE="gdrive-local"
GDRIVE_FOLDER="capitalart-backups"

# === [ SECTION 2: DEFAULT FLAGS ] ====================
AUTO_MODE=false
ENABLE_ZIP=true
ENABLE_CLOUD=true
ENABLE_RETENTION=true
ENABLE_GIT=true
JUST_GIT=false

# === [ SECTION 3: FLAG PARSER ] ======================
for arg in "$@"; do
  case $arg in
    --auto|--full-auto) AUTO_MODE=true ;;
    --no-zip)           ENABLE_ZIP=false ;;
    --no-cloud)         ENABLE_CLOUD=false ;;
    --no-retention)     ENABLE_RETENTION=false ;;
    --no-git)           ENABLE_GIT=false ;;
    --just|--just-git)  JUST_GIT=true ;;
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

log "=== 🟢 ART Narrator Git + Backup Script Started ==="

# === [ SECTION 5: GIT STAGING + COMMIT ] =============
log "📂 Checking git status..."
git status | tee -a "$LOG_FILE"

log "➕ Staging all changes..."
git add . 2>>"$LOG_FILE"

if $AUTO_MODE; then
  if [[ -s "$COMMIT_MSG_FILE" ]]; then
    commit_msg=$(cat "$COMMIT_MSG_FILE")
    log "📝 Using Codex commit message: $commit_msg"
  else
    commit_msg="Auto commit: Preparing for Codex upgrade"
    log "📝 Using fallback commit message: $commit_msg"
  fi
else
  read -rp "📝 Enter commit message: " commit_msg
fi

log "✅ Committing changes..."
git commit -m "$commit_msg" 2>>"$LOG_FILE" || log "⚠️ Nothing to commit."
[[ -s "$COMMIT_MSG_FILE" ]] && rm -f "$COMMIT_MSG_FILE"

# === [ SECTION 6: RUN total-rundown ] ================
if [ -f "./art_narrator_total_rundown.py" ]; then
  log "🧠 Running ART Narrator Total Rundown..."
  python3 art_narrator_total_rundown.py >> "$LOG_FILE" 2>&1 || log "⚠️ Rundown script failed."
else
  log "ℹ️ Rundown script not found."
fi

# === [ SECTION 7: SKIP ZIP+BACKUP IF JUST_GIT ] ======
if $JUST_GIT; then
  log "⏹️ JUST GIT MODE: Skipping all backup & cloud steps."
  exit 0
fi

# === [ SECTION 8: BACKUP ZIP CREATION ] =============
if $ENABLE_ZIP; then
  log "📦 Creating full backup ZIP archive..."
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

# === [ SECTION 9: DIFF REPORT ] ======================
log "📄 Generating markdown diff report..."
git diff --name-status HEAD~1 HEAD > "$DIFF_RAW"

{
  echo "# 🗂️ Diff Report — $(date '+%Y-%m-%d %H:%M %p')"
  echo "Backup file: \`$BACKUP_ZIP\`"
  echo ""
  echo "## 📂 Changed Files:"
  if [[ -s "$DIFF_RAW" ]]; then
    cat "$DIFF_RAW"
  else
    echo "_No changes since last commit_"
  fi
} > "$DIFF_REPORT"
log "✅ Markdown diff report saved: $DIFF_REPORT"

# === [ SECTION 10: GIT PULL + PUSH ] =================
if $ENABLE_GIT; then
  log "🔄 Pulling latest from origin/main..."
  git pull origin main --rebase 2>>"$LOG_FILE" || {
    log "❌ git pull --rebase failed."
    exit 1
  }

  log "🚀 Pushing to origin/main..."
  git push origin main 2>>"$LOG_FILE" || {
    log "❌ git push failed."
    exit 2
  }
else
  log "⏭️ Skipping git pull/push (flag --no-git)"
fi

# === [ SECTION 11: CLOUD BACKUP ] ====================
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

# === [ SECTION 12: RETENTION (MAX 20 FILES) ] ========
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

# === [ SECTION 13: GUNICORN + CACHE PURGE + RELOAD ] ==================
log "🧹 Purging old Python cache, __pycache__, and bytecode..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

GUNICORN_CMD="$PWD/venv/bin/gunicorn"
if [ ! -x "$GUNICORN_CMD" ]; then
  log "❌ Gunicorn binary not found at $GUNICORN_CMD"
  exit 3
fi

log "🛑 Stopping existing Gunicorn processes..."
pkill -u "$USER" -f 'gunicorn' || log "🔍 No Gunicorn processes found."
sleep 3

if lsof -i :8070 | grep LISTEN; then
  log "⚠️ Port 8070 is still in use! Gunicorn may not restart cleanly."
fi

log "♻️ Starting fresh Gunicorn: $GUNICORN_CMD -w 4 -b 0.0.0.0:8070 app:app"
nohup "$GUNICORN_CMD" -w 4 -b 0.0.0.0:8070 app:app >> "$LOG_FILE" 2>&1 &
sleep 3

if pgrep -f 'gunicorn' > /dev/null; then
  PID=$(pgrep -f 'gunicorn' | head -1)
  log "✅ Gunicorn restart confirmed (PID $PID)!"
else
  log "❌ Gunicorn did not restart as expected! Check logs ASAP."
fi

log "🔍 Flask/Gunicorn cache purged. All template, route, and static changes will now show live."


# === [ DONE ] ========================================
log "🎉 All done, Robbie! Git, ZIP, rundown, cloud and cleanup complete. 💚"
