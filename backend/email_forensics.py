"""Deterministyczna analiza źródła e-maila dla zakładki "Email".

Wszystko tutaj jest liczone lokalnie, bez sieci i bez LLM: oś czasu, konwersje epoch, długości bh=,
drzewo MIME, tabela linków, ukryta treść itd. Wynik trafia i do interfejsu (od razu), i do promptu LLM
jako "fakty obliczone przez kod", żeby model tłumaczył zamiast liczyć.

Wiadomość jest niezaufanym wejściem: nic tu nie otwiera linków, nie pobiera zasobów ani nie wykonuje treści.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from datetime import datetime, timezone
from email import message_from_string
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlsplit

from backend.email_parser import _parse_received_header

MAX_LLM_SOURCE_CHARS = 120_000
MAX_DECODED_TEXT_CHARS = 60_000

VALID_CTE = {"7bit", "8bit", "binary", "quoted-printable", "base64"}
SINGLE_INSTANCE_HEADERS = {
    "from", "to", "subject", "date", "message-id", "reply-to", "sender", "mime-version",
    "content-type", "content-transfer-encoding", "content-length",
}
TZ_ABBR = {
    "UTC": 0, "GMT": 0, "Z": 0, "PDT": -700, "PST": -800, "MDT": -600, "MST": -700, "CDT": -500, "CST": -600,
    "EDT": -400, "EST": -500, "CET": 100, "CEST": 200, "BST": 100, "EET": 200, "EEST": 300, "JST": 900, "IST": 530,
}
TWO_LEVEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "com.au", "net.au", "com.pl", "net.pl", "org.pl", "co.jp", "com.br", "co.nz",
    "com.tr", "co.za", "com.cn", "co.in", "com.mx", "com.ar", "co.kr",
}
ABUSED_HOSTS = (
    "storage.googleapis.com", "docs.google.com", "drive.google.com", "forms.gle", "sites.google.com",
    "firebaseapp.com", "web.app", "pages.dev", "workers.dev", "r2.dev", "github.io", "notion.site",
    "s3.amazonaws.com", "blob.core.windows.net", "sharepoint.com", "onedrive.live.com", "dropbox.com",
    "cdn.discordapp.com", "t.me", "herokuapp.com", "netlify.app", "vercel.app", "weebly.com", "wixsite.com",
)
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "rebrand.ly", "cutt.ly", "shorturl.at"}
RISKY_EXTENSIONS = {
    "exe", "scr", "bat", "cmd", "com", "js", "jse", "vbs", "vbe", "wsf", "jar", "lnk", "iso", "img", "hta", "ps1",
    "msi", "dll", "docm", "xlsm", "pptm", "html", "htm", "svg", "one", "zip", "rar", "7z", "ace",
}
DOUBLE_EXT_DISPLAY = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "jpg", "jpeg", "png", "gif", "zip"}
PLACEHOLDER_RES = [
    re.compile(r"\{\{[^}]{1,40}\}\}"), re.compile(r"@@\w{2,30}@@"), re.compile(r"%%\w{2,30}%%"),
    re.compile(r"\[\[\w{2,30}\]\]"), re.compile(r"\$\{\w{2,30}\}"), re.compile(r"\{%\s*\w+[^%]{0,30}%\}"),
]
KNOWN_HTML_TAGS = set(
    "a abbr address area article aside audio b base bdi bdo blockquote body br button canvas caption center cite code "
    "col colgroup data datalist dd del details dfn dialog div dl dt em embed fieldset figcaption figure font footer "
    "form h1 h2 h3 h4 h5 h6 head header hr html i iframe img input ins kbd label legend li link main map mark meta "
    "meter nav noscript object ol optgroup option output p param picture pre progress q rp rt ruby s samp script "
    "section select small source span strike strong style sub summary sup table tbody td template textarea tfoot th "
    "thead time title tr track u ul var video wbr o:p v:shape xml".split()
)
VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "area", "base", "col", "embed", "param", "source", "track", "wbr"}
HIDDEN_STYLE_RES = {
    "display:none": re.compile(r"display\s*:\s*none"),
    "visibility:hidden": re.compile(r"visibility\s*:\s*hidden"),
    "font-size:0/1px": re.compile(r"font-size\s*:\s*[01](px|pt)?\s*(;|$|!)"),
    "opacity:0": re.compile(r"opacity\s*:\s*0(\.0+)?\s*(;|$|!)"),
    "max-height:0": re.compile(r"max-height\s*:\s*0"),
    "height:0+overflow:hidden": re.compile(r"(?<![-\w])height\s*:\s*0(px)?\s*(;|$|!)"),
    "width/max-width:0": re.compile(r"(max-)?width\s*:\s*0(px)?\s*(;|$|!)"),
}


# ---------------------------------------------------------------------------
# normalizacja i przygotowanie źródła
# ---------------------------------------------------------------------------

def decode_eml_bytes(data: bytes) -> str:
    """Bajty pliku .eml -> tekst: UTF-8, a gdy się nie da, windows-1252 (bajty nigdy nie giną)."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def normalize_source(raw: str) -> str:
    """Ujednolica źródło wklejone/wczytane z pliku: BOM, zakończenia linii, koperta mbox ("From ..."),
    puste linie na początku. Nie zmienia niczego wewnątrz nagłówków ani treści."""
    text = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    text = text.lstrip("\n")
    lines = text.split("\n", 1)
    if lines and re.match(r"^From \S+", lines[0]) and ":" not in lines[0].split(" ", 1)[0]:
        text = lines[1] if len(lines) > 1 else ""
    return text.lstrip("\n")


def _unfold(value: str) -> str:
    return re.sub(r"\n[ \t]+", " ", str(value)).strip()


def _b64_decode(lines: list[str]) -> bytes | None:
    try:
        return base64.b64decode("".join(l.strip() for l in lines), validate=False)
    except (binascii.Error, ValueError):
        return None


