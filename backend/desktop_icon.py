"""Desktop icon that starts Seisa with one click (Info tab > Settings, or `python -m backend.desktop_icon`).

One module for both entry points, so the button and the terminal command can never drift apart.

- macOS: ~/Applications/Seisa.app (a tiny bundle whose only job is to run seisa-launcher.sh, with the logo as icon).
- Linux: ~/.local/share/applications/seisa.desktop (an entry for the application menu; the logo is used in place).
- Everything else, or a Linux without a graphical session: reported as "unsupported", nothing is written.

Nothing here is automatic and nothing comes from the client: the targets are fixed paths in the user's home, a file
is only replaced or removed when it carries our marker (so a foreign Seisa.app / seisa.desktop is never touched),
and every write goes to a temporary file first. Pinning to the Dock / taskbar stays with the user: the systems
offer no clean way to do it from a program.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import platform
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from backend.config import BASE_DIR, FRONTEND_DIR
from backend.i18n import t

LAUNCHER = BASE_DIR / "seisa-launcher.sh"
LOGO = FRONTEND_DIR / "logo.png"

APP_NAME = "Seisa.app"
DESKTOP_NAME = "seisa.desktop"
MAC_BUNDLE_ID = "local.seisa.launcher"
TOOL_TIMEOUT = 20  # seconds for sips / iconutil / update-desktop-database
ICONSET = {  # file name in the .iconset -> pixel size (the logo is 512 px, so no @2x of the largest size)
    "icon_16x16.png": 16, "icon_16x16@2x.png": 32, "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128, "icon_128x128@2x.png": 256, "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
}


class IconError(Exception):
    """A refusal or failure with a translated message (`key` is a backend/locales key) and an HTTP status."""

    def __init__(self, key: str, status_code: int = 400, **params):
        self.key = key
        self.status_code = status_code
        self.message = t(key, **params)
        super().__init__(self.message)


def _system() -> str:
    return platform.system()


def _home() -> Path:
    return Path.home()


def _shown(path: Path) -> str:
    """The path with the home directory shortened to ~ (what the UI shows)."""
    try:
        return "~/" + path.relative_to(_home()).as_posix()
    except ValueError:
        return str(path)


def _mac_app() -> Path:
    return _home() / "Applications" / APP_NAME


def _linux_entry() -> Path:
    return _home() / ".local" / "share" / "applications" / DESKTOP_NAME


def _platform_problem() -> tuple[str, str | None]:
    """(platform id, key of the reason it is unsupported or None)."""
    system = _system()
    if system == "Darwin":
        kind, problem = "macos", None
        if not (shutil.which("sips") and shutil.which("iconutil")):
            problem = "icon.no_tools"
    elif system == "Linux":
        kind, problem = "linux", None
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            problem = "icon.no_display"
    else:
        return "other", "icon.unsupported_os"
    if problem is None and not (LAUNCHER.is_file() and LOGO.is_file()):
        problem = "icon.files_missing"
    return kind, problem


def _check_project_path() -> None:
    # The path ends up in a shell script and a .desktop line; a control character would break either of them.
    if any(ord(c) < 32 for c in str(BASE_DIR)):
        raise IconError("icon.bad_path", 400)


def _mac_read(app: Path) -> dict | None:
    """The bundle's Info.plist, or None when it is missing/unreadable."""
    try:
        with open(app / "Contents" / "Info.plist", "rb") as fh:
            data = plistlib.load(fh)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _linux_read(entry: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in entry.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep:
                values[key.strip()] = value.strip()
    except (OSError, UnicodeDecodeError):
        pass
    return values


def _classify(target: Path, kind: str) -> str:
    """absent | installed | stale (made for another project path, or the launcher is gone) | foreign (not ours)."""
    if not (target.exists() or target.is_symlink()):
        return "absent"
    if target.is_symlink():
        return "foreign"
    if kind == "macos":
        info = _mac_read(target)
        managed, project = bool(info and info.get("SeisaManaged")), (info or {}).get("SeisaProject")
    else:
        info = _linux_read(target)
        managed, project = info.get("X-Seisa-Managed") == "true", info.get("X-Seisa-Project")
    if not managed:
        return "foreign"
    return "installed" if project == str(BASE_DIR) and LAUNCHER.is_file() else "stale"


def status() -> dict:
    """{"platform", "status", "path", "reason"}; status is absent | installed | stale | foreign | unsupported.

    An icon made earlier is still reported (and can be removed) when only a new one could not be made here."""
    kind, problem = _platform_problem()
    target = _mac_app() if kind == "macos" else _linux_entry() if kind == "linux" else None
    current = _classify(target, kind) if target else "absent"
    if problem and current == "absent":
        current = "unsupported"
    return {"platform": kind, "status": current, "path": _shown(target) if target else None, "reason": t(problem) if problem else None}


def _write_atomic(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _run(*cmd: str) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=TOOL_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise IconError("icon.build_failed", 500, tool=cmd[0]) from exc


def _build_icns(target: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="seisa-iconset-") as tmp:
        iconset = Path(tmp) / "Seisa.iconset"
        iconset.mkdir()
        for name, size in ICONSET.items():
            _run("sips", "-z", str(size), str(size), str(LOGO), "--out", str(iconset / name))
        _run("iconutil", "-c", "icns", str(iconset), "-o", str(target))


def _install_macos() -> None:
    app = _mac_app()
    apps_dir = app.parent
    apps_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=apps_dir, prefix=".Seisa-build-"))
    try:
        bundle = staging / APP_NAME
        (bundle / "Contents" / "MacOS").mkdir(parents=True)
        (bundle / "Contents" / "Resources").mkdir()
        _build_icns(bundle / "Contents" / "Resources" / "Seisa.icns")
        plist = {
            "CFBundleName": "Seisa", "CFBundleDisplayName": "Seisa", "CFBundleIdentifier": MAC_BUNDLE_ID,
            "CFBundleExecutable": "Seisa", "CFBundleIconFile": "Seisa", "CFBundlePackageType": "APPL",
            "CFBundleVersion": "1", "CFBundleShortVersionString": "1", "LSMinimumSystemVersion": "10.13",
            "SeisaManaged": True, "SeisaProject": str(BASE_DIR),
        }
        (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps(plist))
        script = bundle / "Contents" / "MacOS" / "Seisa"
        script.write_text(f"#!/bin/bash\nexec /bin/bash {shlex.quote(str(LAUNCHER))}\n", encoding="utf-8")
        script.chmod(0o755)
        if app.exists():
            shutil.rmtree(app)  # only reached for a bundle that carries our marker (checked by install())
        os.replace(bundle, app)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _desktop_quote(value: str) -> str:
    """One argument of a .desktop Exec line (freedesktop quoting: double quotes, \\ for ` $ \" \\, %% for %)."""
    escaped = "".join("\\" + c if c in '"`$\\' else c for c in value).replace("%", "%%")
    return f'"{escaped}"'


