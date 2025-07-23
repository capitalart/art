import os
from config import _CRITICAL_FOLDERS, BASE_DIR


def create_all_folders():
    for folder in _CRITICAL_FOLDERS:
        folder.mkdir(parents=True, exist_ok=True)
    print("✅ All critical folders created.")


def remove_obsolete_folders():
    all_current = {str(f.resolve()) for f in _CRITICAL_FOLDERS}
    for root, dirs, _ in os.walk(BASE_DIR):
        for d in dirs:
            folder_path = os.path.join(root, d)
            if folder_path not in all_current and d not in {
                '.git', '.venv', 'venv', 'env', '__pycache__'}:
                try:
                    os.rmdir(folder_path)
                    print(f"Removed obsolete folder: {folder_path}")
                except Exception as e:
                    print(f"Could not remove {folder_path}: {e}")


if __name__ == "__main__":
    create_all_folders()
    remove_obsolete_folders()
