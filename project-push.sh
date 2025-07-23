#!/bin/bash

# ============================
#  Robbie's Super Project Push Toolkit
# ============================
# Safely backup, commit, and push all project repos in /home.
# Author: Robbie + Codex
# ============================

# 1. Detect all project dirs in /home (ignore 'robin' and dotfolders)
PROJECTS=$(find /home -mindepth 1 -maxdepth 1 -type d ! -name 'robin' ! -name '.*' -exec basename {} \; | sort)
if [[ -z "$PROJECTS" ]]; then
  echo "No projects found in /home!"
  exit 1
fi

echo "Available projects:"
select PROJECT in $PROJECTS "Exit"; do
  [[ $REPLY == $(( $(echo "$PROJECTS" | wc -w) + 1 )) ]] && exit 0
  [[ -n "$PROJECT" ]] && break
done

cd /home/$PROJECT || { echo "Could not cd to /home/$PROJECT"; exit 1; }
echo "Working in: /home/$PROJECT"

# 2. Try to activate venv if it exists
if [[ -f venv/bin/activate ]]; then
  source venv/bin/activate
  VENV_ACTIVE=1
  echo "(venv) activated"
else
  VENV_ACTIVE=0
  echo "No venv found. Skipping venv activation."
fi

# 3. Main menu
while true; do
  echo
  echo "Choose a PUSH action:"
  echo "  1) Safe Push with Google Drive Backup"
  echo "  2) Quick Commit & Push (No Backup)"
  echo "  3) Safe Local Backup Before Push"
  echo "  4) Safe Local & GDrive Backups & Safe Push"
  echo "  5) Exit"
  read -rp "Selection: " SEL
  NOW=$(date "+%a-%d-%b-%Y-%I-%M-%p")
  BACKUPNAME="backup_${NOW}"

  case "$SEL" in
    1)
      mkdir -p backups
      zip -r -q "backups/${BACKUPNAME}.zip" . \
        -x '.git/*' 'venv/*' 'node_modules/*' '__pycache__/*' 'backups/*' 'logs/*' \
        'dev_logs/*' 'git-update-push-logs/*' 'reports/*' '*.DS_Store' '.env' 'inputs/*' \
        'outputs/*' 'uploads_temp/*' 'example-images/*' '*.sqlite3' '*.pyc' '*.pyo' 'art-processing/*'
      echo "Local backup created: backups/${BACKUPNAME}.zip"
      if command -v rclone >/dev/null; then
        rclone copy "backups/${BACKUPNAME}.zip" gdrive:${PROJECT}-backups --progress
        echo "Backup uploaded to Google Drive: gdrive:${PROJECT}-backups"
      else
        echo "rclone not found! Skipping Google Drive upload."
      fi
      git add .
      git commit -m "Quick update push — $(date '+%Y-%m-%d %I:%M %p')"
      git push origin master
      ;;
    2)
      git add .
      git commit -m "Quick update push — $(date '+%Y-%m-%d %I:%M %p')"
      git push origin master
      ;;
    3)
      mkdir -p backups
      tar czf backups/${BACKUPNAME}.tar.gz \
        --exclude=venv --exclude=backups --exclude=inputs --exclude=outputs \
        --exclude=reports --exclude=logs --exclude=uploads_temp --exclude=art-processing \
        --exclude=PREVIOUS-CODE-STACKS .
      echo "Local backup created: backups/${BACKUPNAME}.tar.gz"
      git add .
      git commit -m "Quick update push — $(date '+%Y-%m-%d %I:%M %p')"
      git push origin master
      ;;
    4)
      # NEW: Both local and GDrive backups, then push
      mkdir -p backups
      zip -r -q "backups/${BACKUPNAME}.zip" . \
        -x '.git/*' 'venv/*' 'node_modules/*' '__pycache__/*' 'backups/*' 'logs/*' \
        'dev_logs/*' 'git-update-push-logs/*' 'reports/*' '*.DS_Store' '.env' 'inputs/*' \
        'outputs/*' 'uploads_temp/*' 'example-images/*' '*.sqlite3' '*.pyc' '*.pyo' 'art-processing/*'
      echo "Local backup created: backups/${BACKUPNAME}.zip"
      if command -v rclone >/dev/null; then
        rclone copy "backups/${BACKUPNAME}.zip" gdrive:${PROJECT}-backups --progress
        echo "Backup uploaded to Google Drive: gdrive:${PROJECT}-backups"
      else
        echo "rclone not found! Skipping Google Drive upload."
      fi
      git add .
      git commit -m "Quick update push — $(date '+%Y-%m-%d %I:%M %p')"
      git push origin master
      ;;
    5) exit 0 ;;
    *) echo "Invalid selection, try again." ;;
  esac
done
