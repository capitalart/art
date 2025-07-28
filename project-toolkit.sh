#!/bin/bash
# ======================================================================================
# PROJECT TOOLKIT (GEMINI ENHANCED EDITION)
# AUTHOR: Robbie & Gemini (2025-07-28)
# PURPOSE: A robust, deterministic toolkit for managing project workflows including
#          Git operations, testing, backups, and service management.
# ======================================================================================
#
# INDEX
# -----
# 1.  CONFIGURATION & INITIALISATION
# 2.  UTILITY & LOGGING FUNCTIONS
# 3.  CORE WORKFLOWS (PULL, PUSH, BACKUP)
# 4.  TESTING & QA FUNCTIONS
# 5.  MENU SYSTEM
# 6.  MAIN EXECUTION
#
# ======================================================================================

set -euo pipefail

# ======================================================================================
# SECTION 1: CONFIGURATION & INITIALISATION
# ======================================================================================

# --- [ 1.1: Project Definitions ] ---
PROJECTS=("art" "ezy" "thebigshed")
PROJECTS_PATH="/home"
DEFAULT_BRANCH="main"

# --- [ 1.2: Backup & Logging Definitions ] ---
GDRIVE_REMOTE="gdrive"
GDRIVE_BACKUP_FOLDER="project-backups"
LOG_DIR="logs"
INCLUDES_FILE="backup_includes.txt"

# --- [ 1.3: Dynamic Variable Initialisation ] ---
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/project-toolkit-$(date +'%Y-%m-%d_%H-%M-%S').log"
PROJECT=""
PROJECT_PATH=""
CODESTACK_SCRIPT=""


# ======================================================================================
# SECTION 2: UTILITY & LOGGING FUNCTIONS
# ======================================================================================

log() {
  local type="$1"; shift
  local color="\033[1;36m" # Default INFO color
  case "$type" in
    SUCCESS) color="\033[1;32m";;
    ERROR)   color="\033[1;31m";;
    WARN)    color="\033[1;33m";;
  esac
  echo -e "${color}[$type]\033[0m $*" | tee -a "$LOG_FILE"
}

die() {
  log ERROR "$*"
  echo -e "\n[ABORTED] A critical error occurred. Please check the log for details."
  exit 1
}

# ======================================================================================
# SECTION 3: CORE WORKFLOWS (PULL, PUSH, BACKUP)
# ======================================================================================

# --- [ 3.1: Full Safety Workflows ] ---
full_pull() {
  log INFO "Starting [PULL1] Full Safety Pull..."
  health_and_deps_check
  check_api_connections
  run_full_test_suite
  run_code_stack
  gdrive_backup
  local_backup
  safe_git_pull
  restart_services
  log SUCCESS "[PULL1] All steps completed successfully."
}

full_push() {
  log INFO "Starting [PUSH1] Full Safety Push..."
  health_and_deps_check
  check_api_connections
  run_full_test_suite
  run_code_stack
  gdrive_backup
  local_backup
  safe_git_push
  restart_services
  log SUCCESS "[PUSH1] All steps completed successfully."
}

# --- [ 3.2: Git Operations ] ---
safe_git_pull() {
  log INFO "Pulling latest changes from '$DEFAULT_BRANCH' branch..."
  git checkout "$DEFAULT_BRANCH"
  git pull origin "$DEFAULT_BRANCH"
  log SUCCESS "Git pull complete."
}

safe_git_push() {
  log INFO "Adding, committing, and pushing changes to '$DEFAULT_BRANCH' branch..."
  git add .
  git commit -m "Toolkit Push: $(date '+%Y-%m-%d %I:%M %p')" || log WARN "Nothing to commit."
  git push origin "$DEFAULT_BRANCH"
  log SUCCESS "Git push complete."
}