def prepare_for_llm(src: str, max_chars: int = MAX_LLM_SOURCE_CHARS) -> tuple[str, list[str]]:
    """Wersja źródła dla LLM: binarne załączniki base64 zastępowane znacznikiem (rozmiar + sha256), tekstowe
    części base64 dekodowane (model czyta je wprost), reszta bez zmian. Zwraca (tekst, notatki dla użytkownika)."""
    lines = src.split("\n")
    out: list[str] = []
    notes: list[str] = []
    boundaries: set[str] = set()

    def is_boundary(line: str) -> bool:
        s = line.rstrip()
        return any(s == "--" + b or s == "--" + b + "--" for b in boundaries)

    mode = "headers"
    hdrs: dict[str, str] = {}
    last_name: str | None = None
    capture: list[str] = []

    def finish_headers() -> None:
        ct = hdrs.get("content-type", "")
        for m in re.finditer(r'boundary\s*=\s*"?([^";\s]+)"?', ct, re.IGNORECASE):
            boundaries.add(m.group(1))

    def flush_capture(ctype: str, charset_hint: str) -> None:
        data = _b64_decode(capture)
        if data is None:
            out.extend(capture)
            return
        if ctype.startswith("text/"):
            charset = charset_hint or "utf-8"
            try:
                text = data.decode(charset, errors="replace")
            except LookupError:
                text = data.decode("utf-8", errors="replace")
            if len(text) > MAX_DECODED_TEXT_CHARS:
                text = text[:MAX_DECODED_TEXT_CHARS] + "\n...(obcięte)"
            out.append(f"[arcyAnalizer: poniżej treść części {ctype} zdekodowana z base64 (charset {charset})]")
            out.extend(text.split("\n"))
            out.append("[arcyAnalizer: koniec zdekodowanej części]")
            notes.append(f"zdekodowano część {ctype} z base64 ({len(data)} B)")
        else:
            digest = hashlib.sha256(data).hexdigest()
            out.append(f"[arcyAnalizer: pominięto treść base64 ({ctype or 'nieznany typ'}): {len(data)} bajtów po zdekodowaniu, sha256={digest}]")
            notes.append(f"pominięto binarną treść base64 {ctype or '?'} ({len(data)} B)")

    for line in lines:
        if mode == "capture":
            if is_boundary(line):
                flush_capture(hdrs.get("content-type", "").split(";")[0].strip().lower(),
                              (re.search(r"charset\s*=\s*\"?([\w.-]+)", hdrs.get("content-type", ""), re.IGNORECASE) or [None, ""])[1])
                capture = []
                out.append(line)
                mode, hdrs, last_name = "headers", {}, None
            else:
                capture.append(line)
            continue

        out.append(line)
        if mode == "headers":
            if line.strip() == "":
                finish_headers()
                if hdrs.get("content-transfer-encoding", "").strip().lower() == "base64" and \
                        not hdrs.get("content-type", "").lower().startswith("multipart/"):
                    mode = "capture"
                    capture = []
                else:
                    mode = "body"
            elif line[0] in " \t" and last_name:
                hdrs[last_name] += " " + line.strip()
            elif ":" in line:
                last_name = line.split(":", 1)[0].strip().lower()
                hdrs[last_name] = line.split(":", 1)[1].strip()
        elif mode == "body":
            if is_boundary(line):
                mode, hdrs, last_name = "headers", {}, None

    if mode == "capture" and capture:
        flush_capture(hdrs.get("content-type", "").split(";")[0].strip().lower(), "")

    text = "\n".join(out)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[arcyAnalizer: źródło obcięte do limitu]"
        notes.append(f"źródło obcięte do {max_chars} znaków (limit wysyłki do LLM)")
    return text, notes


# ---------------------------------------------------------------------------
# narzędzia pomocnicze
# ---------------------------------------------------------------------------

def registrable_domain(host: str | None) -> str | None:
    if not host:
        return None
    host = host.strip().strip(".").lower()
    if re.fullmatch(r"[\d.]+|[0-9a-f:]+", host) and (":" in host or host.count(".") == 3):
        return None  # adres IP
    labels = host.split(".")
    if len(labels) < 2:
        return host
    if ".".join(labels[-2:]) in TWO_LEVEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


# Rodziny domen jednego operatora poczty: Received/Authentication-Results tego samego operatora bywają pod różnymi domenami.
PROVIDER_FAMILIES = {
    "microsoft": {"microsoft.com", "outlook.com", "office365.com", "office.com", "hotmail.com", "live.com", "msn.com"},
    "google": {"google.com", "gmail.com", "googlemail.com"},
    "yahoo": {"yahoo.com", "yahoodns.net", "yahoo.co.jp"},
    "apple": {"icloud.com", "me.com", "apple.com"},
    "proton": {"proton.me", "protonmail.ch", "protonmail.com"},
}


def family(domain: str | None) -> str | None:
    """Klucz rodziny operatora dla domeny (nieznana domena = sama sobie rodziną)."""
    if not domain:
        return None
    for key, members in PROVIDER_FAMILIES.items():
        if domain in members:
            return key
    return domain


