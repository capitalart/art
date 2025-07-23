#!/bin/bash

# ======================================================================================
# Robbie’s Mega Project Toolkit (Robbie Mode™: FULLY Deterministic, Includes-Only, No Guessing)
# Author: Robbie & ChatGPT (2025-07-23)
# ======================================================================================

set -euo pipefail

# --------- CONFIG ---------------------------------------------------------
PROJECTS=("art" "ezy" "thebigshed")
PROJECTS_PATH="/home"
DEFAULT_BRANCH="master"
GDRIVE_REMOTE="gdrive"
GDRIVE_BACKUP_FOLDER="project-backups"
LOG_DIR="logs"
INCLUDES_FILE="backup_includes.txt"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/project-toolkit-$(date +'%Y-%m-%d_%H-%M-%S').log"

# --------------- UTILS ---------------------------------------------------
log() {
  local t="$1"; shift
  local col="\033[1;36m"
  [ "$t" == "SUCCESS" ] && col="\033[1;32m"
  [ "$t" == "ERROR" ] && col="\033[1;31m"
  [ "$t" == "WARN" ] && col="\033[1;33m"
  echo -e "${col}[$t]\033[0m $*" | tee -a "$LOG_FILE"
}
die() {
  log ERROR "$*"
  echo -e "\n[ABORTED] See above error. Exiting for your own safety, legend!"
  exit 1
}

# --------------- PROJECT SELECTOR ----------------------------------------
select_project() {
  echo -e "\n========================\n      PROJECTS\n========================"
  select p in "${PROJECTS[@]}" "Exit"; do
    if [[ "$p" == "Exit" ]]; then exit 0; fi
    for test in "${PROJECTS[@]}"; do
      if [[ "$p" == "$test" ]]; then
        PROJECT="$p"
        PROJECT_PATH="$PROJECTS_PATH/$p"
        cd "$PROJECT_PATH"
        CODESTACK_SCRIPT="$PROJECT_PATH/code-stacker.sh"
        log INFO "Working in: $PROJECT_PATH"
        return 0
      fi
    done
    echo "Invalid selection."
  done
}

# --------------- MENUS ---------------------------------------------------
main_menu() {
  echo -e "\n========================\n      MAIN MENU\n========================"
  echo "  [1] PULL ACTIONS"
  echo "  [2] PUSH ACTIONS"
  echo "  [3] Restore/Extract Backup"
  echo "  [4] Show Recent Backups/Reports"
  echo "  [5] SYSTEM ACTIONS"
  echo "  [6] DRY RUN: See What Will Be Backed Up"
  echo "  [7] Run AI Artwork Analysis Self-Test"
  echo "  [0] Exit"
  read -rp "Select: " sel
  case "$sel" in
    1) pull_menu ;;
    2) push_menu ;;
    3) restore_backup ;;
    4) show_backups ;;
    5) sys_menu ;;
    6) backup_dryrun_menu ;;
    7) ai_selftest_menu ;;
    0) exit 0 ;;
    *) echo "Invalid selection." ;;
  esac
  main_menu
}

# --------------- HEALTH / DEPENDENCY CHECKS ------------------------------
health_and_deps_check() {
  log INFO "Running Health/Dependency Checks..."
  if [[ ! -d venv ]]; then die "Python venv not found!"; fi
  source venv/bin/activate || die "Could not activate venv!"
  pip check || die "pip check reported broken requirements!"
  python3 -c "import openai; print('✅ OpenAI Python installed.')" || die "OpenAI Python not installed."
  [[ -f .env ]] || die ".env file is missing!"
  if ! curl -fs http://localhost:7777/healthz >/dev/null 2>&1; then
    die "/health endpoint is not responding! Fix your stack before continuing."
  else
    log SUCCESS "Local route /healthz check OK"
  fi
}

