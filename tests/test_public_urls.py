import config
from helpers.listing_utils import generate_public_image_urls

def setup_paths(tmp_path, monkeypatch):
    base = tmp_path / "app"
    base.mkdir()
    monkeypatch.setattr(config, "BASE_DIR", base)
    monkeypatch.setattr(config, "BASE_URL", "http://example.com")
    unanalysed = base / "art-processing" / "unanalysed-artwork"
    processed = base / "art-processing" / "processed-artwork"
    finalised = base / "art-processing" / "finalised-artwork"
    vault = base / "art-processing" / "artwork-vault"
    for p in (unanalysed, processed, finalised, vault):
        p.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "UNANALYSED_ROOT", unanalysed)
    monkeypatch.setattr(config, "PROCESSED_ROOT", processed)
    monkeypatch.setattr(config, "FINALISED_ROOT", finalised)
    monkeypatch.setattr(config, "ARTWORK_VAULT_ROOT", vault)
    monkeypatch.setattr(config, "UNANALYSED_IMG_URL_PREFIX", "unanalysed-img")
    monkeypatch.setattr(config, "PROCESSED_URL_PATH", f"static/{processed.relative_to(base).as_posix()}")
    monkeypatch.setattr(config, "FINALISED_URL_PATH", f"static/{finalised.relative_to(base).as_posix()}")
    monkeypatch.setattr(config, "LOCKED_URL_PATH", f"static/{vault.relative_to(base).as_posix()}")
    return processed, vault

def test_generate_public_image_urls_processed(tmp_path, monkeypatch):
    processed, _ = setup_paths(tmp_path, monkeypatch)
    folder = processed / "test-art"
    folder.mkdir()
    (folder / "test-art-1.jpg").write_bytes(b"a")
    urls = generate_public_image_urls("test-art", "processed")
    expected = f"http://example.com/{processed.relative_to(config.BASE_DIR).as_posix()}/test-art/test-art-1.jpg"
    assert urls == [expected]

def test_generate_public_image_urls_vault(tmp_path, monkeypatch):
    _, vault = setup_paths(tmp_path, monkeypatch)
    folder = vault / "LOCKED-test-art"
    folder.mkdir()
    (folder / "LOCKED-test-art.jpg").write_bytes(b"a")
    urls = generate_public_image_urls("test-art", "vault")
    expected = f"http://example.com/{vault.relative_to(config.BASE_DIR).as_posix()}/LOCKED-test-art/LOCKED-test-art.jpg"
    assert urls == [expected]
