import hashlib
import zipfile

import pytest

from undertone import runtime, updater


def test_version_compare():
    assert updater.is_newer("0.2.1", "0.2.0")
    assert updater.is_newer("0.10.0", "0.9.9")
    assert not updater.is_newer("0.2.0", "0.2.0")
    assert not updater.is_newer("v0.1.9", "0.2.0")


def test_latest_picks_windows_zip(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "tag_name": "v9.0.0",
                "html_url": "https://github.com/x/releases/tag/v9.0.0",
                "assets": [
                    {"name": "notes.txt", "browser_download_url": "https://x/notes.txt"},
                    {"name": "Undertone-9.0.0-windows.zip", "browser_download_url": "https://x/u.zip",
                     "size": 5, "digest": "sha256:abc"},
                ],
            }

    import requests

    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp())
    rel = updater.check()
    assert rel.version == "9.0.0" and rel.url == "https://x/u.zip" and rel.sha256 == "abc"


def _fake_release_zip(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("python/pythonw.exe", "exe")
        z.writestr("undertone/__init__.py", '__version__ = "9.0.0"\n')
        z.writestr("Undertone.bat", "@echo off")


@pytest.fixture
def staging(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "STAGING", tmp_path / "app" / "_update")
    monkeypatch.setattr(updater, "local_dir", lambda: tmp_path / "local")
    return updater.STAGING


def test_download_stages_release(tmp_path, staging, monkeypatch):
    src = tmp_path / "src.zip"
    _fake_release_zip(src)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    monkeypatch.setattr(runtime, "_download", lambda url, dest, progress, label: dest.write_bytes(src.read_bytes()))
    seen = []
    rel = updater.Release("9.0.0", "https://x/Undertone-9.0.0-windows.zip", 1, digest, "")
    updater.download(rel, lambda f, label: seen.append(f))
    assert (staging / "undertone" / "__init__.py").is_file()
    assert updater.staged_version() == "9.0.0"
    assert not (tmp_path / "local" / "updates").exists()  # zip removed
    assert seen[-1] == 1.0 and seen == sorted(seen)


def test_download_rejects_bad_checksum(tmp_path, staging, monkeypatch):
    monkeypatch.setattr(runtime, "_download", lambda url, dest, progress, label: _fake_release_zip(dest))
    rel = updater.Release("9.0.0", "https://x/Undertone-9.0.0-windows.zip", 1, "0" * 64, "")
    with pytest.raises(RuntimeError, match="corrupted"):
        updater.download(rel, lambda f, label: None)
    assert not updater.staged_version()


def test_clean_leftovers_keeps_a_ready_update(tmp_path, staging, monkeypatch):
    monkeypatch.setattr(updater, "ROOT", staging.parent)
    monkeypatch.setattr(updater, "supported", lambda: True)
    staging.mkdir(parents=True)
    (staging.parent / "_old_20260101000000" / "python").mkdir(parents=True)
    (staging / "update-ready.txt").write_text("9.0.0")
    updater.clean_leftovers()
    assert staging.is_dir() and not list(staging.parent.glob("_old_*"))
    (staging / "update-ready.txt").write_text("0.0.1")  # older than this version: stale
    updater.clean_leftovers()
    assert not staging.exists()