def _addr_domain(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    addr = parseaddr(value)[1] or (re.search(r"<([^>]+)>", value) or [None, value.strip()])[1]
    if addr and "@" in addr:
        dom = addr.rsplit("@", 1)[1].strip(" >").lower()
        return addr, dom
    return addr or None, None


def _url_host(url: str) -> str | None:
    try:
        return (urlsplit(url).hostname or "").lower() or None
    except ValueError:
        return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value.strip())
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _decode_words(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _tags(value: str) -> dict[str, str]:
    """Tagi DKIM/ARC 'k=v; k=v' -> dict (kolejne wystąpienia nie nadpisują pierwszego)."""
    out: dict[str, str] = {}
    for part in value.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out.setdefault(k.strip().lower(), re.sub(r"\s+", "", v))
    return out


def _fmt_utc(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC") if dt else None


# ---------------------------------------------------------------------------
# analiza HTML (ukryta treść, linki, elementy zdalne)
# ---------------------------------------------------------------------------

class _HtmlAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict] = []
        self.images: list[dict] = []
        self.hidden: list[dict] = []
        self.forms = self.scripts = self.iframes = self.objects = 0
        self.comment_count = self.comment_chars = 0
        self.comment_samples: list[str] = []
        self.wrapped_anchor = False
        self._stack: list[dict] = []
        self._anchor: dict | None = None

    def _hidden_techniques(self, attrs: dict) -> list[str]:
        style = (attrs.get("style") or "").lower()
        found = [name for name, rx in HIDDEN_STYLE_RES.items() if rx.search(style)]
        if "height:0+overflow:hidden" in found and "overflow" not in style:
            found.remove("height:0+overflow:hidden")
        if "hidden" in attrs:
            found.append("atrybut hidden")
        return found

    def handle_starttag(self, tag, attrs_list):
        attrs = {k: (v or "") for k, v in attrs_list}
        if tag == "form":
            self.forms += 1
        elif tag == "script":
            self.scripts += 1
        elif tag == "iframe":
            self.iframes += 1
        elif tag in ("object", "embed"):
            self.objects += 1
        elif tag == "img":
            src = attrs.get("src", "")
            w, h = attrs.get("width", "").strip(), attrs.get("height", "").strip()
            tiny = w in ("0", "1") or h in ("0", "1")
            self.images.append({
                "src_host": _url_host(src), "src": src[:200], "width": w, "height": h,
                "tracking_hint": bool(tiny or (urlsplit(src).query if src.startswith("http") else "")),
            })
        elif tag == "a":
            self._anchor = {"href": attrs.get("href", ""), "text": "", "inner_tags": 0,
                            "block": "display:block" in (attrs.get("style") or "").replace(" ", "").lower()}
        elif self._anchor is not None:
            self._anchor["inner_tags"] += 1

        if tag in VOID_TAGS:
            return
        techniques = self._hidden_techniques(attrs)
        parent_hidden = any(item["hidden"] for item in self._stack)
        item = {"tag": tag, "hidden": bool(techniques) or parent_hidden, "record": None}
        if techniques and not parent_hidden:
            item["record"] = {"tag": tag, "techniques": techniques, "text_len": 0, "sample": ""}
            self.hidden.append(item["record"])
        elif parent_hidden:
            for it in reversed(self._stack):
                if it["record"] is not None:
                    item["record"] = it["record"]
                    break
        self._stack.append(item)

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor is not None:
            a = self._anchor
            self._anchor = None
            text = re.sub(r"\s+", " ", a["text"]).strip()
            self.links.append({"href": a["href"], "text": text[:160]})
            if a["block"] and (len(text) > 100 or a["inner_tags"] >= 5):
                self.wrapped_anchor = True
        if tag in VOID_TAGS:
            return
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data):
        if self._anchor is not None:
            self._anchor["text"] += data
        if any(it["hidden"] for it in self._stack):
            for it in reversed(self._stack):
                if it["record"] is not None:
                    stripped = re.sub(r"\s+", " ", data).strip()
                    it["record"]["text_len"] += len(stripped)
                    if len(it["record"]["sample"]) < 100 and stripped:
                        it["record"]["sample"] = (it["record"]["sample"] + " " + stripped).strip()[:100]
                    break

    def handle_comment(self, data):
        self.comment_count += 1
        self.comment_chars += len(data)
        if len(self.comment_samples) < 3 and data.strip():
            self.comment_samples.append(re.sub(r"\s+", " ", data.strip())[:100])


def _audit_html(html: str) -> dict:
    audit = _HtmlAudit()
    try:
        audit.feed(html)
        audit.close()
    except Exception:  # zepsuty HTML nie może wywrócić analizy
        pass

    tag_names = re.findall(r"<\s*/?\s*([A-Za-z][A-Za-z0-9:_-]*)", html)
    mixed = sorted({t for t in tag_names if t != t.lower() and t != t.upper() and t != t.capitalize()})
    unknown = sorted({t.lower() for t in tag_names if t.lower() not in KNOWN_HTML_TAGS})

    links = []
    for l in audit.links:
        href = l["href"].strip()
        host = _url_host(href) if re.match(r"(?i)https?://", href) else None
        text_host = None
        m = re.search(r"(?i)(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", l["text"])
        if m:
            text_host = m.group(1).lower()
        mismatch = bool(host and text_host and registrable_domain(host) != registrable_domain(text_host))
        params = len(parse_qsl(urlsplit(href).query)) if host else 0
        links.append({
            "text": l["text"], "href": href[:300], "host": host, "scheme": urlsplit(href).scheme if host else None,
            "text_host_mismatch": mismatch, "query_params": params,
            "abused_host": bool(host and any(host == h or host.endswith("." + h) for h in ABUSED_HOSTS)),
            "shortener": bool(host and host in SHORTENERS),
            "idn": bool(host and (host.startswith("xn--") or ".xn--" in host or not host.isascii())),
        })
    return {
        "links": links,
        "images": audit.images,
        "hidden": audit.hidden,
        "hidden_text_total": sum(h["text_len"] for h in audit.hidden),
        "forms": audit.forms, "scripts": audit.scripts, "iframes": audit.iframes, "objects": audit.objects,
        "comment_count": audit.comment_count, "comment_chars": audit.comment_chars,
        "comment_samples": audit.comment_samples,
        "wrapped_anchor": audit.wrapped_anchor,
        "mixed_case_tags": mixed[:10], "unknown_tags": unknown[:10], "unknown_tag_count": len(unknown),
    }


# ---------------------------------------------------------------------------
# filtry antyspamowe odbiorcy i flagi ustawione przez nadawcę
# ---------------------------------------------------------------------------

