"""backend/desktop_icon.py: the icon is made only at fixed places in the home directory, only when asked, and a file
that Seisa did not make is never replaced or removed.

HOME points to a temporary directory in every test, so nothing here can touch the real Applications folder or menu.
The expected file contents come from the freedesktop Desktop Entry spec and from Apple's Info.plist keys, not from
what the code happens to write."""
from __future__ import annotations

import plistlib
import shlex
import shutil
import subprocess

import pytest

from backend import desktop_icon as di


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def linux(home, monkeypatch):
    monkeypatch.setattr(di, "_system", lambda: "Linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(di.shutil, "which", lambda name: None)  # no update-desktop-database call
    return home


@pytest.fixture
def mac(home, monkeypatch):
    monkeypatch.setattr(di, "_system", lambda: "Darwin")
    return home


def _foreign_app(home, plist: dict | None):
    bundle = home / "Applications" / "Seisa.app" / "Contents"
    bundle.mkdir(parents=True)
    if plist is not None:
        (bundle / "Info.plist").write_bytes(plistlib.dumps(plist))
    return bundle.parent


# ---- Linux ----

def test_linux_install_writes_a_valid_entry_and_reports_installed(linux):
    assert di.status()["status"] == "absent"
    result = di.install()
    entry = linux / ".local" / "share" / "applications" / "seisa.desktop"
    lines = entry.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "[Desktop Entry]"
    assert "Type=Application" in lines
    assert "Terminal=false" in lines
    assert "X-Seisa-Managed=true" in lines
    assert f"X-Seisa-Project={di.BASE_DIR}" in lines
    assert f"Icon={di.ICON}" in lines
    exec_line = next(line for line in lines if line.startswith("Exec="))
    assert exec_line == f'Exec=/bin/bash "{di.LAUNCHER}"'
    assert result["status"] == "installed" and result["platform"] == "linux"
    assert result["path"] == "~/.local/share/applications/seisa.desktop"


def test_linux_install_is_repeatable(linux):
    di.install()
    assert di.install()["status"] == "installed"


def test_linux_remove_deletes_only_our_entry(linux):
    di.install()
    assert di.remove()["status"] == "absent"
    assert not (linux / ".local" / "share" / "applications" / "seisa.desktop").exists()
    assert di.remove()["status"] == "absent"  # nothing to remove is not an error


def test_linux_foreign_entry_is_never_replaced_or_removed(linux):
    entry = linux / ".local" / "share" / "applications" / "seisa.desktop"
    entry.parent.mkdir(parents=True)
    entry.write_text("[Desktop Entry]\nName=Somebody else's Seisa\n", encoding="utf-8")
    assert di.status()["status"] == "foreign"
    for action in (di.install, di.remove):
        with pytest.raises(di.IconError) as err:
            action()
        assert err.value.status_code == 409
    assert entry.read_text(encoding="utf-8") == "[Desktop Entry]\nName=Somebody else's Seisa\n"


def test_linux_entry_for_another_folder_is_stale_and_install_repairs_it(linux):
    di.install()
    entry = linux / ".local" / "share" / "applications" / "seisa.desktop"
    entry.write_text(entry.read_text(encoding="utf-8").replace(f"X-Seisa-Project={di.BASE_DIR}", "X-Seisa-Project=/old/place"), encoding="utf-8")
    assert di.status()["status"] == "stale"
    assert di.install()["status"] == "installed"


def test_linux_without_a_graphical_session_is_unsupported(linux, monkeypatch):
    monkeypatch.delenv("DISPLAY")
    assert di.status()["status"] == "unsupported" and di.status()["reason"]
    with pytest.raises(di.IconError):
        di.install()
    assert not (linux / ".local").exists()


def test_other_systems_are_unsupported(home, monkeypatch):
    monkeypatch.setattr(di, "_system", lambda: "Windows")
    assert di.status() == {"platform": "other", "status": "unsupported", "path": None, "reason": di.t("icon.unsupported_os")}
    for action in (di.install, di.remove):
        with pytest.raises(di.IconError):
            action()


@pytest.mark.parametrize("value, expected", [
    ("/plain/path", '"/plain/path"'),
    ("/with space/seisa", '"/with space/seisa"'),
    ('/a"b`c$d\\e', '"/a\\"b\\`c\\$d\\\\e"'),
    ("/100%/x", '"/100%%/x"'),
])
def test_desktop_exec_quoting_follows_the_spec(value, expected):
    assert di._desktop_quote(value) == expected


def test_a_control_character_in_the_project_path_is_refused(linux, monkeypatch):
    monkeypatch.setattr(di, "BASE_DIR", di.BASE_DIR.parent / "bad\nname")
    with pytest.raises(di.IconError):
        di.install()
    assert not (linux / ".local").exists()


# ---- macOS ----

def test_mac_foreign_bundle_is_never_replaced_or_removed(mac, monkeypatch):
    monkeypatch.setattr(di.shutil, "which", lambda name: "/usr/bin/" + name)
    app = _foreign_app(mac, {"CFBundleName": "Not ours"})
    assert di.status()["status"] == "foreign"
    for action in (di.install, di.remove):
        with pytest.raises(di.IconError) as err:
            action()
        assert err.value.status_code == 409
    assert (app / "Contents" / "Info.plist").is_file()


def test_mac_symlink_is_foreign(mac, monkeypatch, tmp_path):
    monkeypatch.setattr(di.shutil, "which", lambda name: "/usr/bin/" + name)
    target = tmp_path / "elsewhere"
    target.mkdir()
    (mac / "Applications").mkdir()
    (mac / "Applications" / "Seisa.app").symlink_to(target)
    assert di.status()["status"] == "foreign"
    with pytest.raises(di.IconError):
        di.remove()
    assert target.is_dir()


def test_mac_without_sips_and_iconutil_is_unsupported(mac, monkeypatch):
    monkeypatch.setattr(di.shutil, "which", lambda name: None)
    assert di.status()["status"] == "unsupported"
    with pytest.raises(di.IconError):
        di.install()
    assert not (mac / "Applications").exists()


def _skip_unless_sips_can_write(tmp_path):
    """sips fails with "Cannot write to file" inside a sandbox that forbids its own temporary files (for example the
    Claude Code sandbox). That is the environment, not the code, so one tiny trial run decides between run and skip."""
    try:
        subprocess.run(["sips", "-z", "16", "16", str(di.ICON), "--out", str(tmp_path / "probe.png")],
                       check=True, capture_output=True, timeout=di.TOOL_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        pytest.skip("sips cannot write here (sandbox?); run the tests outside it to cover this one")


@pytest.mark.skipif(not (shutil.which("sips") and shutil.which("iconutil")), reason="needs the macOS image tools")
def test_mac_install_and_remove_round_trip(home, monkeypatch, tmp_path_factory):
    _skip_unless_sips_can_write(tmp_path_factory.mktemp("probe"))
    monkeypatch.setattr(di, "_system", lambda: "Darwin")
    result = di.install()
    app = home / "Applications" / "Seisa.app"
    assert result["status"] == "installed" and result["path"] == "~/Applications/Seisa.app"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundlePackageType"] == "APPL" and info["CFBundleExecutable"] == "Seisa"
    assert info["SeisaManaged"] is True and info["SeisaProject"] == str(di.BASE_DIR)
    assert (app / "Contents" / "Resources" / "Seisa.icns").read_bytes()[:4] == b"icns"
    launcher = app / "Contents" / "MacOS" / "Seisa"
    assert launcher.stat().st_mode & 0o111
    assert launcher.read_text(encoding="utf-8").splitlines()[-1] == f"exec /bin/bash {shlex.quote(str(di.LAUNCHER))}"
    assert not [p for p in (home / "Applications").iterdir() if p.name.startswith(".")]  # no build leftovers
    assert di.install()["status"] == "installed"
    assert di.remove()["status"] == "absent"
    assert not app.exists()