# --------------- CODE STACK / QA -----------------------------------------
run_code_stack() {
  log INFO "Generating code stack / QA report..."
  if [[ -x "$CODESTACK_SCRIPT" ]]; then
    bash "$CODESTACK_SCRIPT"
    log SUCCESS "Code stack generated."
  else
    log WARN "$CODESTACK_SCRIPT not found/skipped."
  fi
}

# --------------- BACKUPS (INCLUDES ONLY) ---------------------------------
gdrive_backup() {
  local now=$(date "+%a-%d-%b-%Y-%I-%M-%p")
  mkdir -p backups
  local backup_zip="backups/backup_${now}.zip"
  log INFO "Creating ZIP backup: $backup_zip"
  if [[ -f "$INCLUDES_FILE" ]]; then
    zip -r -q "$backup_zip" -@ < "$INCLUDES_FILE"
  else
    die "INCLUDES file ($INCLUDES_FILE) not found!"
  fi
  log INFO "Uploading backup to Google Drive..."
  rclone copy "$backup_zip" "$GDRIVE_REMOTE:$GDRIVE_BACKUP_FOLDER" --progress && log SUCCESS "GDrive backup uploaded." || log ERROR "GDrive upload failed."
}

local_backup() {
  local now=$(date "+%a-%d-%b-%Y-%I-%M-%p")
  mkdir -p backups
  local backup_tar="backups/backup_${now}.tar.gz"
  log INFO "Creating local tar.gz backup: $backup_tar"
  if [[ -f "$INCLUDES_FILE" ]]; then
    tar czf "$backup_tar" -T "$INCLUDES_FILE"
  else
    die "INCLUDES file ($INCLUDES_FILE) not found!"
  fi
  log SUCCESS "Local backup complete."
}

