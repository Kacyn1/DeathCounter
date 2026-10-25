import hashlib
import io
import json
import sys
from contextlib import contextmanager

import pytest

from deathcounter import updater
from deathcounter.updater import Release, UpdateError


def api_payload(tag="v1.9.0", content=b"nowy exe", digest=None):
    digest = digest or "sha256:" + hashlib.sha256(content).hexdigest()
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/Kacyn1/DeathCounter/releases/tag/{tag}",
        "assets": [
            {"name": "LICENSE.txt", "size": 3, "digest": "sha256:00",
             "browser_download_url": "https://example.invalid/LICENSE.txt"},
            {"name": "DeathCounter.exe", "size": len(content), "digest": digest,
             "browser_download_url": "https://example.invalid/DeathCounter.exe"},
        ],
    }


def opener_for(body: bytes):
    @contextmanager
    def opener(request, timeout):
        yield io.BytesIO(body)
    return opener


def test_versions():
    assert updater.parse_version("v1.10.2") == (1, 10, 2)
    assert updater.parse_version("beta") == ()
    assert updater.is_newer("1.10.0", "1.9.3")
    assert not updater.is_newer("1.8.0", "1.8.0")
    assert not updater.is_newer("", "1.8.0")


def test_daily_check():
    assert updater.due(0.0, 1_700_000_000)
    assert not updater.due(1_700_000_000, 1_700_000_000 + 3600)
    assert updater.due(1_700_000_000, 1_700_000_000 + 25 * 3600)
    assert updater.due(1_700_000_000, 1_699_000_000)  # cofnięty zegar


def test_fetch_latest_reads_exe_asset():
    release = updater.fetch_latest(opener_for(json.dumps(api_payload()).encode()))
    assert release.version == "1.9.0"
    assert release.download_url.endswith("/DeathCounter.exe")
    assert release.sha256 == hashlib.sha256(b"nowy exe").hexdigest()


def test_release_without_digest_cannot_be_downloaded(tmp_path):
    payload = api_payload()
    del payload["assets"][1]["digest"]
    release = updater.release_from_json(payload)
    assert release.download_url is None
    with pytest.raises(UpdateError):
        updater.download(release, tmp_path / "new.exe")


def test_fetch_errors_become_update_error():
    def offline(request, timeout):
        raise OSError("brak sieci")
    with pytest.raises(UpdateError, match="brak sieci"):
        updater.fetch_latest(offline)


def test_download_verifies_checksum(tmp_path):
    release = updater.release_from_json(api_payload(content=b"nowy exe"))
    seen = []
    path = updater.download(release, tmp_path / "new.exe", lambda done, total: seen.append((done, total)),
                            opener=opener_for(b"nowy exe"))
    assert path.read_bytes() == b"nowy exe"
    assert seen[-1] == (8, 8)

    with pytest.raises(UpdateError, match="Suma kontrolna"):
        updater.download(release, tmp_path / "bad.exe", opener=opener_for(b"podmienione"[:8]))
    assert not (tmp_path / "bad.exe").exists()
    assert not (tmp_path / "bad.exe.part").exists()


def test_install_swaps_files_and_cleanup_removes_old(tmp_path):
    exe = tmp_path / "DeathCounter.exe"
    exe.write_bytes(b"stary")
    new = tmp_path / "DeathCounter.new.exe"
    new.write_bytes(b"nowy")
    updater.install(new, exe)
    assert exe.read_bytes() == b"nowy"
    assert (tmp_path / "DeathCounter.old.exe").read_bytes() == b"stary"
    updater.cleanup(exe)
    assert not (tmp_path / "DeathCounter.old.exe").exists()
    assert exe.exists()


def test_install_failure_keeps_running_version(tmp_path):
    exe = tmp_path / "DeathCounter.exe"
    exe.write_bytes(b"stary")
    with pytest.raises(UpdateError):
        updater.install(tmp_path / "brak.exe", exe)
    assert exe.read_bytes() == b"stary"


def test_running_from_source_has_no_exe():
    assert updater.running_exe() is None


def test_release_dataclass_defaults():
    release = Release("1.9.0", "", None, 0, "")
    assert release.download_url is None


def test_relaunch_command_for_exe_and_sources(monkeypatch, tmp_path):
    exe = tmp_path / "DeathCounter.exe"
    monkeypatch.setattr(updater, "running_exe", lambda: exe)
    assert updater.relaunch_command() == [str(exe)]
    monkeypatch.setattr(updater, "running_exe", lambda: None)
    monkeypatch.setattr(updater.sys, "executable", "python.exe")
    monkeypatch.setattr(updater.sys, "argv", [str(tmp_path / "DeathCounter.pyw")])
    assert updater.relaunch_command() == ["python.exe", str((tmp_path / "DeathCounter.pyw").resolve())]
    monkeypatch.setattr(updater.sys, "argv", [str(tmp_path / "__main__.py")])
    assert updater.relaunch_command() == ["python.exe", "-m", "deathcounter"]


@pytest.mark.skipif(sys.platform != "win32", reason="subprocess.DETACHED_PROCESS jest tylko na Windowsie")
def test_restart_passes_argument(monkeypatch, tmp_path):
    started = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda command, **kwargs: started.append((command, kwargs["cwd"])))
    monkeypatch.setattr(updater, "relaunch_command", lambda: [str(tmp_path / "DeathCounter.exe")])
    updater.restart(None, updater.RESTART_ARG)
    assert started == [([str(tmp_path / "DeathCounter.exe"), "--restart"], str(tmp_path))]
