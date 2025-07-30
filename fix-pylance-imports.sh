#!/bin/bash

# ======================================================================================
# SCRIPT: fix-pylance-imports.sh
# PURPOSE: Resolve "missing imports" errors in VSCode + Pylance for relative modules
# CREATED: WED 30 JULY 2025 — Robbie Mode™
# ======================================================================================

set -e

# ----------------------------------------
# 1. Define all directories that need __init__.py
# ----------------------------------------
MODULE_DIRS=(
  "./"
  "./routes"
  "./services"
  "./utils"
  "./models"
  "./database"
)

echo "🔧 Creating __init__.py files..."
for DIR in "${MODULE_DIRS[@]}"; do
  if [ ! -d "$DIR" ]; then
    echo "📁 Creating missing directory: $DIR"
    mkdir -p "$DIR"
  fi

  TARGET="${DIR}/__init__.py"
  if [ ! -f "$TARGET" ]; then
    touch "$TARGET"
    echo "✅ Created: $TARGET"
  else
    echo "☑️ Already exists: $TARGET"
  fi
done

# ----------------------------------------
# 2. Patch .vscode/settings.json if needed
# ----------------------------------------
VSCODE_SETTINGS=".vscode/settings.json"
EXTRA_PATHS="\"python.analysis.extraPaths\": [\"./\", \"./routes\", \"./services\", \"./utils\", \"./models\", \"./database\"]"

mkdir -p .vscode

if [ ! -f "$VSCODE_SETTINGS" ]; then
  echo "🆕 Creating new $VSCODE_SETTINGS..."
  echo "{ $EXTRA_PATHS }" > "$VSCODE_SETTINGS"
  echo "✅ settings.json created with extraPaths"
else
  if grep -q "python.analysis.extraPaths" "$VSCODE_SETTINGS"; then
    echo "☑️ settings.json already contains python.analysis.extraPaths — skipping patch."
  else
    echo "🛠 Patching existing settings.json to add python.analysis.extraPaths..."
    TMP_FILE=$(mktemp)

    # Insert before the last closing brace
    sed "\$ s/}/,\n  $EXTRA_PATHS\n}/" "$VSCODE_SETTINGS" > "$TMP_FILE"
    mv "$TMP_FILE" "$VSCODE_SETTINGS"
    echo "✅ Patched: $VSCODE_SETTINGS"
  fi
fi

echo -e "\n🎉 All done! VSCode + Pylance should now resolve imports cleanly."
