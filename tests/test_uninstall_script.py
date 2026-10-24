"""uninstall.sh: the uninstaller asks before every step, deletes only fixed paths inside the Seisa folder and its own
icon, keeps the user's data unless the exact word is typed, and only shows a preview without a terminal.

Every run happens in a throw-away copy of the minimal folder layout with HOME in a temporary directory, so nothing
here can touch the real project, the real Applications folder or the real menu. `uname` and `curl` are fakes on the
PATH, so one machine tests both systems and both "Seisa is running" answers. The questions are answered through a
pseudo-terminal, because the script asks only when it runs in a terminal. The icon files are written by hand from the
markers documented in backend/desktop_icon.py and docs/OPERATIONS.md, not by the icon code."""
from __future__ import annotations

import os
import plistlib
import pty
import select
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow  # every test starts the script in a child process

SCRIPT = Path(__file__).resolve().parent.parent / "uninstall.sh"
SYSTEMS = ("Linux", "Darwin")


@pytest.fixture
def tree(tmp_path):
    folder = tmp_path / "seisa"
    (folder / "backend").mkdir(parents=True)
    for name in ("install.sh", "seisa.sh", "seisa-launcher.sh", "requirements.lock", "backend/desktop_icon.py"):
        (folder / name).write_text("# stand-in\n", encoding="utf-8")
    shutil.copy(SCRIPT, folder / "uninstall.sh")
    (tmp_path / "home").mkdir()
    return folder


def _bin(tree: Path, system: str, running: bool = False) -> Path:
    """Fakes for uname (the system to simulate), curl (is Seisa running?) and python3 (a known Python on the PATH)."""
    bin_dir = tree.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    fakes = {
        "uname": f"#!/bin/sh\necho {system}\n",
        "curl": f"#!/bin/sh\nexit {0 if running else 7}\n",
        "python3": f'#!/bin/sh\nexec "{sys.executable}" "$@"\n',
    }
    for name, body in fakes.items():
        (bin_dir / name).write_text(body, encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    return bin_dir


def _env(tree: Path, system: str, running: bool = False) -> dict[str, str]:
    env = dict(os.environ)
    env.update(HOME=str(tree.parent / "home"), PATH=f"{_bin(tree, system, running)}:{os.environ['PATH']}")
    env.pop("XDG_CACHE_HOME", None)
    return env


def _icon_path(tree: Path, system: str) -> Path:
    home = tree.parent / "home"
    return home / "Applications" / "Seisa.app" if system == "Darwin" else home / ".local" / "share" / "applications" / "seisa.desktop"


def _make_icon(tree: Path, system: str, project: str | None, managed: bool = True) -> Path:
    """An icon as Seisa makes it (SeisaManaged / X-Seisa-Managed plus the project folder), or a foreign one."""
    target = _icon_path(tree, system)
    if system == "Darwin":
        (target / "Contents").mkdir(parents=True)
        info = {"CFBundleName": "Seisa"}
        if managed:
            info.update(SeisaManaged=True, SeisaProject=project)
        (target / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
    else:
        target.parent.mkdir(parents=True)
        lines = ["[Desktop Entry]", "Type=Application", "Name=Seisa"]
        if managed:
            lines += ["X-Seisa-Managed=true", f"X-Seisa-Project={project}"]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _make_venv(tree: Path) -> None:
    bin_dir = tree / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    (bin_dir / "python").chmod(0o755)
    (tree / "backend" / "__pycache__").mkdir()
    (tree / "backend" / "__pycache__" / "x.pyc").write_bytes(b"")


def _make_data(tree: Path) -> None:
    for folder in ("data", "logs"):
        (tree / folder / "history").mkdir(parents=True)
        (tree / folder / ".gitkeep").write_text("", encoding="utf-8")
    (tree / "data" / "history" / "entry.json").write_text('{"raw": "Received: from x"}', encoding="utf-8")
    (tree / "logs" / "seisa.log").write_text("line\n", encoding="utf-8")
    (tree / ".env").write_text("EXAMPLE_API_KEY=my-own-value\n", encoding="utf-8")


def _full(tree: Path, system: str) -> Path:
    _make_venv(tree)
    _make_data(tree)
    return _make_icon(tree, system, str(tree.resolve()))


def _run_plain(tree: Path, system: str, *args: str, running: bool = False) -> subprocess.CompletedProcess[str]:
    """No terminal: stdin is empty and the output goes to a pipe, as when started from another program."""
    return subprocess.run(
        ["/bin/bash", "uninstall.sh", *args], cwd=tree, env=_env(tree, system, running),
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60, check=False,
    )


def _run_tty(tree: Path, system: str, answers: list[str], *args: str, running: bool = False) -> tuple[int, str]:
    """Runs the script in a pseudo-terminal and types the answers, one line each."""
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        ["/bin/bash", "uninstall.sh", *args], cwd=tree, env=_env(tree, system, running),
        stdin=slave, stdout=slave, stderr=slave, close_fds=True,
    )
    os.close(slave)
    os.write(master, "".join(a + "\n" for a in answers).encode("utf-8"))
    output = b""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], 0.2)
        if ready:
            try:
                chunk = os.read(master, 4096)
            except OSError:  # Linux: the child closed the terminal
                break
            if not chunk:
                break
            output += chunk
        elif proc.poll() is not None:
            break
    os.close(master)
    code = proc.wait(timeout=10)
    return code, output.decode("utf-8", "replace").replace("\r\n", "\n")


