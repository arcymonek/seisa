"""Forms found in the DOM of a scanned page (urlscan.io serves the rendered DOM at /dom/{uuid}/).

The page is untrusted: it is only parsed as text with the standard-library HTML parser - nothing is fetched from it
and nothing is executed. The result is a short list of facts about the forms; the one that matters most for phishing is a
password field whose form posts to another domain than the page itself."""
from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

MAX_FORMS = 20
MAX_FIELDS = 12
MAX_DOM_CHARS = 2_000_000


class _FormCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[dict] = []
        self._open: dict | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {k: (v or "") for k, v in attrs}
        if tag == "form":
            self._open = {"action": attributes.get("action", "").strip(), "method": (attributes.get("method") or "get").lower(), "fields": [], "password": False}
            self.forms.append(self._open)
        elif tag in ("input", "textarea", "select") and self._open is not None:
            kind = (attributes.get("type") or ("text" if tag == "input" else tag)).lower()
            if kind == "password":
                self._open["password"] = True
            if kind != "hidden" and len(self._open["fields"]) < MAX_FIELDS:
                name = attributes.get("name") or attributes.get("id") or ""
                self._open["fields"].append(f"{kind}:{name[:40]}" if name else kind)

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._open = None


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def extract_forms(dom: str, page_url: str, page_domain: str | None) -> list[dict]:
    """Facts about the forms of a page: where each posts, its method, its (non-hidden) fields, whether it asks for a
    password and whether it posts to another domain than the page."""
    collector = _FormCollector()
    try:
        collector.feed(dom[:MAX_DOM_CHARS])
        collector.close()
    except Exception:  # a malformed page must never break the report
        pass
    page_host = (page_domain or _host(page_url)).lower()
    forms: list[dict] = []
    for raw in collector.forms[:MAX_FORMS]:
        action_url = urljoin(page_url, raw["action"]) if raw["action"] else page_url
        scheme = urlsplit(action_url).scheme.lower() if action_url else ""
        target = _host(action_url)
        external = bool(target) and bool(page_host) and target != page_host and not target.endswith("." + page_host) and not page_host.endswith("." + target)
        forms.append({
            "action": action_url if scheme in ("http", "https") else (raw["action"] or "")[:200],
            "method": raw["method"],
            "fields": raw["fields"],
            "password": raw["password"],
            "external": external,
            "insecure": scheme == "http" and raw["password"],
        })
    return forms
