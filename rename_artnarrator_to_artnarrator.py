import os
import re

ROOT = os.path.expanduser('~/art')  # Change to your base dir if different

# List of file extensions to check (add more if needed)
TEXT_EXTENSIONS = (
    '.py', '.txt', '.md', '.html', '.js', '.css', '.json', '.yaml', '.yml', '.ini', '.cfg', '.toml',
    '.csv', '.ts', '.scss', '.sh', '.bat', '.env', '.sql'
)

def should_edit_file(filename):
    return filename.endswith(TEXT_EXTENSIONS)

def replace_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    # Replace all common case patterns
    content_new = (
        content
        .replace('artnarrator', 'artnarrator')
        .replace('ArtNarrator', 'ArtNarrator')
        .replace('Artnarrator', 'Artnarrator')
        .replace('ARTNARRATOR', 'ARTNARRATOR')
    )
    if content_new != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content_new)
        print(f'Updated: {filepath}')

def rename_if_needed(path):
    # Only rename if artnarrator is in the name
    basename = os.path.basename(path)
    dirname = os.path.dirname(path)
    new_basename = (
        basename
        .replace('artnarrator', 'artnarrator')
        .replace('ArtNarrator', 'ArtNarrator')
        .replace('Artnarrator', 'Artnarrator')
        .replace('ARTNARRATOR', 'ARTNARRATOR')
    )
    if new_basename != basename:
        new_path = os.path.join(dirname, new_basename)
        os.rename(path, new_path)
        print(f'Renamed: {path} -> {new_path}')
        return new_path
    return path

for root, dirs, files in os.walk(ROOT, topdown=False):
    # Skip venvs, .git, __pycache__, node_modules, etc.
    skip_dirs = ('venv', '.git', '__pycache__', 'node_modules', '.vscode', '.idea')
    dirs[:] = [d for d in dirs if d not in skip_dirs and 'venv' not in d]
    # Rename files
    for name in files:
        filepath = os.path.join(root, name)
        # Edit contents if text file
        if should_edit_file(name):
            replace_in_file(filepath)
        # Rename file if needed
        rename_if_needed(filepath)
    # Rename folder itself if needed
    rename_if_needed(root)