# --- [ 3.3: Backup Operations ] ---
gdrive_backup() {
  local timestamp
  timestamp=$(date "+%a-%d-%b-%Y-%I-%M-%p")
  mkdir -p backups
  local backup_zip="backups/backup_${timestamp}.zip"
  
  log INFO "Creating ZIP backup for Google Drive: $backup_zip"
  if [[ ! -f "$INCLUDES_FILE" ]]; then die "Backup includes file ($INCLUDES_FILE) not found!"; fi
  zip -r -q "$backup_zip" -@ < "$INCLUDES_FILE"
  
  log INFO "Uploading backup to Google Drive..."
  if rclone copy "$backup_zip" "$GDRIVE_REMOTE:$GDRIVE_BACKUP_FOLDER" --progress; then
    log SUCCESS "Google Drive backup uploaded successfully."
  else
    log ERROR "Google Drive upload failed."
  fi
}

local_backup() {
  local timestamp
  timestamp=$(date "+%a-%d-%b-%Y-%I-%M-%p")
  mkdir -p backups
  local backup_tar="backups/backup_${timestamp}.tar.gz"
  
  log INFO "Creating local tar.gz backup: $backup_tar"
  if [[ ! -f "$INCLUDES_FILE" ]]; then die "Backup includes file ($INCLUDES_FILE) not found!"; fi
  tar czf "$backup_tar" -T "$INCLUDES_FILE"
  
  log SUCCESS "Local backup created successfully."
}

# ======================================================================================
# SECTION 4: TESTING & QA FUNCTIONS
# ======================================================================================

# --- [ 4.1: Full Test Suite (pytest) ] ---
run_full_test_suite() {
  log INFO "Running full project test suite (pytest)..."
  if [[ ! -d "tests" ]]; then
    log WARN "No 'tests' directory found. Skipping full test suite."
    return
  fi
  if [[ ! -d venv ]]; then die "Python venv not found!"; fi
  source venv/bin/activate || die "Could not activate venv!"
  
  log INFO "Executing command: python3 -m pytest tests/"
  if python3 -m pytest tests/; then
    log SUCCESS "All tests passed successfully!"
  else
    die "One or more tests failed. Please review the output above."
  fi
}

# --- [ 4.2: Health and Dependency Checks ] ---
health_and_deps_check() {
  log INFO "Running Health & Dependency Checks..."
  [[ -d venv ]] || die "Python venv not found!"
  source venv/bin/activate || die "Could not activate venv!"
  pip check || die "pip check reported broken requirements!"
  python3 -c "import openai" || die "OpenAI Python library not installed."
  python3 -c "import pytest" || die "Pytest library not installed."
  [[ -f .env ]] || die ".env file is missing!"
  if ! curl -fs http://localhost:7777/healthz >/dev/null 2>&1; then
    die "/healthz endpoint is not responding! Is the Flask app running?"
  else
    log SUCCESS "Local route /healthz check OK."
  fi
}

# --- [ 4.3: API Connection Tests ] ---
run_connection_tests() {
  log INFO "Running API Connection Test Script..."
  local test_script="$PROJECT_PATH/scripts/test_connections.py"
  if [[ ! -f "$test_script" ]]; then
    log WARN "Connection test script ($test_script) not found. Skipping."
    return
  fi

  [[ -d venv ]] || die "Python venv not found!"
  source venv/bin/activate || die "Could not activate venv!"
  python3 "$test_script"
  log SUCCESS "Connection test script finished."
}

check_api_connections() {
  log INFO "Verifying external API connections..."
  local test_script="$PROJECT_PATH/scripts/test_connections.py"
  if [[ ! -f "$test_script" ]]; then
    log WARN "Connection test script ($test_script) not found. Skipping check."
    return
  fi
  [[ -d venv ]] || die "Python venv not found!"
  source venv/bin/activate || die "Could not activate venv!"
  
  local test_output
  test_output=$(python3 "$test_script")
  echo -e "$test_output" | tee -a "$LOG_FILE"

  if echo "$test_output" | grep -q "❌"; then
    die "One or more API connection tests failed. Check credentials in .env file."
  else
    log SUCCESS "All API connections are OK."
  fi
}

