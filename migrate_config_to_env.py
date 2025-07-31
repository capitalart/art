#!/usr/bin/env python3
"""
Migrate Hardcoded Config Values to .env File
--------------------------------------------
Safely extract known config keys and write them into your `.env` file.
Will append only if the key is not already present.

Run with: python3 migrate_config_to_env.py
"""

import os
from pathlib import Path

# --- Keys and default values to migrate ---
CONFIG_VARS = {
    "BRAND_NAME": "Art Narrator",
    "BRAND_TAGLINE": "Create. Automate. Sell Art.",
    "BRAND_AUTHOR": "Robin Custance",
    "BRAND_DOMAIN": "artnarrator.com",
    "LIVE_MODE": "False",
    "OPENAI_API_KEY": "",  # Leave blank; user must fill manually
    "FLASK_SECRET_KEY": "",  # Leave blank; user must fill manually
}

ENV_PATH = Path(".env")

def load_existing_env(env_path):
    existing_keys = set()
    if env_path.exists():
        with env_path.open("r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key = line.split("=", 1)[0].strip()
                    existing_keys.add(key)
    return existing_keys

def append_missing_keys(env_path, keys_to_add):
    with env_path.open("a", encoding="utf-8") as f:
        for key, default_val in keys_to_add.items():
            f.write(f"{key}={default_val}\n")
            print(f"✅ Added: {key}")

def main():
    print(f"📦 Preparing to migrate config variables to {ENV_PATH}")
    existing_keys = load_existing_env(ENV_PATH)

    missing_keys = {
        k: v for k, v in CONFIG_VARS.items()
        if k not in existing_keys
    }

    if not missing_keys:
        print("✅ .env already has all config keys. Nothing to update.")
        return

    print(f"✍️ Writing {len(missing_keys)} new keys to .env...")
    append_missing_keys(ENV_PATH, missing_keys)

    print("\n✅ Migration complete.")
    print("🛠️ Please manually fill in secrets like OPENAI_API_KEY and FLASK_SECRET_KEY.")

if __name__ == "__main__":
    main()
