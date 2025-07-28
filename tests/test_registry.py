# tests/test_registry.py
import os
import importlib
import json
from pathlib import Path
import sys

def test_move_and_registry(tmp_path, monkeypatch):
    """
    Tests that moving a file also updates its record in the central registry.
    """
    # --- FIX: Set BASE_DIR to the temporary path for consistent relative paths ---
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import config
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)

    # Set other environment variables to point to the temporary directory
    monkeypatch.setenv('ART_PROCESSING_DIR', str(tmp_path / 'ap'))
    monkeypatch.setenv('OUTPUT_JSON', str(tmp_path / 'ap' / 'reg.json'))

    # Reload modules to ensure they use the new temporary paths
    importlib.reload(config)
    from routes import utils
    importlib.reload(utils)

    # 1. Create a dummy file and register it
    folder = utils.create_unanalysed_subfolder()
    dummy_file = folder / 'img.jpg'
    dummy_file.write_text('test content')
    uid = 'test_uid_123'
    utils.register_new_artwork(uid, 'img.jpg', folder, ['img.jpg'], 'unanalysed', 'img-base')

    # 2. Move the file to a new location
    dest_folder = tmp_path / 'processed'
    dest_path = dest_folder / 'img.jpg'
    utils.move_and_log(dummy_file, dest_path, uid, 'processed')

    # 3. Assertions
    assert not dummy_file.exists()
    assert dest_path.exists()

    registry_data = json.loads(Path(config.OUTPUT_JSON).read_text())
    record = registry_data[uid]
    
    assert record['status'] == 'processed'
    assert str(dest_path.parent) in record['current_folder']
    assert dest_path.name in record['assets']

    # 4. Test a status update
    vault_folder = tmp_path / 'vault'
    vault_folder.mkdir()
    utils.update_status(uid, vault_folder, 'vault')
    
    registry_data_after_update = json.loads(Path(config.OUTPUT_JSON).read_text())
    assert registry_data_after_update[uid]['status'] == 'vault'