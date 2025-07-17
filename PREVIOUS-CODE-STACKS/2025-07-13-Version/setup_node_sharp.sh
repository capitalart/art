#!/usr/bin/env bash

# ================================================================
# setup_node_sharp.sh - Idempotent Node.js + Sharp setup script
# Works on macOS and Ubuntu/Debian-based systems.
# - Installs nvm (if missing) via the official install script.
# - Installs the latest LTS Node.js version if node/npm not found.
# - Initializes an npm project if package.json is absent.
# - Installs the Sharp image library.
# - Creates resize.js for quick image resizing tests.
# - Prints usage instructions and tips at the end.
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- 1. Install nvm if needed -----------------------------------
NVM_DIR="$HOME/.nvm"
# If nvm is already installed, load it so `nvm` command becomes available
if [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh"
fi

if ! command -v nvm >/dev/null 2>&1; then
  echo "[INFO] nvm not found. Installing..."
  # Recommended install method from nvm-sh
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  # Load nvm for the current shell session
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
else
  echo "[INFO] nvm already installed."
fi

# --- 2. Install Node.js LTS if needed ---------------------------
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  echo "[INFO] Node.js and npm already installed."
else
  echo "[INFO] Installing latest LTS Node.js via nvm..."
  nvm install --lts
  nvm use --lts
fi

# --- 3. Initialise npm project ----------------------------------
if [ ! -f package.json ]; then
  echo "[INFO] Initialising npm project..."
  npm init -y
else
  echo "[INFO] package.json already exists."
fi

# --- 4. Install Sharp -------------------------------------------
if npm list sharp >/dev/null 2>&1; then
  echo "[INFO] Sharp already installed."
else
  echo "[INFO] Installing Sharp..."
  npm install sharp
fi

# --- 5. Create resize.js ---------------------------------------
if [ ! -f resize.js ]; then
  cat <<'JS' > resize.js
const fs = require('fs');
const sharp = require('sharp');

const input = 'input.jpg';
const output = 'output.jpg';

(async () => {
  try {
    if (!fs.existsSync(input)) {
      console.error(`❌ ${input} not found`);
      process.exit(1);
    }
    await sharp(input)
      .resize({ width: 1200, withoutEnlargement: true })
      .toFile(output);
    console.log(`✅ Saved resized image as ${output}`);
  } catch (err) {
    console.error('❌ Error processing image:', err.message);
    process.exit(1);
  }
})();
JS
  echo "[INFO] Created resize.js"
else
  echo "[INFO] resize.js already exists."
fi

# --- 6. Final instructions -------------------------------------
cat <<'EOS'

Setup complete!

To test Sharp:
 1) Place an image named 'input.jpg' in this directory.
 2) Run:   node resize.js
 3) Check 'output.jpg' for the resized result.

If you encounter Sharp install errors:
 - Ubuntu/Debian: ensure build tools with 'sudo apt-get install build-essential libvips-dev'
 - macOS: install Xcode command line tools and 'brew install libvips'

To add more Node packages later, use 'npm install <package>'

Bonus tip: call this script from Python:
  import subprocess
  subprocess.run(['node', 'resize.js'], check=True)

EOS

