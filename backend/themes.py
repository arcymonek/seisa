"""Colour themes: JSON files in frontend/themes/ turned into CSS.

A theme file holds colours only (a fixed set of keys, each value #rrggbb, plus an optional two-colour header stripe),
never CSS. The CSS is generated here from validated values, so a theme dropped into the folder (or sent in a pull
request) cannot carry url(), @import or any other rule: everything that reaches the stylesheet is a whitelisted key,
a hex colour, a checked id or 'dark'/'light'.
A file that fails any check is skipped and logged (the reason, never the content).
"""
from __future__ import annotations

import json
import logging
import re

from backend.config import FRONTEND_DIR

logger = logging.getLogger("app")

THEMES_DIR = FRONTEND_DIR / "themes"
MAX_FILE_BYTES = 8 * 1024
MAX_THEMES = 24
BASES = ("dark", "light")  # becomes the CSS color-scheme (form controls, scrollbars)
LANGS = ("en", "pl")
COLOR_KEYS = (
    "bg", "bg-raised", "bg-inset", "hair", "hair-soft",
    "text", "text-strong", "muted",
    "accent", "on-accent", "info",
    "fail", "fail-bg", "pass", "pass-bg", "warn", "warn-bg", "on-warn",
    "hit-bg", "focus", "tooltip-bg", "shadow", "cite-hover-bg",
)
STRIPE_KEYS = ("top", "bottom")  # optional two-tone bar under the page header (top half, bottom half), colours only
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_NAME_CHARS = re.compile(r"^[^\x00-\x1f\x7f<>&\"'`]{1,40}$")


class ThemeError(ValueError):
    pass


def validate_theme(data: object, stem: str) -> dict:
    """Return the normalised theme or raise ThemeError (the message names the problem, never echoes the content)."""
    if not isinstance(data, dict):
        raise ThemeError("not a JSON object")
    if set(data) - {"id", "name", "base", "order", "colors", "stripe"}:
        raise ThemeError("unknown top-level key")
    theme_id = data.get("id")
    if not isinstance(theme_id, str) or not _ID.match(theme_id):
        raise ThemeError("bad id")
    if theme_id != stem:
        raise ThemeError("id differs from the file name")
    if data.get("base") not in BASES:
        raise ThemeError("base must be dark or light")
    order = data.get("order", 100)
    if isinstance(order, bool) or not isinstance(order, int) or not 0 <= order <= 1000:
        raise ThemeError("order must be an integer 0-1000")
    names = data.get("name")
    if not isinstance(names, dict) or not names or set(names) - set(LANGS):
        raise ThemeError("name must map en/pl to text")
    for value in names.values():
        if not isinstance(value, str) or not _NAME_CHARS.match(value):
            raise ThemeError("bad name text")
    colors = data.get("colors")
    if not isinstance(colors, dict) or set(colors) != set(COLOR_KEYS):
        raise ThemeError("colors must be exactly the required set of keys")
    for value in colors.values():
        if not isinstance(value, str) or not _HEX.match(value):
            raise ThemeError("every colour must be #rrggbb")
    stripe = data.get("stripe")
    if stripe is not None:
        if not isinstance(stripe, dict) or set(stripe) != set(STRIPE_KEYS):
            raise ThemeError("stripe must be exactly top and bottom")
        for value in stripe.values():
            if not isinstance(value, str) or not _HEX.match(value):
                raise ThemeError("every stripe colour must be #rrggbb")
    fallback = names.get("en") or next(iter(names.values()))
    out = {
        "id": theme_id,
        "name": {lang: names.get(lang, fallback) for lang in LANGS},
        "base": data["base"],
        "order": order,
        "colors": {key: colors[key].lower() for key in COLOR_KEYS},
    }
    if stripe is not None:
        out["stripe"] = {key: stripe[key].lower() for key in STRIPE_KEYS}
    return out


def load_themes() -> list[dict]:
    """All valid themes, sorted by (order, id). Read from disk on every call: a new file shows up after a reload."""
    themes: list[dict] = []
    if not THEMES_DIR.is_dir():
        return themes
    for path in sorted(THEMES_DIR.glob("*.json"))[:MAX_THEMES]:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                raise ThemeError("not a regular small file")
            themes.append(validate_theme(json.loads(path.read_text(encoding="utf-8")), path.stem))
        except (OSError, ValueError) as exc:  # ThemeError and json.JSONDecodeError are ValueErrors
            logger.warning(f"theme {path.name} skipped: {exc}")
    return sorted(themes, key=lambda th: (th["order"], th["id"]))


def render_css(themes: list[dict]) -> str:
    blocks = []
    for th in themes:
        body = "".join(f"--{key}:{value};" for key, value in th["colors"].items())
        if "stripe" in th:  # themes without it leave the variables unset, and the stylesheet then paints nothing
            body += "".join(f"--stripe-{key}:{th['stripe'][key]};" for key in STRIPE_KEYS)
        # which logo variant is shown follows the base: the dark badge on a dark theme, the accent-coloured shape on a light one
        dark_logo, light_logo = ("inline", "none") if th["base"] == "dark" else ("none", "inline")
        blocks.append(
            f':root[data-theme="{th["id"]}"]{{color-scheme:{th["base"]};'
            f"--logo-dark-display:{dark_logo};--logo-light-display:{light_logo};{body}}}"
        )
    return "\n".join(blocks) + "\n"


def public_list(themes: list[dict]) -> list[dict]:
    """What the footer switch needs: no colours, only id, names, base and order."""
    return [{k: th[k] for k in ("id", "name", "base", "order")} for th in themes]
