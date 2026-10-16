"""Backend translations: catalogs in backend/locales/<lang>.json, language of the current request in a ContextVar.

The frontend sends its language in the X-Seisa-Lang header; LanguageMiddleware (main.py) stores it here, so code
deep inside the call chain (e-mail forensics, scoring, reports) can call t(<key>, name=value) without threading a
`lang` argument through every function. Values are plain text (never HTML). Plural forms use the keys
<key>_one / _few / _many / _other (see tn()).
"""
from __future__ import annotations

import json
import re
from contextvars import ContextVar
from pathlib import Path

SUPPORTED = ("pl", "en")
DEFAULT_LANG = "en"

# Names of the UI languages as the LLM prompts spell them (the prompts are English; they say which language to answer in).
LANGUAGE_NAMES = {"pl": "Polish", "en": "English"}

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"
_catalogs: dict[str, dict[str, str]] = {
    lang: json.loads((_LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    for lang in SUPPORTED
    if (_LOCALES_DIR / f"{lang}.json").exists()
}
_current: ContextVar[str] = ContextVar("seisa_lang", default=DEFAULT_LANG)
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def normalize_lang(value: str | None) -> str:
    value = (value or "").strip().lower()[:2]
    return value if value in SUPPORTED else DEFAULT_LANG


def set_lang(value: str | None):
    """Sets the language of the current request context; returns the token for reset_lang()."""
    return _current.set(normalize_lang(value))


def reset_lang(token) -> None:
    _current.reset(token)


def current_lang() -> str:
    return _current.get()


def _lookup(lang: str, key: str) -> str | None:
    return _catalogs.get(lang, {}).get(key)


def t(key: str, lang: str | None = None, **params) -> str:
    """Translated text for `key` in the request language (or `lang`), falling back to English, then to the key."""
    lang = lang or _current.get()
    text = _lookup(lang, key)
    if text is None:
        text = _lookup(DEFAULT_LANG, key)
    if text is None:
        return key
    if not params:
        return text
    return _PLACEHOLDER.sub(lambda m: str(params[m.group(1)]) if m.group(1) in params else m.group(0), text)


def plural_category(lang: str, n: int) -> str:
    if lang == "pl":
        if n == 1:
            return "one"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return "few"
        return "many"
    return "one" if n == 1 else "other"


def tn(key: str, n: int, lang: str | None = None, **params) -> str:
    """Plural-aware translation: picks <key>_one/_few/_many/_other for n; {n} is filled in automatically.

    Not used by any message yet, kept on purpose: check_i18n.py already validates plural forms in the backend
    catalogs, so the first "{n} items" message only needs the catalog entries."""
    lang = lang or _current.get()
    category = plural_category(lang, n)
    for suffix in (f"_{category}", "_other"):
        if _lookup(lang, key + suffix) is not None or _lookup(DEFAULT_LANG, key + suffix) is not None:
            return t(key + suffix, lang, n=n, **params)
    return key
