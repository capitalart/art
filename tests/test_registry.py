# In tests/test_registry.py

import os
import importlib
import json
from pathlib import Path
import sys

def test_move_and_registry(tmp_path, monkeypatch):
    """
    Tests that moving a file also updates its record in the central registry.
    """
    # 1. Setup mock directories and files
    mock_unanalysed_dir = tmp_path / "unanalysed"
    mock_processed_dir = tmp_path / "processed"
    mock_registry_file = tmp_path / "registry.json"
    mock_unanalysed_dir.mkdir()

    # 2. Monkeypatch the config variables directly
    # This is safer than reloading the module.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import config
    monkeypatch.setattr(config, "UNANALYSED_ROOT", mock_unanalysed_dir)
    monkeypatch.setattr(config, "OUTPUT_JSON", mock_registry_file)

    # 3. Reload the modules that USE the config to ensure they get the patched values
    from helpers import listing_utils
    from routes import utils
    importlib.reload(listing_utils)
    importlib.reload(utils)

    # 4. Create a dummy file and register it
    folder = listing_utils.create_unanalysed_subfolder("test_image.jpg")
    dummy_file = folder / 'img.jpg'
    dummy_file.write_text('test content')
    uid = 'test_uid_123'
    utils.register_new_artwork(uid, 'img.jpg', folder, ['img.jpg'], 'unanalysed', 'img-base')

    # 5. Move the file to a new location
    dest_path = mock_processed_dir / 'img.jpg'
    utils.move_and_log(dummy_file, dest_path, uid, 'processed')

    # 6. Assertions
    assert not dummy_file.exists()
    assert dest_path.exists()

    registry_data = json.loads(mock_registry_file.read_text())
    record = registry_data[uid]
    
    assert record['status'] == 'processed'
    assert str(dest_path.parent) in record['current_folder']
    assert dest_path.name in record['assets']

    # 7. Test a status update
    vault_folder = tmp_path / 'vault'
    vault_folder.mkdir()
    utils.update_status(uid, vault_folder, 'vault')
    
    registry_data_after_update = json.loads(mock_registry_file.read_text())
    assert registry_data_after_update[uid]['status'] == 'vault'