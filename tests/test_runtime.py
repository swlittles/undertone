import shutil
import sys
import zipfile

from undertone import runtime


def _fake_wheel(path, pkg):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"{pkg}/__init__.py", "")
        z.writestr(f"{pkg}/include/ATen/deep.h", "")
        z.writestr(f"{pkg}/lib/c10.dll", "dll")
        z.writestr(f"{pkg}/lib/c10.lib", "import lib")
        z.writestr(f"{pkg}-1.0.data/purelib/{pkg}_extra.py", "")
        z.writestr(f"{pkg}-1.0.data/scripts/tool.exe", "")
        z.writestr(f"{pkg}-1.0.dist-info/METADATA", "Name: x")


def test_install_unpacks_wheels_and_activates(tmp_path, monkeypatch):
    rt = tmp_path / "rt"
    monkeypatch.setattr(runtime, "RUNTIME", rt)
    monkeypatch.setattr(runtime, "_SKIP_PREFIXES", ("torch/include/", "torch/share/"))
    monkeypatch.setattr(runtime, "_wheel_urls", lambda flavor: [f"https://x/{p}-1.whl" for p in ("torch", "torchaudio")])
    monkeypatch.setattr(runtime, "_download", lambda url, dest, progress, label: _fake_wheel(dest, url.rsplit("/", 1)[1].split("-")[0]))
    (rt / "old-version").mkdir(parents=True)
    path_before = list(sys.path)
    seen = []
    try:
        runtime.install("cpu", lambda f, label: seen.append(f))
        target = rt / "cpu"
        assert runtime.installed_flavor() == "cpu"
        assert (target / "torch" / "__init__.py").is_file()
        assert (target / "torch" / "lib" / "c10.dll").is_file()
        assert (target / "torch_extra.py").is_file()  # .data/purelib goes to the top
        assert (target / "torch-1.0.dist-info" / "METADATA").is_file()
        assert not (target / "torch" / "include").exists()
        assert not (target / "torch" / "lib" / "c10.lib").exists()
        assert not list(target.rglob("tool.exe"))
        assert sorted(p.name for p in rt.iterdir()) == ["cpu"]  # downloads and old versions removed
        assert sys.path[0] == str(target)
        assert seen[-1] == 1.0 and seen == sorted(seen)
    finally:
        sys.path[:] = path_before


def test_incomplete_install_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "RUNTIME", tmp_path)
    (tmp_path / "cu128" / "torch").mkdir(parents=True)  # no marker: interrupted
    assert runtime.installed_flavor() is None
    shutil.rmtree(tmp_path / "cu128")
