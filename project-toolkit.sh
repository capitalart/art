#!/bin/bash
# ======================================================================================
# PROJECT TOOLKIT (GEMINI ENHANCED EDITION)
# AUTHOR: Robbie & Gemini (2025-07-30)
# PURPOSE: A robust, deterministic toolkit for managing project workflows including
#          Git operations, testing, backups, log analysis, and service management.
# ======================================================================================

set -euo pipefail

# ======================================================================================
# SECTION 1: CONFIGURATION & INITIALISATION
# ======================================================================================

PROJECTS_PATH="/home"
DEFAULT_BRANCH="main"

GDRIVE_REMOTE="gdrive"
GDRIVE_BACKUP_FOLDER="project-backups"
LOG_DIR="logs"
INCLUDES_FILE="backup_includes.txt"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/project-toolkit-$(date +'%Y-%m-%d_%H-%M-%S').log"
CODESTACK_SCRIPT="code-stacker.sh"

# ======================================================================================
# SECTION 2: UTILITY & LOGGING FUNCTIONS
# ======================================================================================

log() {
  local type="$1"; shift
  local color="\033[1;36m"
  case "$type" in
    SUCCESS) color="\033[1;32m";;
    ERROR)   color="\033[1;31m";;
    WARN)    color="\033[1;33m";;
  esac
  echo -e "${color}[$type]\033[0m $*" | tee -a "$LOG_FILE"
}

die() {
  log ERROR "$*"
  echo -e "\n[ABORTED] A critical error occurred. Please check the log: $LOG_FILE"
  exit 1
}

# ======================================================================================
# SECTION 3: CORE WORKFLOWS
# ======================================================================================

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
  log SUCCESS "[PULL1] Complete."
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
  log SUCCESS "[PUSH1] Complete."
}

safe_git_pull() {
  log INFO "Pulling latest changes from '$DEFAULT_BRANCH'..."
  git checkout "$DEFAULT_BRANCH"
  git pull origin "$DEFAULT_BRANCH" --rebase --autostash
  log SUCCESS "Git pull complete."
}

safe_git_push() {
  log INFO "Committing and pushing changes to '$DEFAULT_BRANCH'..."
  git add .
  git commit -m "Toolkit Push: $(date '+%Y-%m-%d %I:%M %p')" || log WARN "Nothing to commit."
  git push origin "$DEFAULT_BRANCH"
  log SUCCESS "Git push complete."
}

gdrive_backup() {
  local timestamp
  timestamp=$(date "+%a-%d-%b-%Y-%I-%M-%p")
  local backup_zip="backups/backup_${timestamp}.zip"
  mkdir -p backups
  log INFO "Creating ZIP backup: $backup_zip"
  [[ -f "$INCLUDES_FILE" ]] || die "Missing includes file: $INCLUDES_FILE"
  zip -r -q "$backup_zip" -@ < "$INCLUDES_FILE"
  rclone copy "$backup_zip" "$GDRIVE_REMOTE:$GDRIVE_BACKUP_FOLDER" --progress || log ERROR "Google Drive upload failed."
  log SUCCESS "Backup uploaded to Google Drive."
}

local_backup() {
  local timestamp
  timestamp=$(date "+%a-%d-%b-%Y-%I-%M-%p")
  local backup_tar="backups/backup_${timestamp}.tar.gz"
  mkdir -p backups
  log INFO "Creating local backup: $backup_tar"
  [[ -f "$INCLUDES_FILE" ]] || die "Missing includes file: $INCLUDES_FILE"
  tar czf "$backup_tar" -T "$INCLUDES_FILE"
  log SUCCESS "Local backup created."
}

# ======================================================================================
# SECTION 4: TESTING, HEALTH & QA
# ======================================================================================

run_full_test_suite() {
  log INFO "Running full test suite..."
  [[ -d tests ]] || { log WARN "No 'tests' directory. Skipping tests."; return; }
  [[ -d venv ]] || die "Python venv not found!"
  source venv/bin/activate || die "Failed to activate venv!"
  python3 -m pytest tests/ || die "One or more tests failed."
  log SUCCESS "All tests passed."
}

health_and_deps_check() {
  log INFO "Running Health Check..."
  [[ -d venv ]] || die "Python venv not found!"
  source venv/bin/activate || die "Venv activation failed!"
  pip check || die "Dependency check failed!"
  [[ -f .env ]] || die "Missing .env file!"
  curl -fs http://localhost:7777/healthz >/dev/null || die "/healthz not responding!"
  log SUCCESS "All system checks passed."
}

