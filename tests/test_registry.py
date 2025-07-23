import os
import importlib
import json
from pathlib import Path
import sys


def test_move_and_registry(tmp_path, monkeypatch):
    monkeypatch.setenv('ART_PROCESSING_DIR', str(tmp_path / 'ap'))
    monkeypatch.setenv('OUTPUT_JSON', str(tmp_path / 'ap' / 'reg.json'))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import config
    importlib.reload(config)
    from routes import utils
    importlib.reload(utils)

    folder = utils.create_unanalysed_subfolder()
    dummy = folder / 'img.jpg'
    dummy.write_text('x')
    uid = 'u1'
    utils.register_new_artwork(uid, 'img.jpg', folder, ['img.jpg'], 'unanalysed', 'img')

    dest = Path(tmp_path / 'processed' / 'img.jpg')
    utils.move_and_log(dummy, dest, uid, 'processed')

    assert not dummy.exists()
    assert dest.exists()
    reg = json.loads(Path(config.OUTPUT_JSON).read_text())
    rec = reg[uid]
    assert rec['status'] == 'processed'
    assert dest.name in rec['assets']

    vault = Path(tmp_path / 'vault')
    vault.mkdir()
    utils.update_status(uid, vault, 'vault')
    reg = json.loads(Path(config.OUTPUT_JSON).read_text())
    assert reg[uid]['status'] == 'vault'