def _untouched(tree: Path, system: str) -> None:
    assert (tree / ".venv" / "bin" / "python").exists()
    assert (tree / "data" / "history" / "entry.json").exists()
    assert (tree / "logs" / "seisa.log").exists()
    assert (tree / ".env").read_text(encoding="utf-8") == "EXAMPLE_API_KEY=my-own-value\n"
    assert _icon_path(tree, system).exists()


def _program_files_stay(tree: Path) -> None:
    for name in ("install.sh", "seisa.sh", "uninstall.sh", "backend/desktop_icon.py", "data/.gitkeep", "logs/.gitkeep"):
        assert (tree / name).exists(), name


@pytest.mark.parametrize("system", SYSTEMS)
def test_without_a_terminal_it_only_shows_a_preview(tree, system):
    icon = _full(tree, system)
    result = _run_plain(tree, system)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "only a preview" in result.stdout
    assert f"Would remove {icon}" in result.stdout
    assert "Would delete .venv" in result.stdout
    assert "- .env: your API keys" in result.stdout
    assert "- data/: 1 files" in result.stdout
    assert "This was a preview; nothing was deleted." in result.stdout
    _untouched(tree, system)


def test_dry_run_in_a_terminal_asks_nothing_and_deletes_nothing(tree):
    _full(tree, "Linux")
    code, out = _run_tty(tree, "Linux", ["y", "y", "y", "DELETE"], "--dry-run")
    assert code == 0, out
    assert "[y/N]" not in out
    assert "This was a preview; nothing was deleted." in out
    _untouched(tree, "Linux")


@pytest.mark.parametrize("system", SYSTEMS)
def test_yes_to_everything_with_a_backup(tree, system):
    icon = _full(tree, system)
    code, out = _run_tty(tree, system, ["y", "y", "y", "DELETE"])
    assert code == 0, out
    assert not icon.exists()
    assert not (tree / ".venv").exists()
    assert not (tree / "backend" / "__pycache__").exists()
    assert not (tree / ".env").exists()
    assert sorted(p.name for p in (tree / "data").iterdir()) == [".gitkeep"]
    assert sorted(p.name for p in (tree / "logs").iterdir()) == [".gitkeep"]
    _program_files_stay(tree)

    backups = list((tree.parent / "home").glob("seisa-backup-*.tar.gz"))
    assert len(backups) == 1, out
    assert stat.S_IMODE(backups[0].stat().st_mode) == 0o600
    with tarfile.open(backups[0]) as archive:
        names = archive.getnames()
        assert ".env" in names
        assert "data/history/entry.json" in names
        assert "logs/seisa.log" in names
        assert archive.extractfile("data/history/entry.json").read() == b'{"raw": "Received: from x"}'
    assert "rm -r " in out  # the folder itself is only named, never deleted


def test_enter_everywhere_keeps_everything(tree):
    _full(tree, "Darwin")
    code, out = _run_tty(tree, "Darwin", ["", "", "", ""])
    assert code == 0, out
    assert out.count("Kept.") == 3
    _untouched(tree, "Darwin")
    assert not list((tree.parent / "home").glob("seisa-backup-*"))


@pytest.mark.parametrize("word", ["delete", "yes", "y", "DELET"])
def test_only_the_exact_word_deletes_the_data(tree, word):
    _make_data(tree)
    code, out = _run_tty(tree, "Linux", ["n", word])
    assert code == 0, out
    assert (tree / ".env").exists()
    assert (tree / "data" / "history" / "entry.json").exists()
    assert (tree / "logs" / "seisa.log").exists()