# --- [ 4.4: AI Self-Tests ] ---
ai_selftest_openai() {
  log INFO "[SelfTest] Running OpenAI Artwork Analysis Self-Test"
  local test_images_path="$PROJECT_PATH/tests/opneai-analysys-tests"
  local analyze_script="$PROJECT_PATH/scripts/analyze_artwork.py"
  
  local test_images=("$test_images_path"/*/test-image-*-for-analyse.jpg)
  if [[ ! -f "${test_images[0]}" ]]; then
    log WARN "No OpenAI test images found in '$test_images_path'. Skipping."
    return
  fi
  
  local picked_image="${test_images[RANDOM % ${#test_images[@]}]}"
  local folder
  folder=$(dirname "$picked_image")
  local basename
  basename=$(basename "$picked_image" .jpg)
  local outfile="$folder/${basename}-openai-$(date +'%Y-%m-%d_%H-%M-%S').json"

  log INFO "Testing OpenAI analysis on: $picked_image"
  python3 "$analyze_script" "$picked_image" --provider openai --json-output > "$outfile" 2>&1

  if grep -q '"aspect_ratio"' "$outfile"; then
    log SUCCESS "OpenAI artwork analysis succeeded! Output: $outfile"
  else
    log ERROR "OpenAI analysis failed! See log for details: $outfile"
  fi
}

ai_selftest_google() {
  log INFO "[SelfTest] Running Google Artwork Analysis Self-Test"
  local test_images_path="$PROJECT_PATH/tests/google-analysys-tests"
  local analyze_script="$PROJECT_PATH/scripts/analyze_artwork_google.py"
  
  local test_images=("$test_images_path"/*/test-image-*-for-analyse.jpg)
  if [[ ! -f "${test_images[0]}" ]]; then
    log WARN "No Google test images found in '$test_images_path'. Skipping."
    return
  fi
  
  local picked_image="${test_images[RANDOM % ${#test_images[@]}]}"
  local folder
  folder=$(dirname "$picked_image")
  local basename
  basename=$(basename "$picked_image" .jpg)
  local outfile="$folder/${basename}-google-$(date +'%Y-%m-%d_%H-%M-%S').json"

  log INFO "Testing Google analysis on: $picked_image"
  python3 "$analyze_script" "$picked_image" > "$outfile" 2>&1

  if grep -q '"was_json": true' "$outfile"; then
    log SUCCESS "Google artwork analysis succeeded! Output: $outfile"
  else
    log ERROR "Google analysis failed! See log for details: $outfile"
  fi
}

# ======================================================================================
# SECTION 5: MENU SYSTEM
# ======================================================================================

# --- [ 5.1: Project Selector ] ---
select_project() {
  echo -e "\n========================\n      PROJECTS\n========================"
  select project_choice in "${PROJECTS[@]}" "Exit"; do
    if [[ "$project_choice" == "Exit" ]]; then exit 0; fi
    if [[ " ${PROJECTS[*]} " =~ " ${project_choice} " ]]; then
      PROJECT="$project_choice"
      PROJECT_PATH="$PROJECTS_PATH/$PROJECT"
      cd "$PROJECT_PATH" || die "Could not change directory to $PROJECT_PATH"
      CODESTACK_SCRIPT="$PROJECT_PATH/code-stacker.sh"
      log INFO "Working directory set to: $PROJECT_PATH"
      return 0
    fi
    echo "Invalid selection."
  done
}

# --- [ 5.2: Main Menu ] ---
main_menu() {
  while true; do
    echo -e "\n========================\n      MAIN MENU\n========================"
    echo "  [1] PULL Actions (Get updates from remote)"
    echo "  [2] PUSH Actions (Send updates to remote)"
    echo "  [3] System Actions (Checks, backups, restarts)"
    echo "  [4] Testing & QA"
    echo "  [5] Backup Management"
    echo "  [0] Exit"
    read -rp "Select an option: " main_menu_selection
    case "$main_menu_selection" in
      1) pull_menu ;;
      2) push_menu ;;
      3) sys_menu ;;
      4) test_menu ;;
      5) backup_menu ;;
      0) exit 0 ;;
      *) echo "Invalid selection." ;;
    esac
  done
}