# --------------- BACKUP DRY RUN MENU -------------------------------------
backup_dryrun_menu() {
  echo -e "\n--------------------------\nBACKUP DRY RUN\n--------------------------"
  echo "  [1] Show files/folders that WILL be backed up (from $INCLUDES_FILE)"
  echo "  [2] Show all file paths that WILL be included (expanded)"
  echo "  [0] Back to Main Menu"
  read -rp "Select: " drysel
  case "$drysel" in
    1)
      echo "========== backup_includes.txt ==========" > files-being-backed-up.txt
      cat "$INCLUDES_FILE" | tee -a files-being-backed-up.txt
      echo -e "\n✅ Files/folders to be backed up listed in files-being-backed-up.txt\n"
      ;;
    2)
      > files-being-backed-up-expanded.txt
      while read -r line; do
        [[ -z "$line" ]] && continue
        [[ "$line" =~ ^# ]] && continue
        if [[ -d "$line" ]]; then
          find "$line" -type f >> files-being-backed-up-expanded.txt 2>/dev/null
        elif [[ -f "$line" ]]; then
          echo "$line" >> files-being-backed-up-expanded.txt
        fi
      done < "$INCLUDES_FILE"
      sort files-being-backed-up-expanded.txt | uniq | tee files-being-backed-up-expanded.txt
      echo -e "\n✅ Expanded file list written to files-being-backed-up-expanded.txt\n"
      ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
  backup_dryrun_menu
}

# --------------- RESTART SERVICES ----------------------------------------
restart_services() {
  log INFO "Restarting gunicorn/nginx (if running)..."
  sudo systemctl restart gunicorn || log WARN "Gunicorn restart failed."
  sudo systemctl restart nginx || log WARN "Nginx restart failed."
  log SUCCESS "Services restarted."
}

# --------------- SAFE GIT ------------------------------------------------
safe_git_pull() {
  git checkout "$DEFAULT_BRANCH"
  git pull origin "$DEFAULT_BRANCH"
  log SUCCESS "Git pull complete."
}
safe_git_push() {
  git add .
  git commit -m "Quick update push — $(date '+%Y-%m-%d %I:%M %p')" || log INFO "Nothing to commit."
  git push origin "$DEFAULT_BRANCH"
  log SUCCESS "Git push complete."
}

# --------------- FAST / QUICK MODES --------------------------------------
fast_git_pull() {
  log WARN "Running FAST GIT PULL (No safety checks, no backup, no QA, no service restarts)"
  git checkout "$DEFAULT_BRANCH"
  git pull origin "$DEFAULT_BRANCH"
  log SUCCESS "Fast git pull complete."
}
quick_git_push() {
  log WARN "Running QUICK GIT PUSH (No safety checks, no backup, no QA, no service restarts)"
  git add .
  git commit -m "Quick push — $(date '+%Y-%m-%d %I:%M %p')" || log INFO "Nothing to commit."
  git push origin "$DEFAULT_BRANCH"
  log SUCCESS "Quick git push complete."
}

# --------------- FULL ACTIONS --------------------------------------------
full_pull() {
  health_and_deps_check
  run_code_stack
  gdrive_backup
  local_backup
  safe_git_pull
  restart_services
  log SUCCESS "[PULL] All steps completed."
}
full_push() {
  health_and_deps_check
  run_code_stack
  gdrive_backup
  local_backup
  safe_git_push
  restart_services
  log SUCCESS "[PUSH] All steps completed."
}

# --------------- SYSTEM ACTIONS (SYS1) -----------------------------------
sys_menu() {
  echo -e "\n--------------------------\nSYSTEM ACTIONS\n--------------------------"
  echo "  [SYS1] Full System Check + Code Stacker: Health/Dependency Checks, QA Report, GDrive Backup, Local Backup, Run Code Stacker, Gunicorn/Nginx Restart"
  echo "  [0] Back to Main Menu"
  read -rp "Selection: " syssel
  case "$syssel" in
    SYS1|1) sys1_action ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
  sys_menu
}
sys1_action() {
  log INFO "[SYS1] Starting Full System Check + Code Stacker"
  health_and_deps_check || die "Health/Dependency check failed."
  run_code_stack
  gdrive_backup
  local_backup
  if [[ -x "$CODESTACK_SCRIPT" ]]; then
    log INFO "Running code-stacker.sh..."
    bash "$CODESTACK_SCRIPT"
    log SUCCESS "code-stacker.sh completed."
  else
    log WARN "$CODESTACK_SCRIPT not found or not executable. Skipping."
  fi
  restart_services
  log SUCCESS "[SYS1] System check & code stack completed."
}