def _refresh_menu(directory: Path) -> None:
    """Asks the desktop to re-read its menu entries; only a cache refresh, the entry works without it."""
    if shutil.which("update-desktop-database"):
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(["update-desktop-database", str(directory)], capture_output=True, timeout=TOOL_TIMEOUT)


def _install_linux() -> None:
    entry = _linux_entry()
    text = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Seisa",
        f"Comment={t('icon.comment', lang='en')}",
        f"Comment[pl]={t('icon.comment', lang='pl')}",
        f"Exec=/bin/bash {_desktop_quote(str(LAUNCHER))}",
        f"Icon={LOGO}",
        "Terminal=false",
        "Categories=Network;Security;",
        "StartupNotify=false",
        "X-Seisa-Managed=true",
        f"X-Seisa-Project={BASE_DIR}",
        "",
    ])
    _write_atomic(entry, text.encode("utf-8"), 0o644)
    _refresh_menu(entry.parent)


def install() -> dict:
    kind, problem = _platform_problem()
    if problem:
        raise IconError(problem, 400)
    _check_project_path()
    current = status()["status"]
    if current == "foreign":
        raise IconError("icon.foreign", 409, path=status()["path"])
    if kind == "macos":
        _install_macos()
    else:
        _install_linux()
    return status()


def remove() -> dict:
    kind, _problem = _platform_problem()
    if kind == "other":
        raise IconError("icon.unsupported_os", 400)
    current = status()
    if current["status"] == "foreign":
        raise IconError("icon.foreign", 409, path=current["path"])
    if current["status"] in ("installed", "stale"):
        if kind == "macos":
            shutil.rmtree(_mac_app())
        else:
            _linux_entry().unlink()
            _refresh_menu(_linux_entry().parent)
    return status()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.desktop_icon", description="Seisa desktop icon (macOS, Linux).")
    parser.add_argument("action", choices=("status", "install", "remove"))
    action = parser.parse_args(argv).action
    try:
        result = {"status": status, "install": install, "remove": remove}[action]()
    except IconError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    print(f"{result['status']}" + (f" ({result['path']})" if result["path"] else "") + (f" - {result['reason']}" if result["reason"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