check_api_connections() {
  log INFO "Verifying API connectivity..."
  local test_script="scripts/test_connections.py"
  [[ -f "$test_script" ]] || { log WARN "API test script missing."; return; }
  [[ -d venv ]] || die "Python venv not found!"
  source venv/bin/activate || die "Venv activation failed!"
  python3 "$test_script" | tee -a "$LOG_FILE"
}

# ======================================================================================
# SECTION 5: CHATBOT SNAPSHOT EXPORT
# ======================================================================================

gather_recent_logs() {
  local since_minutes=60
  local now_label
  now_label=$(date "+%a-%d-%B-%Y-%I-%M-%p" | tr '[:lower:]' '[:upper:]')
  local snapshot_dir="code-stacks/log-snapshots"
  local output_file="${snapshot_dir}/log-stack-${now_label}.md"

  mkdir -p "$snapshot_dir"
  echo "# 📦 LOG SNAPSHOT (Last ${since_minutes} Minutes)" > "$output_file"

  find "$LOG_DIR" -type f \( -name "*.log" -o -name "*.txt" \) | sort | while read -r log_file; do
    echo -e "\n\n---\n## $(basename "$log_file")\n---" >> "$output_file"
    echo "**Path:** \`$log_file\`" >> "$output_file"
    echo "**Updated:** \`$(date -r "$log_file" "+%Y-%m-%d %H:%M:%S")\`" >> "$output_file"
    echo >> "$output_file"

    grep -E "$(date --date="-${since_minutes} minutes" "+%Y-%m-%d %H:[0-9]{2}:[0-9]{2}")" "$log_file" >> "$output_file" 2>/dev/null || {
      echo "_(No entries in last ${since_minutes} minutes – showing last 30 lines)_" >> "$output_file"
      tail -n 30 "$log_file" >> "$output_file"
    }
  done

  log SUCCESS "Generated log snapshot: $output_file"
}

# ======================================================================================
# SECTION 6: MENU SYSTEM
# ======================================================================================

main_menu() {
  while true; do
    echo -e "\n========================\n      MAIN MENU\n========================"
    echo "  [1] PULL Actions"
    echo "  [2] PUSH Actions"
    echo "  [3] System Actions"
    echo "  [4] Testing & QA"
    echo "  [5] Backup Management"
    echo "  [6] Cleanup Actions"
    echo "  [7] Export Logs Snapshot for Chatbot (Last 60min)"
    echo "  [0] Exit"
    read -rp "Select an option: " main_menu_selection
    case "$main_menu_selection" in
      1) full_pull ;;
      2) full_push ;;
      3) restart_services ;;
      4) run_full_test_suite ;;
      5) backup_menu ;;
      6) cleanup_menu ;;
      7) gather_recent_logs ;;
      0) exit 0 ;;
      *) echo "Invalid selection." ;;
    esac
  done
}

backup_menu() {
  echo -e "\n--------------------------\nBACKUP MENU\n--------------------------"
  echo "  [1] Create Local Backup"
  echo "  [2] Create Google Drive Backup"
  echo "  [3] Show Recent Local Backups"
  echo "  [0] Back to Main Menu"
  read -rp "Select: " sel
  case "$sel" in
    1) local_backup ;;
    2) gdrive_backup ;;
    3) ls -lt backups | head -10 ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
}

cleanup_menu() {
  echo -e "\n--------------------------\nCLEANUP MENU\n--------------------------"
  echo "  [1] Delete all *.md code stack reports"
  echo "  [2] Delete all *.log toolkit logs"
  echo "  [0] Back to Main Menu"
  read -rp "Select: " sel
  case "$sel" in
    1) rm -f code-stack-*.md && log SUCCESS "Deleted *.md reports." ;;
    2) rm -f "$LOG_DIR"/*.log && log SUCCESS "Deleted toolkit logs." ;;
    0) return ;;
    *) echo "Invalid selection." ;;
  esac
}

restart_services() {
  log INFO "Restarting services..."
  sudo systemctl restart gunicorn || log WARN "Gunicorn may not be running."
  sudo systemctl restart nginx || log WARN "Nginx may not be running."
  log SUCCESS "Restart command issued."
}

run_code_stack() {
  log INFO "Generating code stack..."
  [[ -x "$CODESTACK_SCRIPT" ]] && bash "$CODESTACK_SCRIPT" || log WARN "Script not found or not executable: $CODESTACK_SCRIPT"
}

# ======================================================================================
# SECTION 7: MAIN EXECUTION
# ======================================================================================

log INFO "Project Toolkit Initialised – Launching Main Menu..."
main_menu