# --------------- AI ARTWORK ANALYSIS SELF-TESTS --------------------------
ai_selftest_openai() {
  log INFO "[SelfTest] Running OpenAI Artwork Analysis Self-Test"
  TEST_IMAGES=(tests/opneai-analysys-tests/*/test-image-*-for-analyse.jpg)
  if [[ ${#TEST_IMAGES[@]} -eq 0 ]]; then
    log WARN "No OpenAI test images found. Skipping."
    return
  fi
  PICKED_IMAGE="${TEST_IMAGES[RANDOM % ${#TEST_IMAGES[@]}]}"
  FOLDER=$(dirname "$PICKED_IMAGE")
  BASENAME=$(basename "$PICKED_IMAGE" .jpg)
  OUTFILE="$FOLDER/${BASENAME}-openai-$(date +'%Y-%m-%d_%H-%M-%S').json"

  log INFO "Testing OpenAI analysis on: $PICKED_IMAGE"
  python3 /home/art/scripts/analyze_artwork.py "$PICKED_IMAGE" --provider openai --json-output > "$OUTFILE" 2>&1

  if grep -q '"aspect_ratio"' "$OUTFILE"; then
    log SUCCESS "OpenAI artwork analysis succeeded! Output: $OUTFILE"
  else
    log ERROR "OpenAI analysis failed! See $OUTFILE"
    mv "$OUTFILE" "$FOLDER/${BASENAME}-openai-FAILED-$(date +'%Y-%m-%d_%H-%M-%S').log"
  fi
}

ai_selftest_google() {
  log INFO "[SelfTest] Running Google Artwork Analysis Self-Test"
  TEST_IMAGES=(tests/google-analysys-tests/*/test-image-*-for-analyse.jpg)
  if [[ ${#TEST_IMAGES[@]} -eq 0 ]]; then
    log WARN "No Google test images found. Skipping."
    return
  fi
  PICKED_IMAGE="${TEST_IMAGES[RANDOM % ${#TEST_IMAGES[@]}]}"
  FOLDER=$(dirname "$PICKED_IMAGE")
  BASENAME=$(basename "$PICKED_IMAGE" .jpg)
  OUTFILE="$FOLDER/${BASENAME}-google-$(date +'%Y-%m-%d_%H-%M-%S').json"

  log INFO "Testing Google analysis on: $PICKED_IMAGE"
  python3 /home/art/scripts/analyze_artwork.py "$PICKED_IMAGE" --provider google --json-output > "$OUTFILE" 2>&1

  if grep -q '"aspect_ratio"' "$OUTFILE"; then
    log SUCCESS "Google artwork analysis succeeded! Output: $OUTFILE"
  else
    log ERROR "Google analysis failed! See $OUTFILE"
    mv "$OUTFILE" "$FOLDER/${BASENAME}-google-FAILED-$(date +'%Y-%m-%d_%H-%M-%S').log"
  fi
}

ai_selftest_menu() {
  echo -e "\n--------------------------\nAI Artwork Analysis Self-Test\n--------------------------"
  echo "  [1] Test with OpenAI"
  echo "  [2] Test with Google"
  echo "  [0] Back to Main Menu"
  read -rp "Select test: " testsel
  case "$testsel" in
    1) ai_selftest_openai ;;
    2) ai_selftest_google ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
  ai_selftest_menu
}

# --------------- MENUS (PULL / PUSH etc) ---------------------------------
pull_menu() {
  echo -e "\n--------------------------\nPULL ACTIONS\n--------------------------"
  echo "  [PULL1] Full safety pull: Health/Dependency Checks, QA Report, GDrive Backup, Local Backup, Git Pull, Gunicorn/Nginx Restart"
  echo "  [PULL2] Fast pull: Just git pull (No safety checks, backups, or restarts)"
  echo "  [PULL3] (Reserved) Custom/Experimental pull (not implemented)"
  echo "  [0] Back to Main Menu"
  read -rp "Selection: " pullsel
  case "$pullsel" in
    PULL1|1) full_pull ;;
    PULL2|2) fast_git_pull ;;
    PULL3|3) echo "[RESERVED] Custom/Experimental pull not implemented yet." ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
  pull_menu
}
push_menu() {
  echo -e "\n--------------------------\nPUSH ACTIONS\n--------------------------"
  echo "  [PUSH1] Full safety push: Health/Dependency Checks, QA Report, GDrive Backup, Local Backup, Commit & Push, Gunicorn/Nginx Restart"
  echo "  [PUSH2] Quick push: Just commit & git push (No safety checks, backups, or restarts)"
  echo "  [PUSH3] (Reserved) Custom/Experimental push (not implemented)"
  echo "  [0] Back to Main Menu"
  read -rp "Selection: " pushsel
  case "$pushsel" in
    PUSH1|1) full_push ;;
    PUSH2|2) quick_git_push ;;
    PUSH3|3) echo "[RESERVED] Custom/Experimental push not implemented yet." ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
  push_menu
}
restore_backup() {
  echo -e "Not yet implemented. (You legend, remind me to add this when you want!)"
  sleep 2
}
show_backups() {
  echo -e "\nRecent backups:"
  ls -lt backups | head -20
  sleep 2
}

# --------------- MAIN ENTRY ----------------------------------------------
select_project
main_menu
