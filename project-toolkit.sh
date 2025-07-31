#!/bin/bash
# ======================================================================================
# PROJECT TOOLKIT (ROBBIE MODE™ - Codex-Ready Edition)
# AUTHOR: Robin Custance & Codex Assistant (2025-07-30)
# PURPOSE: Manage Git workflows, testing, auditing, backups, log snapshots, and services
# ======================================================================================

set -euo pipefail

# --- Force .env to load for ALL subprocesses ---
set -a
[ -f .env ] && source .env
set +a

# ======================================================================================
# SECTION 1: CONFIGURATION
# ======================================================================================
PROJECTS_PATH="/home"
DEFAULT_BRANCH="main"
GDRIVE_REMOTE="gdrive"
GDRIVE_BACKUP_FOLDER="project-backups"
LOG_DIR="logs"
INCLUDES_FILE="backup_includes.txt"
CODESTACK_SCRIPT="code-stacker.sh"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/project-toolkit-$(date +'%Y-%m-%d_%H-%M-%S').log"

# ======================================================================================
# SECTION 2: LOGGING FUNCTIONS
# ======================================================================================
log() {
  local level="$1"
  shift
  local color="\033[1;36m"
  case "$level" in
    SUCCESS) color="\033[1;32m" ;;
    ERROR)   color="\033[1;31m" ;;
    WARN)    color="\033[1;33m" ;;
  esac
  echo -e "${color}[$level]\033[0m $*" | tee -a "$LOG_FILE"
}

die() {
  log ERROR "$*"
  echo -e "\n[ABORTED] Critical error occurred. See log: $LOG_FILE"
  exit 1
}

# ======================================================================================
# SECTION 3: CORE WORKFLOWS
# ======================================================================================
full_pull() {
  log INFO "Running [PULL] workflow..."
  health_and_deps_check
  check_api_connections
  run_full_test_suite
  run_code_stack
  gdrive_backup
  local_backup
  safe_git_pull
  restart_services
  log SUCCESS "[PULL] Complete."
}

full_push() {
  log INFO "Running [PUSH] workflow..."
  health_and_deps_check
  check_api_connections
  run_full_test_suite
  run_code_stack
  gdrive_backup
  local_backup
  safe_git_push
  restart_services
  log SUCCESS "[PUSH] Complete."
}

safe_git_pull() {
  log INFO "Pulling latest from $DEFAULT_BRANCH..."
  git checkout "$DEFAULT_BRANCH"
  git pull origin "$DEFAULT_BRANCH" --rebase --autostash
  log SUCCESS "Git pull successful."
}

safe_git_push() {
  log INFO "Committing and pushing to $DEFAULT_BRANCH..."
  git add .
  git commit -m "Toolkit push on $(date '+%Y-%m-%d %I:%M %p')" || log WARN "Nothing to commit."
  git push origin "$DEFAULT_BRANCH"
  log SUCCESS "Git push successful."
}

# ======================================================================================
# SECTION 4: BACKUPS
# ======================================================================================
gdrive_backup() {
  local timestamp
  timestamp=$(date "+%a-%d-%b-%Y-%I-%M-%p")
  local zipfile="backups/backup_${timestamp}.zip"
  mkdir -p backups
  [[ -f "$INCLUDES_FILE" ]] || die "Missing includes file: $INCLUDES_FILE"
  zip -r -q "$zipfile" -@ < "$INCLUDES_FILE"
  rclone copy "$zipfile" "$GDRIVE_REMOTE:$GDRIVE_BACKUP_FOLDER" --progress || log ERROR "Google Drive upload failed."
  log SUCCESS "Uploaded backup to Google Drive: $zipfile"
}

local_backup() {
  local timestamp
  timestamp=$(date "+%a-%d-%b-%Y-%I-%M-%p")
  local tarball="backups/backup_${timestamp}.tar.gz"
  mkdir -p backups
  [[ -f "$INCLUDES_FILE" ]] || die "Missing includes file: $INCLUDES_FILE"
  tar czf "$tarball" -T "$INCLUDES_FILE"
  log SUCCESS "Local backup created: $tarball"
}

# ======================================================================================
# SECTION 5: TESTING & QA
# ======================================================================================
health_and_deps_check() {
  log INFO "Running health check..."
  [[ -d venv ]] || die "Python venv not found"
  source venv/bin/activate || die "Venv activation failed"
  pip check || die "Dependency check failed"
  [[ -f .env ]] || die "Missing .env file"
  curl -fs http://localhost:7777/healthz > /dev/null || die "/healthz not responding"
  log SUCCESS "All system checks passed."
}

check_api_connections() {
  log INFO "Verifying API connectivity..."
  local test_script="scripts/test_connections.py"
  [[ -f "$test_script" ]] || { log WARN "API test script not found."; return; }
  source venv/bin/activate
  python3 "$test_script" | tee -a "$LOG_FILE"
}

run_full_test_suite() {
  log INFO "Running test suite..."
  [[ -d tests ]] || { log WARN "No 'tests' directory found. Skipping tests."; return; }
  source venv/bin/activate
  export PYTHONPATH="/home/art"
  python3 -m pytest tests/ || die "Tests failed"
  log SUCCESS "All tests passed."
  cleanup_test_folders
}

# ======================================================================================
# SECTION 6: CLEANUP
# ======================================================================================
cleanup_test_folders() {
  local TEST_UNANALYSED="art-processing/unanalysed-artwork"
  local TEST_PROCESSED="art-processing/processed-artwork"
  log INFO "Cleaning up test folders..."
  find "$TEST_UNANALYSED" -type d -name "test-*" -exec rm -rf {} + || true
  find "$TEST_UNANALYSED" -type f -name "*.qc.json" -delete || true
  rm -rf "$TEST_PROCESSED/first-artwork" "$TEST_PROCESSED/second-artwork" || true
  log SUCCESS "Test artefacts cleaned."
}