def test_the_polish_word_deletes_the_data_too(tree):
    _make_data(tree)
    code, out = _run_tty(tree, "Linux", ["n", "USUŃ"])
    assert code == 0, out
    assert not (tree / ".env").exists()
    assert not (tree / "data" / "history").exists()


@pytest.mark.parametrize("system", SYSTEMS)
def test_an_icon_without_our_marker_is_never_removed(tree, system):
    icon = _make_icon(tree, system, None, managed=False)
    code, out = _run_tty(tree, system, ["y", "y"])
    assert code == 0, out
    assert icon.exists()
    assert "was not made by Seisa, so it stays" in out


@pytest.mark.parametrize("system", SYSTEMS)
def test_the_icon_of_another_seisa_folder_stays(tree, system):
    other = tree.parent / "other-seisa"
    other.mkdir()
    (other / "seisa-launcher.sh").write_text("# stand-in\n", encoding="utf-8")
    icon = _make_icon(tree, system, str(other))
    code, out = _run_tty(tree, system, ["y"])
    assert code == 0, out
    assert icon.exists()
    assert f"belongs to the Seisa in {other}" in out


@pytest.mark.parametrize("system", SYSTEMS)
def test_the_icon_of_a_vanished_seisa_folder_is_offered(tree, system):
    icon = _make_icon(tree, system, str(tree.parent / "gone"))
    code, out = _run_tty(tree, system, ["y"])
    assert code == 0, out
    assert not icon.exists()


def test_a_linked_icon_is_never_followed(tree):
    real = tree.parent / "elsewhere.desktop"
    real.write_text("[Desktop Entry]\nX-Seisa-Managed=true\nX-Seisa-Project=" + str(tree.resolve()) + "\n", encoding="utf-8")
    link = _icon_path(tree, "Linux")
    link.parent.mkdir(parents=True)
    link.symlink_to(real)
    code, out = _run_tty(tree, "Linux", ["y"])
    assert code == 0, out
    assert link.is_symlink()
    assert real.exists()


def test_a_running_seisa_stops_the_real_run(tree):
    _full(tree, "Linux")
    code, out = _run_tty(tree, "Linux", ["y", "y", "y", "DELETE"], running=True)
    assert code == 1
    assert "Seisa is running. Stop it first" in out
    _untouched(tree, "Linux")


def test_linked_folders_are_left_alone(tree):
    outside = tree.parent / "my-data"
    (outside / "history").mkdir(parents=True)
    (outside / "history" / "entry.json").write_text("{}", encoding="utf-8")
    (tree / "data").symlink_to(outside)
    venv_target = tree.parent / "shared-venv"
    venv_target.mkdir()
    (tree / ".venv").symlink_to(venv_target)
    code, out = _run_tty(tree, "Linux", ["y", "y", "DELETE"])
    assert code == 0, out
    assert (outside / "history" / "entry.json").exists()
    assert venv_target.is_dir()
    assert "Links to another place stay (remove them yourself if you want): data" in out
    assert ".venv is a link to another place" in out


def test_without_any_python_the_icon_is_only_named(tree):
    icon = _make_icon(tree, "Linux", str(tree.resolve()))
    env = _env(tree, "Linux")
    bin_dir = tree.parent / "bin"
    (bin_dir / "python3").unlink()
    for tool in ("du", "cut", "find", "head", "wc", "tr", "rm", "tar", "date"):  # what the script runs, and no Python
        found = shutil.which(tool)
        assert found, tool
        (bin_dir / tool).symlink_to(found)
    env["PATH"] = str(bin_dir)
    result = subprocess.run(
        ["/bin/bash", "uninstall.sh"], cwd=tree, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "cannot check that Seisa made it" in result.stdout
    assert icon.exists()


def test_outside_a_seisa_folder_it_refuses(tree):
    (tree / "backend" / "desktop_icon.py").unlink()
    _make_data(tree)
    code, out = _run_tty(tree, "Linux", ["y", "DELETE"])
    assert code == 1
    assert "must stay in the Seisa folder" in out
    assert (tree / ".env").exists()


def test_other_systems_are_refused(tree):
    result = _run_plain(tree, "FreeBSD")
    assert result.returncode == 1
    assert "macOS and Linux only" in result.stderr


def test_help_from_another_folder(tree):
    result = subprocess.run(
        ["/bin/bash", "seisa/uninstall.sh", "--help"], cwd=tree.parent, env=_env(tree, "Linux"),
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "bash uninstall.sh [--dry-run]" in result.stdout


def test_unknown_option(tree):
    result = _run_plain(tree, "Linux", "--bogus")
    assert result.returncode == 2
    assert "Unknown option" in result.stderr
