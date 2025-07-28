import os
from pathlib import Path

# ============================== [ CONFIGURATION ] ==============================

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR
OUTPUT_FILE = "folder_structure.txt"

# Folders or files to ignore (case insensitive)
# MODIFIED: Added user-specific and tool-specific dotfiles/folders to ignore
IGNORE_NAMES = {
    # Standard dev/tooling ignores
    ".git", "__pycache__", ".venv", "venv", "env", ".idea", ".DS_Store",
    "node_modules", ".nojekyll", ".pytest_cache", ".mypy_cache",
    ".ipynb_checkpoints", ".history", ".cache",
    # User-specific shell/config files from home directory
    ".bash_history", ".bash_logout", ".bashrc", ".profile", ".lesshst",
    ".python_history", ".selected_editor", ".wget-hsts",
    # Tool-specific config/cache folders
    ".codegpt", ".config", ".dotnet", ".local", ".sdkman", ".ssh", ".vscode-server"
}

# File extensions to ignore (add as needed, e.g., '.log', '.tmp')
IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".swp", ".log", ".tmp"
}

# ============================== [ HELPER FUNCTION ] ==============================

def should_ignore(entry):
    # Ignore by exact name (case insensitive)
    if entry.lower() in {x.lower() for x in IGNORE_NAMES}:
        return True
    # Ignore by extension
    _, ext = os.path.splitext(entry)
    if ext.lower() in IGNORE_EXTENSIONS:
        return True
    return False

def generate_tree(start_path: str, prefix: str = "") -> str:
    tree_str = ""
    try:
        entries = sorted(os.listdir(start_path))
    except PermissionError:
        # Skip protected dirs (shouldn’t happen, but just in case)
        return tree_str
    entries = [e for e in entries if not should_ignore(e)]

    for idx, entry in enumerate(entries):
        full_path = os.path.join(start_path, entry)
        connector = "└── " if idx == len(entries) - 1 else "├── "
        tree_str += f"{prefix}{connector}{entry}\n"

        if os.path.isdir(full_path):
            extension = "    " if idx == len(entries) - 1 else "│   "
            tree_str += generate_tree(full_path, prefix + extension)
    return tree_str

# ============================== [ MAIN EXECUTION ] ==============================

if __name__ == "__main__":
    print(f"📂 Generating folder structure starting at: {os.path.abspath(ROOT_DIR)}")
    tree_output = f"{os.path.basename(os.path.abspath(ROOT_DIR))}\n"
    tree_output += generate_tree(str(ROOT_DIR))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(tree_output)

    print(f"✅ Folder structure written to: {OUTPUT_FILE}")