SENDER_SET_HEADERS = {
    "x-message-flag": "flaga wiadomości ustawiana przez nadawcę (Outlook pokaże ją przy wiadomości) - technika przyciągania uwagi",
    "importance": "ważność deklarowana przez nadawcę (wpływa tylko na wyświetlanie w kliencie)",
    "x-priority": "priorytet deklarowany przez nadawcę (1 = najwyższy)",
    "priority": "priorytet deklarowany przez nadawcę",
    "x-msmail-priority": "priorytet deklarowany przez nadawcę",
    "return-receipt-to": "żądanie potwierdzenia odbioru (śledzenie: potwierdza, że skrzynka żyje)",
    "disposition-notification-to": "żądanie potwierdzenia odczytu (śledzenie: potwierdza, że wiadomość otwarto)",
}
PHISH_CATEGORIES = {"PHSH": "phishing", "HPHSH": "phishing o wysokiej pewności", "MALW": "malware", "SPM": "spam", "HSPM": "spam o wysokiej pewności", "BULK": "masowa"}


def _kv(value: str) -> dict[str, str]:
    """Nagłówki filtrów Microsoftu 'KLUCZ:wartość;KLUCZ:wartość' -> dict (klucze wielkimi literami)."""
    out: dict[str, str] = {}
    for part in value.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out.setdefault(k.strip().upper(), v.strip())
    return out


def _decode_b64_ascii(value: str) -> str | None:
    try:
        raw = base64.b64decode(value.strip() + "=" * (-len(value.strip()) % 4), validate=True)
        text = raw.decode("ascii")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    return text if text and all(32 <= ord(c) < 127 for c in text) else None


def _extract_filters(headers: list[tuple[str, str]], flag) -> dict:
    hd = {}
    for n, v in headers:
        hd.setdefault(n.lower(), v)

    ms: dict = {}
    scl: dict[str, str] = {}
    if "x-ms-exchange-organization-scl" in hd:
        scl["X-MS-Exchange-Organization-SCL"] = hd["x-ms-exchange-organization-scl"].strip()
    forefront = _kv(hd["x-forefront-antispam-report"]) if "x-forefront-antispam-report" in hd else {}
    if forefront.get("SCL"):
        scl["X-Forefront-Antispam-Report"] = forefront["SCL"]
    delivery_decoded = _decode_b64_ascii(hd["x-message-delivery"]) if "x-message-delivery" in hd else None
    if delivery_decoded:
        m = re.search(r"SCL=(-?\d+)", delivery_decoded)
        if m:
            scl["X-Message-Delivery (zdekodowany)"] = m.group(1)
    antispam = _kv(hd["x-microsoft-antispam"]) if "x-microsoft-antispam" in hd else {}
    mailbox = _kv(hd["x-microsoft-antispam-mailbox-delivery"]) if "x-microsoft-antispam-mailbox-delivery" in hd else {}

    if scl or forefront or antispam or mailbox or "x-ms-exchange-organization-authas" in hd:
        junk = "junk" in mailbox.get("RF", "").lower() or mailbox.get("DEST", "").upper() == "J"
        ms = {
            "scl": scl,
            "bcl": antispam.get("BCL"),
            "folder": "Wiadomości-śmieci (Junk)" if junk else None,
            "mailbox_delivery": {k: mailbox[k] for k in ("DEST", "RF", "OFR") if k in mailbox},
            "auth_as": hd.get("x-ms-exchange-organization-authas"),
            "auth_source": hd.get("x-ms-exchange-organization-authsource"),
            "sid_result": hd.get("x-sid-result"),
            "sid_pra": hd.get("x-sid-pra"),
            "forefront": {k: forefront[k] for k in ("CAT", "SFV", "IPV", "DIR", "CTRY", "LANG", "H", "PTR") if forefront.get(k)},
            "message_delivery_decoded": delivery_decoded,
            "opaque_headers": [n for n, _ in headers if n.lower() in ("x-microsoft-antispam-message-info", "x-ms-exchange-antispam-messagedata-0")],
        }
        nums = [int(x) for x in scl.values() if re.fullmatch(r"-?\d+", x)]
        if nums and max(nums) >= 5:
            flag("warn", f"Filtr odbiorcy (Microsoft): SCL={max(nums)} (0-1 czysta, 5-6 spam, 9 najwyższa pewność spamu).")
        if junk:
            flag("warn", "Wiadomość została dostarczona do folderu Wiadomości-śmieci (znaczniki RF:JunkEmail / dest:J w nagłówku dostarczenia filtra).")
        cat = forefront.get("CAT", "")
        for code in [c for c in re.split(r"[+,\s]+", cat) if c in PHISH_CATEGORIES]:
            flag("warn", f"Kategoria filtra Microsoftu: {code} ({PHISH_CATEGORIES[code]}).")
        if (ms["auth_as"] or "").lower() == "anonymous":
            flag("info", "Wiadomość weszła do tenanta anonimowo (AuthAs: Anonymous), bez uwierzytelnionej tożsamości nadawcy.")

    other = []
    for name in ("x-spam-flag", "x-spam-status", "x-spam-score", "x-spam-level", "x-rspamd-score", "x-spam-report"):
        if name in hd:
            other.append({"header": name, "value": hd[name][:200]})
    if hd.get("x-spam-flag", "").strip().upper() == "YES":
        flag("warn", "Filtr antyspamowy odbiorcy oznaczył wiadomość jako spam (X-Spam-Flag: YES).")

    sender_set = []
    for name, note in SENDER_SET_HEADERS.items():
        if name in hd:
            sender_set.append({"header": name, "value": hd[name].strip()[:120], "note": note})
    for item in sender_set:
        if item["header"] in ("return-receipt-to", "disposition-notification-to", "x-message-flag"):
            flag("warn", f"Nadawca ustawił `{item['header']}: {item['value']}` - {item['note']}.")
        elif item["header"] == "importance" and item["value"].lower() == "high" or item["header"] == "x-priority" and item["value"][:1] in ("1", "2"):
            flag("info", f"Nadawca deklaruje wysoki priorytet (`{item['header']}: {item['value']}`) - element presji.")

    return {"microsoft": ms or None, "other": other, "sender_set": sender_set}


# ---------------------------------------------------------------------------
# główna funkcja
# ---------------------------------------------------------------------------

