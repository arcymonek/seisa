"""Editing the API keys in the .env file from the Info tab: which settings can be changed, what a value may look like,
and an atomic rewrite of the file that keeps everything else in it. Nothing here reads a key out (the status only says
whether one is set) and no error text ever contains a value - the global error handler logs exception texts.
"""
from __future__ import annotations

import contextlib
import os
import re
import threading

import backend.config as cfg
from backend.api_limits import load_api_usage, save_api_usage
from backend.config import Settings, settings
from backend.i18n import t

# Every field of Settings can be edited; the list comes from the class so it cannot drift from .env.example.
EDITABLE = tuple(Settings.model_fields)
SECRET_FIELDS = tuple(f for f in EDITABLE if f.endswith("_api_key"))

# Only characters that real keys and model slugs ("vendor/model:free") are made of. The python-dotenv reader turns
# "$", " #", quotes and surrounding spaces into something else even inside quotes, and a newline would add a variable.
VALUE_RE = re.compile(r"[A-Za-z0-9._~+/=:-]{1,512}")

_LOCK = threading.Lock()


class EnvFileError(Exception):
    """A refused change; `message` is already translated and never contains a value."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _default(field: str) -> str:
    return Settings.model_fields[field].default


def _from_environment(field: str) -> bool:
    return field.upper() in os.environ


def _service(field: str) -> str:
    return field.removesuffix("_api_key").removesuffix("_model")


def keys_status() -> list[dict]:
    """One row per editable setting: whether it is set, whether the environment (not the file) provides it and, for the
    model name only (it is not a secret), its value."""
    rows = []
    for field in EDITABLE:
        secret = field in SECRET_FIELDS
        value = getattr(settings, field)
        row = {"field": field, "env_name": field.upper(), "secret": secret,
               "set": bool(value) if secret else value != _default(field), "from_env": _from_environment(field)}
        if not secret:
            row["value"] = value
        rows.append(row)
    return rows


def _check(updates: dict[str, str | None]) -> None:
    for field, value in updates.items():
        if field not in EDITABLE:
            raise EnvFileError(t("settings.unknown_field"))
        if _from_environment(field):
            raise EnvFileError(t("settings.from_environment", name=field.upper()))
        if value is not None and not VALUE_RE.fullmatch(value):
            raise EnvFileError(t("settings.bad_value", name=field.upper()))


def _rewrite(lines: list[str], field: str, value: str | None) -> list[str]:
    """Replaces every `KEY=` / `export KEY=` line of the field by one line at the place of the first (or at the end)."""
    key = field.upper()
    pattern = re.compile(rf"^\s*(?:export\s+)?{re.escape(key)}\s*=")
    new = f"{key}={value or ''}"
    out: list[str] = []
    placed = False
    for line in lines:
        if pattern.match(line):
            if not placed:
                out.append(new)
                placed = True
            continue
        out.append(line)
    if not placed:
        out.append(new)
    return out


def _write_atomic(path, text: str) -> None:
    """Temporary file next to the target, created 0600 from the start, then moved over it."""
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    os.chmod(path, 0o600)


def write(updates: dict[str, str | None]) -> None:
    """Sets (a value) or removes (None) settings in the .env file and in the running `settings`, so the change works
    without a restart. All changes are checked first; a refused one changes nothing."""
    _check(updates)
    if not updates:
        return
    with _LOCK:
        path = cfg.ENV_FILE
        if path.is_symlink():
            raise EnvFileError(t("settings.symlink"))
        try:
            if path.exists():
                text = path.read_text(encoding="utf-8")
            else:
                example = path.with_name(".env.example")
                text = example.read_text(encoding="utf-8") if example.is_file() else ""
            lines = text.splitlines()
            for field, value in updates.items():
                lines = _rewrite(lines, field, value)
            _write_atomic(path, "\n".join(lines) + "\n")
        except (OSError, UnicodeDecodeError) as exc:
            raise EnvFileError(t("settings.write_failed", error=type(exc).__name__)) from exc
        for field, value in updates.items():
            setattr(settings, field, value if value else _default(field))
        _forget_limits(updates)


def _forget_limits(updates: dict[str, str | None]) -> None:
    """The stored quota of a service belongs to the account of the old key; drop it when the key changes."""
    services = {_service(f) for f in updates if f in SECRET_FIELDS}
    if not services:
        return
    usage = load_api_usage()
    live = usage.get("live") or {}
    if any(s in live for s in services):
        for s in services:
            live.pop(s, None)
        save_api_usage(usage)