# --- [ 5.3: Sub-Menus ] ---
pull_menu() {
  echo -e "\n--------------------------\nPULL ACTIONS\n--------------------------"
  echo "  [1] PULL1: Full Safety Pull (Recommended)"
  echo "  [2] PULL2: Fast Pull (Git pull only)"
  echo "  [0] Back to Main Menu"
  read -rp "Selection: " pullsel
  case "$pullsel" in
    1) full_pull ;;
    2) safe_git_pull ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
}

push_menu() {
  echo -e "\n--------------------------\nPUSH ACTIONS\n--------------------------"
  echo "  [1] PUSH1: Full Safety Push (Recommended)"
  echo "  [2] PUSH2: Quick Push (Git add, commit, push only)"
  echo "  [0] Back to Main Menu"
  read -rp "Selection: " pushsel
  case "$pushsel" in
    1) full_push ;;
    2) safe_git_push ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
}

sys_menu() {
  echo -e "\n--------------------------\nSYSTEM ACTIONS\n--------------------------"
  echo "  [1] Run Full System Health Check"
  echo "  [2] Restart Services (gunicorn/nginx)"
  echo "  [0] Back to Main Menu"
  read -rp "Selection: " syssel
  case "$syssel" in
    1) health_and_deps_check ;;
    2) restart_services ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
}

test_menu() {
  echo -e "\n--------------------------\nTESTING & QA\n--------------------------"
  echo "  [1] Run Full Test Suite (pytest)"
  echo "  [2] Test API Connections"
  echo "  [3] Run AI Self-Test (OpenAI)"
  echo "  [4] Run AI Self-Test (Google)"
  echo "  [5] Generate Code Stack Report"
  echo "  [0] Back to Main Menu"
  read -rp "Selection: " testsel
  case "$testsel" in
    1) run_full_test_suite ;;
    2) run_connection_tests ;;
    3) ai_selftest_openai ;;
    4) ai_selftest_google ;;
    5) run_code_stack ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
}

backup_menu() {
    echo -e "\n--------------------------\nBACKUP MANAGEMENT\n--------------------------"
    echo "  [1] Create Local Backup"
    echo "  [2] Create Google Drive Backup"
    echo "  [3] Show Recent Local Backups"
    echo "  [4] DRY RUN: See what files will be in the backup"
    echo "  [0] Back to Main Menu"
    read -rp "Selection: " backupsel
    case "$backupsel" in
        1) local_backup ;;
        2) gdrive_backup ;;
        3) echo -e "\nRecent backups:"; ls -lt backups | head -10 ;;
        4) backup_dryrun_menu ;;
        0) return ;;
        *) echo "Invalid selection." ;;
    esac
}

backup_dryrun_menu() {
  echo -e "\n--- DRY RUN: Files in Backup ---"
  if [[ ! -f "$INCLUDES_FILE" ]]; then
      log WARN "Includes file ($INCLUDES_FILE) not found."
      return
  fi
  echo "The following top-level files/folders are configured for backup:"
  cat "$INCLUDES_FILE"
  echo "------------------------------------"
}

# --- [ 5.4: Utility Functions (Legacy, kept for reference) ] ---
run_code_stack() {
  log INFO "Generating code stack / QA report..."
  if [[ -x "$CODESTACK_SCRIPT" ]]; then
    bash "$CODESTACK_SCRIPT"
    log SUCCESS "Code stack generated."
  else
    log WARN "$CODESTACK_SCRIPT not found/skipped."
  fi
}

restart_services() {
  log INFO "Restarting gunicorn/nginx (if running)..."
  sudo systemctl restart gunicorn || log WARN "Gunicorn restart failed. (Might not be running)."
  sudo systemctl restart nginx || log WARN "Nginx restart failed. (Might not be running)."
  log SUCCESS "Service restart command issued."
}

# ======================================================================================
# SECTION 6: MAIN EXECUTION
# ======================================================================================
log INFO "Project Toolkit Initialised"
select_project
main_menu