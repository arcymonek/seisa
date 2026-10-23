"""install.sh: the installer builds .venv, installs the libraries, keeps an existing .env and stops with a clear
message when Python is missing, too old or the libraries cannot be fetched.

Every run happens in a throw-away copy of the minimal folder layout and offline: pip gets only a hand-made wheel
(PIP_NO_INDEX plus PIP_FIND_LINKS), so no test touches the network or the real project folder. The expected messages
and file modes come from the script's documented behaviour (README, docs/OPERATIONS.md), not from running it."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow  # every test builds a virtual environment or starts the script in a child process

SCRIPT = Path(__file__).resolve().parent.parent / "install.sh"


def _fake_wheel(directory: Path) -> None:
    """A minimal 'uvicorn' wheel whose console script gives the installed .venv/bin/uvicorn the installer checks for."""
    directory.mkdir(parents=True, exist_ok=True)
    info = "uvicorn-0.0.0.dist-info"
    with zipfile.ZipFile(directory / "uvicorn-0.0.0-py3-none-any.whl", "w") as wheel:
        wheel.writestr("uvicorn/__init__.py", "def main():\n    pass\n")
        wheel.writestr(f"{info}/METADATA", "Metadata-Version: 2.1\nName: uvicorn\nVersion: 0.0.0\n")
        wheel.writestr(f"{info}/WHEEL", "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        wheel.writestr(f"{info}/entry_points.txt", "[console_scripts]\nuvicorn = uvicorn:main\n")
        wheel.writestr(f"{info}/RECORD", "")


@pytest.fixture
def tree(tmp_path):
    folder = tmp_path / "seisa"
    (folder / "backend").mkdir(parents=True)
    shutil.copy(SCRIPT, folder / "install.sh")
    (folder / "requirements.lock").write_text("uvicorn==0.0.0\n", encoding="utf-8")
    (folder / "requirements.txt").write_text("uvicorn\n", encoding="utf-8")
    (folder / ".env.example").write_text("EXAMPLE_API_KEY=\n", encoding="utf-8")
    _fake_wheel(tmp_path / "wheels")
    return folder


def _env(tree: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "SEISA_PYTHON"}
    env.update(
        HOME=str(tree.parent),
        PIP_NO_INDEX="1",
        PIP_FIND_LINKS=str(tree.parent / "wheels"),
        PIP_CACHE_DIR=str(tree.parent / "pip-cache"),
        PIP_DISABLE_PIP_VERSION_CHECK="1",
        SEISA_PYTHON=sys.executable,
    )
    env.update(extra)
    return env


def _run(tree: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", "install.sh", *args], cwd=tree, env=env or _env(tree), capture_output=True, text=True, timeout=180, check=False
    )


def _bare_path(tmp_path: Path, extra: dict[str, str] | None = None) -> str:
    """A PATH holding only what the script itself needs, so that no real Python can be found on it."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("uname", "cp", "chmod", "rm"):
        found = shutil.which(tool)
        assert found, tool
        (bin_dir / tool).symlink_to(found)
    for name, body in (extra or {}).items():
        program = bin_dir / name
        program.write_text(body, encoding="utf-8")
        program.chmod(0o755)
    return str(bin_dir)


def test_fresh_install_then_rerun_keeps_env(tree):
    first = _run(tree, "--no-icon")
    assert first.returncode == 0, first.stdout + first.stderr
    assert "Seisa is installed." in first.stdout
    assert (tree / ".venv" / "bin" / "uvicorn").exists()
    env_file = tree / ".env"
    assert env_file.read_text(encoding="utf-8") == "EXAMPLE_API_KEY=\n"
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600

    # The user fills in a key and (by accident) loosens the mode; a second run must keep the key and tighten the mode.
    env_file.write_text("EXAMPLE_API_KEY=my-own-value\n", encoding="utf-8")
    env_file.chmod(0o644)
    second = _run(tree, "--no-icon")
    assert second.returncode == 0, second.stdout + second.stderr
    assert "Using the existing .venv." in second.stdout
    assert env_file.read_text(encoding="utf-8") == "EXAMPLE_API_KEY=my-own-value\n"
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600


def test_no_python_on_the_path(tree, tmp_path):
    env = _env(tree, PATH=_bare_path(tmp_path))
    del env["SEISA_PYTHON"]
    result = _run(tree, "--no-icon", env=env)
    assert result.returncode == 1
    assert "Seisa was not installed." in result.stderr
    assert "Python 3.11 or newer" in result.stderr
    assert not (tree / ".venv").exists()
    assert not (tree / ".env").exists()


def test_python_too_old_is_named(tree, tmp_path):
    # Answers the version check with "no" and the version question with 3.9, like an old system Python would.
    fake = '#!/bin/sh\ncase "$2" in *"print("*) echo 3.9; exit 0 ;; *) exit 1 ;; esac\n'
    env = _env(tree, PATH=_bare_path(tmp_path, {"python3": fake}))
    del env["SEISA_PYTHON"]
    result = _run(tree, "--no-icon", env=env)
    assert result.returncode == 1
    assert "Found only Python 3.9" in result.stderr
    assert not (tree / ".venv").exists()


def test_given_python_that_is_too_old_is_refused(tree, tmp_path):
    fake = tmp_path / "old-python"
    fake.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    fake.chmod(0o755)
    result = _run(tree, "--no-icon", env=_env(tree, SEISA_PYTHON=str(fake)))
    assert result.returncode == 1
    assert "SEISA_PYTHON" in result.stderr


def test_unusable_venv_is_left_alone(tree):
    (tree / ".venv").mkdir()
    result = _run(tree, "--no-icon")
    assert result.returncode == 1
    assert "Rename or delete the folder .venv" in result.stderr
    assert (tree / ".venv").is_dir()
    assert not (tree / ".env").exists()


def test_libraries_that_cannot_be_installed(tree):
    (tree / "requirements.lock").write_text("no-such-package-seisa-test==1.0\n", encoding="utf-8")
    (tree / "requirements.txt").write_text("no-such-package-seisa-test\n", encoding="utf-8")
    result = _run(tree, "--no-icon")
    assert result.returncode == 1
    assert "trying requirements.txt" in result.stdout
    assert "The libraries could not be installed" in result.stderr
    assert not (tree / ".env").exists()


def test_falls_back_to_requirements_txt(tree):
    (tree / "requirements.lock").write_text("no-such-package-seisa-test==1.0\n", encoding="utf-8")
    result = _run(tree, "--no-icon")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "trying requirements.txt" in result.stdout
    assert (tree / ".venv" / "bin" / "uvicorn").exists()


def test_icon_failure_does_not_stop_the_installation(tree):
    # The minimal tree has no backend.desktop_icon module, so the icon step fails the way a missing file would.
    result = _run(tree, "--icon")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "The icon was not added" in result.stdout
    assert "Seisa is installed." in result.stdout


def test_help_from_another_folder(tree):
    result = subprocess.run(
        ["/bin/bash", "seisa/install.sh", "--help"], cwd=tree.parent, env=_env(tree), capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "bash install.sh [--icon | --no-icon]" in result.stdout
    assert not (tree / ".venv").exists()


def test_unknown_option(tree):
    result = _run(tree, "--bogus")
    assert result.returncode == 2
    assert "Unknown option" in result.stderr
