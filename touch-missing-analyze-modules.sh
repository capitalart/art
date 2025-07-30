#!/bin/bash

echo "🔍 Checking and creating any missing Python module files..."

declare -a FILES=(
  "./utils/template_engine.py"
  "./services/artwork_analysis_service.py"
  "./utils/content_blocks.py"
  "./utils/file_utils.py"
  "./utils/template_helpers.py"
  "./utils/ai_utils.py"
  "./utils/image_processing_utils.py"
)

for FILE in "${FILES[@]}"; do
  if [ ! -f "$FILE" ]; then
    touch "$FILE"
    echo "# 🔧 Stub created for: $FILE" > "$FILE"
    echo "✅ Created: $FILE"
  else
    echo "☑️ Already exists: $FILE"
  fi
done

echo ""
echo "🎯 All module files accounted for. Pylance should now be fully happy with analyze_routes.py!"
