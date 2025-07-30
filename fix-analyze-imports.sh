#!/bin/bash

echo "🔧 [Step 1] Creating required folders and __init__.py files..."

MODULES=(
  "."
  "./routes"
  "./services"
  "./models"
  "./database"
  "./utils"
  "./dependencies"
)

for MODULE in "${MODULES[@]}"; do
  if [ ! -d "$MODULE" ]; then
    echo "📁 Creating missing directory: $MODULE"
    mkdir -p "$MODULE"
  fi

  INIT_FILE="$MODULE/__init__.py"
  if [ ! -f "$INIT_FILE" ]; then
    touch "$INIT_FILE"
    echo "✅ Created: $INIT_FILE"
  else
    echo "☑️ Already exists: $INIT_FILE"
  fi
done

echo ""
echo "🔧 [Step 2] Ensuring VSCode settings.json is correctly patched..."

VSCODE_DIR=".vscode"
SETTINGS_FILE="$VSCODE_DIR/settings.json"
EXTRA_PATHS=$(cat <<EOF
{
  "python.analysis.extraPaths": [
    "./",
    "./routes",
    "./services",
    "./models",
    "./database",
    "./utils",
    "./dependencies"
  ]
}
EOF
)

if [ ! -d "$VSCODE_DIR" ]; then
  echo "📁 Creating .vscode directory..."
  mkdir "$VSCODE_DIR"
fi

if [ ! -f "$SETTINGS_FILE" ]; then
  echo "🆕 Creating new settings.json with extraPaths..."
  echo "$EXTRA_PATHS" > "$SETTINGS_FILE"
else
  echo "⚙️ Updating settings.json (preserving existing settings)..."

  python3 - <<EOF
import json, os
settings_path = "$SETTINGS_FILE"
extra_paths = [
    "./", "./routes", "./services", "./models",
    "./database", "./utils", "./dependencies"
]

if os.path.exists(settings_path):
    with open(settings_path) as f:
        data = json.load(f)
else:
    data = {}

paths = set(data.get("python.analysis.extraPaths", []))
paths.update(extra_paths)
data["python.analysis.extraPaths"] = sorted(paths)

with open(settings_path, "w") as f:
    json.dump(data, f, indent=2)
EOF

  echo "✅ Patched: $SETTINGS_FILE"
fi

echo ""
echo "🎉 All done! VSCode and Pylance should now resolve all analyze_routes.py imports."
