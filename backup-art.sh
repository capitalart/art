#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# The directory you want to back up.
# Using ~ targets your entire home directory (e.g., /home/art).
TARGET_DIR=~

# Where to save the final zip file and what to name it.
# Using $HOME ensures the path is correctly expanded to the user's home directory.
BACKUP_DEST="$HOME/art_backup_$(date +%Y-%m-%d).zip"

# --- Script Start ---

echo "Starting backup for: $TARGET_DIR"

# Check if the target directory exists.
if [ ! -d "$TARGET_DIR" ]; then
  echo "Error: Directory $TARGET_DIR does not exist."
  exit 1
fi

# Navigate into the target directory. The script will exit if this fails.
cd "$TARGET_DIR" || exit

echo "Finding files to archive and excluding specified patterns..."

# This script now uses 'find' to build a list of files and pipes it to 'zip'.
# This is a more robust method that avoids issues with the 'zip -x@' flag.
#
# How it works:
# find . -mindepth 1: Start finding from the contents of the current directory, skipping '.' itself.
# -path 'pattern' -prune: If a file or directory matches the pattern, don't go into it.
# -o: Means "OR".
# -print: If none of the prune conditions are met, print the file/directory path.
#
# The list of printed paths is then piped to 'zip -@', which reads the list
# from standard input.

find . -mindepth 1 \
    -path './.vscode-server' -prune -o \
    -path './.cache' -prune -o \
    -path './instance' -prune -o \
    -path './.webassets-cache' -prune -o \
    -path './venv' -prune -o \
    -path './env' -prune -o \
    -path './ENV' -prune -o \
    -path './__pycache__' -prune -o \
    -name 'art_backup_*.zip' -prune -o \
    -name '*.py[cod]' -prune -o \
    -name '*$py.class' -prune -o \
    -name '*.log' -prune -o \
    -name '*.swp' -prune -o \
    -name '*.bak' -prune -o \
    -name '*.tmp' -prune -o \
    -print | zip -r -1 "$BACKUP_DEST" -@

echo "-------------------------------------"
echo "✅ Backup complete!"
echo "Archive saved to: $BACKUP_DEST"
echo "-------------------------------------"

# Go back to the original directory you were in.
cd - > /dev/null