def _walk_mime(msg: Message, depth: int, rows: list[dict], flags: list[str], leaves: list[Message]) -> None:
    ctype = msg.get_content_type()
    cte_raw = (msg.get("Content-Transfer-Encoding") or "").strip()
    cte = cte_raw.lower()
    row = {
        "depth": depth, "content_type": ctype, "charset": msg.get_content_charset(),
        "cte": cte_raw or None, "cte_valid": (not cte) or cte in VALID_CTE,
        "filename": None, "size": None, "boundary": None,
    }
    if not row["cte_valid"]:
        flags.append(f"Niedozwolone Content-Transfer-Encoding: `{cte_raw[:40]}` (część {ctype}) - filtr i klient mogą je zinterpretować różnie (parser differential).")
    if msg.is_multipart():
        row["boundary"] = msg.get_boundary()
        if row["boundary"] and re.search(r"987654321|123456789|0123456789|12345678", row["boundary"]):
            flags.append(f"Boundary `{row['boundary'][:60]}` zawiera ręcznie wpisany ciąg cyfr (imituje generator).")
        rows.append(row)
        parts = msg.get_payload() if isinstance(msg.get_payload(), list) else []
        if ctype == "multipart/digest":
            odd = [p.get_content_type() for p in parts if p.get_content_type().startswith("text/")]
            if odd:
                flags.append("`multipart/digest` służy do paczek wiadomości (message/rfc822), a zawiera części tekstowe/HTML - nietypowe, utrudnia parsowanie.")
        for p in parts:
            _walk_mime(p, depth + 1, rows, flags, leaves)
    else:
        row["filename"] = msg.get_filename()
        try:
            payload = msg.get_payload(decode=True)
            row["size"] = len(payload) if payload is not None else None
        except Exception:
            row["size"] = None
        rows.append(row)
        leaves.append(msg)