# ======================================================================================
# SECTION 7: SNAPSHOT LOGGING
# ======================================================================================
gather_recent_logs() {
  local snapshot_dir="code-stacks/log-snapshots"
  local now=$(date "+%a-%d-%B-%Y-%I-%M-%p" | tr '[:lower:]' '[:upper:]')
  local outfile="${snapshot_dir}/log-stack-${now}.md"
  mkdir -p "$snapshot_dir"
  echo "# 📦 LOG SNAPSHOT (Last 60 Minutes)" > "$outfile"
  find "$LOG_DIR" -type f \( -name "*.log" -o -name "*.txt" \) | while read -r file; do
    echo -e "\n\n---\n## $(basename "$file")\n---" >> "$outfile"
    echo "**Path:** \`$file\`" >> "$outfile"
    echo "**Updated:** \`$(date -r "$file" "+%Y-%m-%d %H:%M:%S")\`" >> "$outfile"
    grep "$(date --date='-60 min' "+%Y-%m-%d %H")" "$file" >> "$outfile" || tail -n 30 "$file" >> "$outfile"
  done
  log SUCCESS "Log snapshot saved: $outfile"
}

# ======================================================================================
# SECTION 8: SERVICE CONTROL
# ======================================================================================
restart_services() {
  log INFO "Restarting services..."
  sudo systemctl restart gunicorn || log WARN "Gunicorn restart failed"
  sudo systemctl restart nginx || log WARN "Nginx restart failed"
  log SUCCESS "Services restarted."
}

run_code_stack() {
  [[ -x "$CODESTACK_SCRIPT" ]] && bash "$CODESTACK_SCRIPT" || log WARN "No executable code stacker script found"
}

# ======================================================================================
# SECTION 9: AUDIT TOOLS (Codex)
# ======================================================================================
run_file_import_scanner() {
  log INFO "Running File & Import Scanner..."
  python3 tools/audit/file_import_scanner.py --include-tests --save-json || log ERROR "Scanner failed"
  log SUCCESS "Import scan complete"
}

run_reverse_dependency_map() {
  log INFO "Running Reverse Dependency Mapper..."
  python3 tools/audit/reverse_dependency_map.py --include-tests --dead-code --save-json || log ERROR "Reverse mapper failed"
  log SUCCESS "Dependency map complete"
}

run_codex_audit_runner() {
  log INFO "Running Codex System Summary..."
  python3 tools/audit/system_codex_audit_runner.py --summarise-risks || log ERROR "Codex audit failed"
  log SUCCESS "Codex audit complete"
}

run_path_link_validator() {
  log INFO "Running Path & Link Validator..."
  python3 tools/audit/path_link_validator.py || log ERROR "Path/link validator failed"
  log SUCCESS "Path & Link validation complete"
}

codex_audit_menu() {
  echo -e "\n--------------------------\nCODEX AUDIT MENU\n--------------------------"
  echo "  [1] Run File & Import Scanner"
  echo "  [2] Run Reverse Dependency Mapper"
  echo "  [3] Run Codex System Summary"
  echo "  [4] Run All Four Audits"
  echo "  [5] Run Path & Link Validator"
  echo "  [0] Back to Main Menu"
  read -rp "Select: " sel
  case "$sel" in
    1) run_file_import_scanner ;;
    2) run_reverse_dependency_map ;;
    3) run_codex_audit_runner ;;
    4)
      run_file_import_scanner
      run_reverse_dependency_map
      run_codex_audit_runner
      run_path_link_validator
      ;;
    5) run_path_link_validator ;;
    0) return ;;
    *) echo "Invalid option." ;;
  esac
}

# ======================================================================================
# SECTION 10: MENU SYSTEM
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
    echo "  [8] Audit Tools"
    echo "  [0] Exit"
    read -rp "Select an option: " main_sel
    case "$main_sel" in
      1) full_pull ;;
      2) full_push ;;
      3) restart_services ;;
      4) run_full_test_suite ;;
      5) backup_menu ;;
      6) cleanup_menu ;;
      7) gather_recent_logs ;;
      8) codex_audit_menu ;;
      0) exit 0 ;;
      *) echo "Invalid option" ;;
    esac
  done
}

backup_menu() {
  echo -e "\n------ BACKUP MENU ------"
  echo "  [1] Local Backup"
  echo "  [2] Google Drive Backup"
  echo "  [3] Show Recent Local Backups"
  echo "  [0] Back"
  read -rp "Select: " sel
  case "$sel" in
    1) local_backup ;;
    2) gdrive_backup ;;
    3) ls -lt backups | head -10 ;;
    0) return ;;
    *) echo "Invalid option." ;;
  esac
}

cleanup_menu() {
  echo -e "\n------ CLEANUP MENU ------"
  echo "  [1] Delete .md reports"
  echo "  [2] Delete .log files"
  echo "  [3] Cleanup test folders"
  echo "  [0] Back"
  read -rp "Select: " sel
  case "$sel" in
    1) rm -f code-stack-*.md && log SUCCESS "Deleted .md files" ;;
    2) rm -f "$LOG_DIR"/*.log && log SUCCESS "Deleted .log files" ;;
    3) cleanup_test_folders ;;
    0) return ;;
    *) echo "Invalid option." ;;
  esac
}

# ======================================================================================
# ENTRYPOINT
# ======================================================================================
log INFO "Project Toolkit Initialised – Launching Main Menu..."
main_menu