def _leaf_text(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    except (LookupError, Exception):
        try:
            return str(part.get_payload())
        except Exception:
            return ""


def decoded_text_parts(src: str) -> str:
    """Zdekodowane (quoted-printable/base64) części tekstowe wiadomości - cytaty z treści HTML modelu
    odpowiadają im, a nie surowemu źródłu."""
    try:
        msg = message_from_string(src)
        leaves: list[Message] = []
        _walk_mime(msg, 0, [], [], leaves)
        return "\n".join(_leaf_text(l) for l in leaves if l.get_content_maintype() == "text" and not l.get_filename())
    except Exception:
        return ""


def compute_facts(src: str) -> dict:
    msg = message_from_string(src)
    headers = [(n, _unfold(v)) for n, v in msg.items()]
    lower_names = [n.lower() for n, _ in headers]
    flags: list[dict] = []  # {"level": "warn"|"info", "text": ...}

    def flag(level: str, text: str) -> None:
        flags.append({"level": level, "text": text})

    def first(name: str) -> str | None:
        for n, v in headers:
            if n.lower() == name:
                return v
        return None

    def all_of(name: str) -> list[str]:
        return [v for n, v in headers if n.lower() == name]

    date_dt = _parse_date(first("date"))

    # --- przegląd ---
    subject_raw = first("subject") or ""
    overview = {
        "subject": _decode_words(subject_raw)[:300],
        "from": _decode_words(first("from") or "")[:300],
        "to": _decode_words(first("to") or "")[:300],
        "date": first("date"),
        "date_utc": _fmt_utc(date_dt),
        "message_id": first("message-id"),
        "header_count": len(headers),
        "received_count": lower_names.count("received"),
        "source_chars": len(src),
    }

    # --- nagłówki: duplikaty, wielkość liter, kodowanie ---
    dup = []
    for name in SINGLE_INSTANCE_HEADERS:
        vals = all_of(name)
        if len(vals) > 1:
            dup.append({"name": name, "count": len(vals), "values": [v[:80] for v in vals]})
            flag("warn", f"Nagłówek `{name}` występuje {len(vals)} razy (powinien raz)" + (
                ": wartości są różne." if len(set(vals)) > 1 else "."))
    casings: dict[str, set[str]] = {}
    for n, _ in headers:
        casings.setdefault(n.lower(), set()).add(n)
    casing_variants = {k: sorted(v) for k, v in casings.items() if len(v) > 1}

    encoded_words, non_ascii = [], []
    for n, v in headers:
        if "=?" in v and re.search(r"=\?[\w-]+\?[bBqQ]\?", v):
            encoded_words.append({"header": n, "raw": v[:160], "decoded": _decode_words(v)[:160]})
        elif not v.isascii():
            non_ascii.append(n)
    if non_ascii:
        flag("info", "Znaki spoza ASCII w nagłówkach bez kodowania RFC 2047: " + ", ".join(sorted(set(non_ascii))[:6]) + " (mógł to spowodować eksport/wklejenie).")

    placeholders: list[str] = []
    head_blob = "\n".join(f"{n}: {v}" for n, v in headers)
    for rx in PLACEHOLDER_RES:
        placeholders += [m.group(0) for m in rx.finditer(head_blob)][:3]

    # --- Received ---
    received = []
    recv_raw = all_of("received")
    for idx, raw in enumerate(recv_raw):
        hop = _parse_received_header(raw)
        ts = None
        if ";" in raw:
            ts = _parse_date(raw.rsplit(";", 1)[1])
        hop_flags = []
        m_id = re.search(r"\bid\s+(\S+?)(?:[;\s]|$)", raw)
        if m_id and re.search(r"[?&=]", m_id.group(1)):
            hop_flags.append(f"pole id zawiera parametry URL (`{m_id.group(1)[:60]}`)")
        m_for = re.search(r"\bfor\s+<?([^>;\s]+)>?", raw)
        if m_for and "@" not in m_for.group(1):
            hop_flags.append(f"`for {m_for.group(1)[:30]}` bez adresu (placeholder?)")
        m_tz = re.search(r"([+-]\d{4})\s*\((\w+)\)\s*$", raw.strip())
        if m_tz and m_tz.group(2).upper() in TZ_ABBR and TZ_ABBR[m_tz.group(2).upper()] != int(m_tz.group(1)):
            hop_flags.append(f"strefa {m_tz.group(1)} nie zgadza się z ({m_tz.group(2)})")
        if ts and date_dt and ts == date_dt and idx == len(recv_raw) - 1 and len(recv_raw) > 1:
            hop_flags.append("czas najstarszego Received identyczny co do sekundy z Date")
        m_helo = re.search(r"helo=([^\s)\]]+)", raw)
        m_ptr = re.search(r"\bfrom\s+\S+\s+\(([^\s()\[\]]+?)\.?\s+\[[0-9a-fA-F:.]+\]", raw)
        m_with = re.search(r"\bwith\s+([A-Za-z0-9]+)", raw)
        m_tls = re.search(r"\((TLS[\w.]*|version=[^)]*)\)|\b(TLS[\w.]+)", raw)
        received.append({
            "index": idx, "from_host": hop["from_host"], "ip": hop["ip"], "by_host": hop["by_host"],
            "helo": m_helo.group(1) if m_helo else None, "ptr": m_ptr.group(1) if m_ptr else None, "with": m_with.group(1) if m_with else None,
            "tls": (m_tls.group(0)[:160] if m_tls else None), "time_utc": _fmt_utc(ts), "_ts": ts,
            "flags": hop_flags, "raw": hop["raw"][:400],
        })
        for f in hop_flags:
            # przy bezpośrednim przyjęciu przez dużego operatora identyczny czas jest normalny - tylko informacja
            level = "info" if f.startswith("czas najstarszego Received") else "warn"
            flag(level, f"Received #{idx} (od góry): {f}.")
    single_operator = None
    trust_note = None
    trust_index = 0
    if received:
        by_fams = {family(registrable_domain((r["by_host"] or "").strip("[]"))) for r in received}
        by_fams.discard(None)
        if len(received) > 1 and len(by_fams) == 1:
            single_operator = next(iter(by_fams))
            trust_index = len(received) - 1
            for r in received:
                r["role"] = (
                    "najstarszy wpis operatora odbiorcy - pierwszy zapis połączenia, IP z gniazda TCP (granica zaufania)"
                    if r["index"] == trust_index
                    else "wewnętrzny skok tego samego operatora (po granicy zaufania)"
                )
            trust_note = (
                f"Cały łańcuch Received należy do jednego operatora ({single_operator}) - to infrastruktura odbiorcy. "
                f"Granicą zaufania jest najstarszy wpis (#{trust_index}): to on zapisał adres IP połączenia; "
                "wyższe wpisy to wewnętrzne skoki tego samego operatora."
            )
            flag("info", trust_note)
        else:
            received[0]["role"] = "najwyższy - dopisany przez serwer odbiorcy (granica zaufania)"
            for r in received[1:]:
                r["role"] = "poniżej granicy zaufania - niezweryfikowany bez zaufania do jego autora"

    # --- uwierzytelnianie ---
    top_by_domains = set()  # rodziny operatorów, które zapisały Received po stronie odbiorcy
    for r in received:
        d = family(registrable_domain((r["by_host"] or "").strip("[]")))
        if d:
            top_by_domains.add(d)
    auth = []
    for n, v in headers:
        ln = n.lower()
        if ln not in ("authentication-results", "arc-authentication-results", "received-spf"):
            continue
        entry: dict = {"header": n, "raw": v[:400], "results": {}, "details": {}}
        if ln == "received-spf":
            m = re.match(r"\s*(pass|fail|softfail|neutral|none|temperror|permerror)", v, re.IGNORECASE)
            if m:
                entry["results"]["spf"] = m.group(1).lower()
            for k in ("client-ip", "envelope-from", "helo", "identity"):
                mm = re.search(rf"{k}\s*=\s*\"?([^;\s\"]+)", v, re.IGNORECASE)
                if mm:
                    entry["details"][k] = mm.group(1)
        else:
            body = re.sub(r"^\s*i\s*=\s*\d+\s*;\s*", "", v)
            authserv = body.split(";", 1)[0].strip().split()[0] if body.strip() else None
            entry["authserv_id"] = authserv
            ad = family(registrable_domain((authserv or "").lower())) if authserv else None
            entry["matches_receiver"] = (ad in top_by_domains) if (ad and top_by_domains) else None
            for m in re.finditer(r"\b(spf|dkim|dmarc|arc|dkim-atps|compauth)\s*=\s*([a-z]+)", body, re.IGNORECASE):
                entry["results"].setdefault(m.group(1).lower(), m.group(2).lower())
            for m in re.finditer(r"\b(smtp\.mailfrom|smtp\.helo|header\.from|header\.d|header\.i|header\.s)\s*=\s*([^\s;]+)", body, re.IGNORECASE):
                entry["details"].setdefault(m.group(1).lower(), m.group(2))
        auth.append(entry)

    # --- DKIM / ARC ---
    dkim = []
    for v in all_of("dkim-signature"):
        t = _tags(v)
        signed = [h.strip().lower() for h in t.get("h", "").split(":") if h.strip()]
        bh = t.get("bh", "")
        hash_hint = {28: "SHA-1 (20 B)", 44: "SHA-256 (32 B)", 88: "SHA-512 (64 B)"}.get(len(bh), "nietypowa")
        unsigned = [h for h in ("from", "to", "subject", "date", "reply-to", "message-id", "content-type") if h not in signed]
        dkim.append({
            "d": t.get("d"), "s": t.get("s"), "a": t.get("a"), "c": t.get("c"), "i": t.get("i"), "t": t.get("t"),
            "bh_len": len(bh), "hash_hint": hash_hint, "signed_headers": signed, "unsigned_important": unsigned,
            "legacy_sha1": (t.get("a") or "").lower().endswith("sha1"),
        })
        if (t.get("a") or "").lower().endswith("sha1"):
            flag("warn", f"DKIM `d={t.get('d')}` używa {t.get('a')} (SHA-1 jest przestarzały, RFC 8301).")
    if "domainkey-signature" in lower_names:
        flag("warn", "Obecny nagłówek `DomainKey-Signature` (przestarzały poprzednik DKIM).")
    arc = []
    for n, v in headers:
        if n.lower() == "arc-seal":
            t = _tags(v)
            arc.append({"i": t.get("i"), "d": t.get("d"), "s": t.get("s"), "cv": t.get("cv"), "t": t.get("t")})

    # --- tożsamość i zgodność domen ---
    from_addr, from_dom = _addr_domain(first("from"))
    from_reg = registrable_domain(from_dom)
    identity_rows = []

    def add_identity(field: str, value: str | None, domain: str | None) -> None:
        if not value and not domain:
            return
        reg = registrable_domain(domain)
        aligned = None if (not reg or not from_reg or field == "From") else (reg == from_reg)
        identity_rows.append({"field": field, "value": (value or "")[:120], "domain": domain, "aligned": aligned})

    add_identity("From", from_addr, from_dom)
    rt = first("reply-to")
    if rt:
        add_identity("Reply-To", *_addr_domain(rt))
    add_identity("Return-Path", *_addr_domain(first("return-path")))
    if first("sender"):
        add_identity("Sender", *_addr_domain(first("sender")))
    mid = first("message-id")
    if mid and "@" in mid:
        add_identity("Message-ID", mid, mid.rsplit("@", 1)[1].strip("> ").lower())
    for d in dkim:
        add_identity("DKIM (d=)", d["d"], (d["d"] or "").lower() or None)
    for a in auth:
        mf = a["details"].get("smtp.mailfrom")
        if mf:
            add_identity(f"{a['header']} smtp.mailfrom", mf, mf.rsplit("@", 1)[-1].lower())
    unsub_hdr = first("list-unsubscribe") or ""
    unsub_urls = re.findall(r"<([^>]+)>", unsub_hdr)
    for u in unsub_urls[:3]:
        if re.match(r"(?i)https?://", u):
            host = _url_host(u)
        else:
            bare = re.sub(r"(?i)^mailto:", "", u).split("?")[0]
            host = bare.rsplit("@", 1)[-1].lower() if "@" in bare else None
        add_identity("List-Unsubscribe", u[:100], host)
    misaligned = [r for r in identity_rows if r["aligned"] is False and r["field"] != "Message-ID"]
    if misaligned and from_reg:
        flag("warn", "Domeny niezgodne z domeną `From` (" + str(from_reg) + "): " + ", ".join(sorted({f"{r['field']}={r['domain']}" for r in misaligned})[:6]) + ".")
    if rt and _addr_domain(rt)[1] and registrable_domain(_addr_domain(rt)[1]) != from_reg:
        flag("warn", "Reply-To w innej domenie niż From (klasyczny sygnał ostrzegawczy).")
    for dom in [from_dom] + [r["domain"] for r in identity_rows if r["domain"]]:
        if dom and (dom.startswith("xn--") or ".xn--" in dom or not dom.isascii()):
            flag("warn", f"Domena `{dom}` używa punycode/znaków spoza ASCII (możliwy homoglif).")
            break

    # --- oś czasu ---
    timeline = []
    if date_dt:
        timeline.append({"event": "Date (deklaracja nadawcy)", "raw": first("date"), "_ts": date_dt})
    for r in reversed(received):
        if r["_ts"]:
            label = f"Received #{r['index']} ({r['by_host'] or '?'})"
            timeline.append({"event": label, "raw": r["time_utc"], "_ts": r["_ts"]})
    prev = None
    for row in timeline:
        row["utc"] = _fmt_utc(row["_ts"])
        row["delta_s"] = int((row["_ts"] - prev).total_seconds()) if prev else None
        prev = row["_ts"]
    if date_dt and received and received[0]["_ts"]:
        total = int((received[0]["_ts"] - date_dt).total_seconds())
        if total > 3600:
            flag("warn", f"Od `Date` do najwyższego Received minęło {total // 3600} h {(total % 3600) // 60} min (duże opóźnienie).")
        elif total < -300:
            flag("warn", "`Date` jest późniejsza niż czas najwyższego Received (data z przyszłości względem odbioru).")
    for r in received:
        r.pop("_ts", None)
    for row in timeline:
        row.pop("_ts", None)

    # --- epoch ---
    epochs = []

    def epoch_add(where: str, num: str) -> None:
        val = int(num)
        secs = val / 1000 if len(num) == 13 else val
        if not (946_684_800 <= secs <= 4_102_444_800):
            return
        dt = datetime.fromtimestamp(secs, tz=timezone.utc)
        epochs.append({"where": where, "value": num, "utc": _fmt_utc(dt),
                       "diff_vs_date_s": int((dt - date_dt).total_seconds()) if date_dt else None,
                       "unit": "ms" if len(num) == 13 else "s"})

    if mid:
        for num in re.findall(r"(?<!\d)(\d{13})(?!\d)", mid):
            epoch_add("Message-ID", num)
    for n, v in headers:
        if n.lower() in ("arc-seal", "arc-message-signature", "dkim-signature"):
            m = re.search(r"(?:^|;)\s*t\s*=\s*(\d{10})\b", v)
            if m:
                epoch_add(n, m.group(1))

    # --- MIME i treść ---
    mime_rows: list[dict] = []
    mime_flag_texts: list[str] = []
    leaves: list[Message] = []
    _walk_mime(msg, 0, mime_rows, mime_flag_texts, leaves)
    for t in mime_flag_texts:
        flag("warn", t)

    attachments = []
    html_parts, text_parts = [], []
    for leaf in leaves:
        ctype = leaf.get_content_type()
        fname = leaf.get_filename()
        if fname:
            try:
                payload = leaf.get_payload(decode=True) or b""
            except Exception:
                payload = b""
            segs = fname.split(".")
            ext = segs[-1].lower() if len(segs) > 1 else ""
            apparent = segs[-2].lower() if len(segs) > 2 and segs[-2].lower() in DOUBLE_EXT_DISPLAY and segs[-2].lower() != ext else None
            attachments.append({
                "filename": _decode_words(fname)[:120], "content_type": ctype, "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest() if payload else None,
                "extension": ext, "double_extension_as": apparent, "risky_extension": ext in RISKY_EXTENSIONS,
            })
            if apparent:
                flag("warn", f"Załącznik `{fname[:60]}`: podwójne rozszerzenie (wygląda na .{apparent}, faktycznie .{ext}).")
            elif ext in RISKY_EXTENSIONS:
                flag("warn", f"Załącznik `{fname[:60]}` ma ryzykowne rozszerzenie .{ext}.")
            continue
        if ctype == "text/html":
            html_parts.append(_leaf_text(leaf))
        elif ctype == "text/plain":
            text_parts.append(_leaf_text(leaf))
    if html_parts and not text_parts:
        flag("info", "Brak części `text/plain` (jest tylko HTML) - legalne wysyłki masowe zwykle dodają tekstową alternatywę.")

    html_audit = _audit_html("\n".join(html_parts)) if html_parts else None
    body_blob = "\n".join(text_parts + html_parts)
    for rx in PLACEHOLDER_RES:
        placeholders += [m.group(0) for m in rx.finditer(body_blob)][:3]
    placeholders = list(dict.fromkeys(placeholders))[:8]
    if placeholders:
        flag("warn", "Niepodstawione placeholdery szablonu: " + ", ".join(f"`{p[:30]}`" for p in placeholders[:5]) + ".")

    urls_plain = list(dict.fromkeys(re.findall(r"https?://[^\s<>\"')]+", "\n".join(text_parts))))[:15]

    if html_audit:
        h = html_audit
        if h["hidden"]:
            techs = sorted({t for rec in h["hidden"] for t in rec["techniques"]})
            flag("warn", f"Ukryta treść: {len(h['hidden'])} elementów ({h['hidden_text_total']} znaków), techniki: {', '.join(techs)}.")
        if h["comment_chars"] > 500:
            flag("warn", f"Duży komentarz HTML ({h['comment_chars']} znaków w {h['comment_count']} komentarzach) - możliwe wypełniacze (Bayesian poisoning).")
        if h["mixed_case_tags"]:
            flag("warn", "Losowa wielkość liter w znacznikach: " + ", ".join(f"`{t}`" for t in h["mixed_case_tags"][:4]) + ".")
        if h["unknown_tag_count"] >= 5:
            flag("warn", f"{h['unknown_tag_count']} nieznanych znaczników HTML (możliwy hash busting), np. " + ", ".join(f"`{t}`" for t in h["unknown_tags"][:3]) + ".")
        if h["wrapped_anchor"]:
            flag("warn", "Duża część treści jest opakowana w jeden link (`<a style=display:block>`): każdy klik prowadzi na stronę docelową.")
        for kind, cnt in (("formularz", h["forms"]), ("skrypt", h["scripts"]), ("iframe", h["iframes"]), ("object/embed", h["objects"])):
            if cnt:
                flag("warn", f"Treść zawiera {kind} ({cnt}).")
        tracking = [i for i in h["images"] if i["tracking_hint"]]
        if tracking:
            flag("info", f"{len(tracking)} obrazów wygląda na śledzące (1x1 lub z parametrami w URL).")
        for l in h["links"]:
            if l["text_host_mismatch"]:
                flag("warn", f"Link: widoczny tekst wskazuje inną domenę niż href (`{l['text'][:40]}` -> `{l['host']}`).")
            if l["scheme"] == "http":
                flag("info", f"Link używa http:// (`{(l['host'] or '')[:50]}`).")
            if l["abused_host"]:
                flag("info", f"Link do usługi często nadużywanej do hostowania phishingu: `{l['host']}`.")
            if l["shortener"]:
                flag("warn", f"Link przez skracacz: `{l['host']}`.")
        if any(l["query_params"] >= 4 for l in h["links"]):
            flag("info", "Link z wieloma parametrami w URL (identyfikatory śledzące?).")

    all_link_hosts = []
    for u in unsub_urls:
        if re.match(r"(?i)https?://", u):
            all_link_hosts.append(_url_host(u))
    if unsub_hdr and not first("list-unsubscribe-post"):
        flag("info", "`List-Unsubscribe` bez `List-Unsubscribe-Post` (brak one-click RFC 8058).")

    filters = _extract_filters(headers, flag)

    # --- IP ---
    ips = []
    for r in received:
        if r["ip"]:
            ips.append({"ip": r["ip"], "where": f"Received #{r['index']}"})
    for name in ("x-originating-ip", "x-sender-ip"):
        v = first(name)
        if v:
            ips.append({"ip": v.strip("[] ")[:45], "where": name})
    if first("x-originating-ip"):
        flag("info", "Nagłówek `X-Originating-IP` może być wyciekiem infrastruktury albo przynętą - nie nadaje się do zgłoszeń bez potwierdzenia w zaufanym Received.")

    # nagłówki o nazwach używanych przez odbiorcę/dostawcę, a leżące PONIŻEJ wszystkich Received
    if len(received) > 1:
        last_recv_idx = max(i for i, (n, _) in enumerate(headers) if n.lower() == "received")
        below = {
            n for n, _ in headers[last_recv_idx + 1:]
            if n.lower().startswith(("x-google-", "x-original-sender", "envelope-to", "x-gm-", "delivered-to"))
        }
        if below:
            flag("warn", "Nagłówki o nazwach używanych przez odbiorcę/dostawcę są PONIŻEJ wszystkich Received (tekst nadawcy, nie serwera): " + ", ".join(sorted(below)[:6]) + ".")

    return {
        "overview": overview,
        "flags": flags,
        "received": received,
        "trust_note": trust_note,
        "single_operator": single_operator,
        "filters": filters,
        "auth": auth,
        "dkim": dkim,
        "arc": arc,
        "identity": identity_rows,
        "timeline": timeline,
        "epochs": epochs,
        "duplicates": dup,
        "casing_variants": casing_variants,
        "encoded_words": encoded_words[:10],
        "placeholders": placeholders,
        "mime": mime_rows,
        "attachments": attachments,
        "html": html_audit,
        "urls_plain": urls_plain,
        "list_unsubscribe": {"urls": [u[:200] for u in unsub_urls[:5]], "one_click": bool(first("list-unsubscribe-post"))},
        "ips": ips,
    }
