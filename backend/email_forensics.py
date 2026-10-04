"""Deterministic analysis of the e-mail source for the "Email" tab.

Everything here is computed locally, without network and without an LLM: timeline, epoch conversions, bh=
lengths, MIME tree, link table, hidden content etc. The result goes both to the interface (immediately) and to
the LLM prompt as "facts computed by the code", so that the model explains instead of calculating.

User-facing texts (findings, roles, labels) are produced with t() in the language of the current request.

The message is untrusted input: nothing here opens links, downloads resources or executes content.
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
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlsplit

from backend.email_parser import find_boundary_index, parse_received_header
from backend.i18n import t
from backend.mail_trust import (
    domains_consistent,
    family,
    hop_specific_auth,
    is_dotless_internal_hop,
    is_special_ip,
    parse_ip,
    registrable_domain,
)

MAX_LLM_SOURCE_CHARS = 120_000
MAX_DECODED_TEXT_CHARS = 60_000
# Markers that fence the quoted message in an LLM prompt: everything between them is UNTRUSTED data, not instructions.
EMAIL_START = "===EMAIL-START==="
EMAIL_END = "===EMAIL-END==="

VALID_CTE = {"7bit", "8bit", "binary", "quoted-printable", "base64"}
SINGLE_INSTANCE_HEADERS = {
    "from", "to", "subject", "date", "message-id", "reply-to", "sender", "mime-version",
    "content-type", "content-transfer-encoding", "content-length",
}
TZ_ABBR = {
    "UTC": 0, "GMT": 0, "Z": 0, "PDT": -700, "PST": -800, "MDT": -600, "MST": -700, "CDT": -500, "CST": -600,
    "EDT": -400, "EST": -500, "CET": 100, "CEST": 200, "BST": 100, "EET": 200, "EEST": 300, "JST": 900, "IST": 530,
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
KNOWN_HTML_TAGS = {
    "a", "abbr", "address", "area", "article", "aside", "audio", "b", "base", "bdi", "bdo", "blockquote",
    "body", "br", "button", "canvas", "caption", "center", "cite", "code", "col", "colgroup", "data",
    "datalist", "dd", "del", "details", "dfn", "dialog", "div", "dl", "dt", "em", "embed", "fieldset",
    "figcaption", "figure", "font", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "head", "header",
    "hr", "html", "i", "iframe", "img", "input", "ins", "kbd", "label", "legend", "li", "link", "main", "map",
    "mark", "meta", "meter", "nav", "noscript", "object", "ol", "optgroup", "option", "output", "p", "param",
    "picture", "pre", "progress", "q", "rp", "rt", "ruby", "s", "samp", "script", "section", "select", "small",
    "source", "span", "strike", "strong", "style", "sub", "summary", "sup", "table", "tbody", "td", "template",
    "textarea", "tfoot", "th", "thead", "time", "title", "tr", "track", "u", "ul", "var", "video", "wbr", "o:p",
    "v:shape", "xml",
}
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
# normalisation and preparation of the source
# ---------------------------------------------------------------------------

def normalize_source(raw: str) -> str:
    """Unifies the source pasted/loaded from a file: BOM, line endings, mbox envelope ("From ..."), leading
    empty lines. Does not change anything inside the headers or the body."""
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
        return base64.b64decode("".join(line.strip() for line in lines), validate=False)
    except (binascii.Error, ValueError):
        return None


def prepare_for_llm(src: str, max_chars: int = MAX_LLM_SOURCE_CHARS) -> tuple[str, list[str]]:
    """Version of the source for the LLM: binary base64 attachments are replaced by a marker (size + sha256),
    text base64 parts are decoded (the model reads them directly), the rest is unchanged. Returns (text, notes
    for the user). The markers are input for the model (English); the notes are shown to the user (translated)."""
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
                text = text[:MAX_DECODED_TEXT_CHARS] + "\n...(truncated)"
            out.append(f"[Seisa: below is the content of the {ctype} part decoded from base64 (charset {charset})]")
            out.extend(text.split("\n"))
            out.append("[Seisa: end of the decoded part]")
            notes.append(t("forensics.prep_decoded", ctype=ctype, size=len(data)))
        else:
            digest = hashlib.sha256(data).hexdigest()
            out.append(f"[Seisa: base64 content omitted ({ctype or 'unknown type'}): {len(data)} bytes after decoding, sha256={digest}]")
            notes.append(t("forensics.prep_omitted", ctype=ctype or "?", size=len(data)))

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
        elif mode == "body" and is_boundary(line):
            mode, hdrs, last_name = "headers", {}, None

    if mode == "capture" and capture:
        flush_capture(hdrs.get("content-type", "").split(";")[0].strip().lower(), "")

    text = "\n".join(out)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[Seisa: source truncated to the limit]"
        notes.append(t("forensics.prep_truncated", n=max_chars))
    return text, notes


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

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
    """DKIM/ARC tags 'k=v; k=v' -> dict (later occurrences do not overwrite the first one)."""
    out: dict[str, str] = {}
    for part in value.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out.setdefault(k.strip().lower(), re.sub(r"\s+", "", v))
    return out


def _fmt_utc(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC") if dt else None


# ---------------------------------------------------------------------------
# HTML analysis (hidden content, links, remote elements)
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
            found.append(t("forensics.hidden_attr"))
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
    except Exception:  # broken HTML must not bring down the analysis
        pass

    tag_names = re.findall(r"<\s*/?\s*([A-Za-z][A-Za-z0-9:_-]*)", html)
    mixed = sorted({tag for tag in tag_names if tag != tag.lower() and tag != tag.upper() and tag != tag.capitalize()})
    unknown = sorted({tag.lower() for tag in tag_names if tag.lower() not in KNOWN_HTML_TAGS})

    links = []
    for link in audit.links:
        href = link["href"].strip()
        host = _url_host(href) if re.match(r"(?i)https?://", href) else None
        text_host = None
        m = re.search(r"(?i)(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", link["text"])
        if m:
            text_host = m.group(1).lower()
        mismatch = bool(host and text_host and registrable_domain(host) != registrable_domain(text_host))
        params = len(parse_qsl(urlsplit(href).query)) if host else 0
        links.append({
            "text": link["text"], "href": href[:300], "host": host, "scheme": urlsplit(href).scheme if host else None,
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
# recipient anti-spam filters and flags set by the sender
# ---------------------------------------------------------------------------

# header -> catalog key of the explanation (forensics.sender.<key>)
SENDER_SET_HEADERS = {
    "x-message-flag": "message_flag",
    "importance": "importance",
    "x-priority": "x_priority",
    "priority": "priority",
    "x-msmail-priority": "priority",
    "return-receipt-to": "return_receipt",
    "disposition-notification-to": "read_receipt",
}
PHISH_CATEGORIES = ("PHSH", "HPHSH", "MALW", "SPM", "HSPM", "BULK")  # names: forensics.category.<code>


def _kv(value: str) -> dict[str, str]:
    """Microsoft filter headers 'KEY:value;KEY:value' -> dict (keys in upper case)."""
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
            scl[t("forensics.msg_delivery_decoded")] = m.group(1)
    antispam = _kv(hd["x-microsoft-antispam"]) if "x-microsoft-antispam" in hd else {}
    mailbox = _kv(hd["x-microsoft-antispam-mailbox-delivery"]) if "x-microsoft-antispam-mailbox-delivery" in hd else {}

    if scl or forefront or antispam or mailbox or "x-ms-exchange-organization-authas" in hd:
        junk = "junk" in mailbox.get("RF", "").lower() or mailbox.get("DEST", "").upper() == "J"
        ms = {
            "scl": scl,
            "bcl": antispam.get("BCL"),
            "folder": t("forensics.junk_folder") if junk else None,
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
            flag("warn", t("forensics.flag.scl", scl=max(nums)))
        if junk:
            flag("warn", t("forensics.flag.junk"))
        cat = forefront.get("CAT", "")
        for code in [c for c in re.split(r"[+,\s]+", cat) if c in PHISH_CATEGORIES]:
            flag("warn", t("forensics.flag.ms_category", code=code, name=t(f"forensics.category.{code}")))
        if (ms["auth_as"] or "").lower() == "anonymous":
            flag("info", t("forensics.flag.anonymous"))

    other = []
    for name in ("x-spam-flag", "x-spam-status", "x-spam-score", "x-spam-level", "x-rspamd-score", "x-spam-report"):
        if name in hd:
            other.append({"header": name, "value": hd[name][:200]})
    if hd.get("x-spam-flag", "").strip().upper() == "YES":
        flag("warn", t("forensics.flag.spam_flag"))

    sender_set = []
    for name, note_key in SENDER_SET_HEADERS.items():
        if name in hd:
            sender_set.append({"header": name, "value": hd[name].strip()[:120], "note": t(f"forensics.sender.{note_key}")})
    for item in sender_set:
        if item["header"] in ("return-receipt-to", "disposition-notification-to", "x-message-flag"):
            flag("warn", t("forensics.flag.sender_set", header=item["header"], value=item["value"], note=item["note"]))
        elif (item["header"] == "importance" and item["value"].lower() == "high") or (item["header"] == "x-priority" and item["value"][:1] in ("1", "2")):
            flag("info", t("forensics.flag.high_priority", header=item["header"], value=item["value"]))

    return {"microsoft": ms or None, "other": other, "sender_set": sender_set}


# ---------------------------------------------------------------------------
# main function
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
        flags.append(t("forensics.flag.bad_cte", cte=cte_raw[:40], ctype=ctype))
    if msg.is_multipart():
        row["boundary"] = msg.get_boundary()
        if row["boundary"] and re.search(r"987654321|123456789|0123456789|12345678", row["boundary"]):
            flags.append(t("forensics.flag.boundary_digits", boundary=row["boundary"][:60]))
        rows.append(row)
        parts = msg.get_payload() if isinstance(msg.get_payload(), list) else []
        if ctype == "multipart/digest":
            odd = [p.get_content_type() for p in parts if p.get_content_type().startswith("text/")]
            if odd:
                flags.append(t("forensics.flag.digest"))
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
    except Exception:
        try:
            return str(part.get_payload())
        except Exception:
            return ""


def decoded_text_parts(src: str) -> str:
    """Decoded (quoted-printable/base64) text parts of the message - quotes from the HTML body made by the model
    correspond to them, not to the raw source."""
    try:
        msg = message_from_string(src)
        leaves: list[Message] = []
        _walk_mime(msg, 0, [], [], leaves)
        return "\n".join(_leaf_text(leaf) for leaf in leaves if leaf.get_content_maintype() == "text" and not leaf.get_filename())
    except Exception:
        return ""


class _Ctx:
    """State shared by the sections of compute_facts: the parsed message, the unfolded headers and the findings.

    The sections run in a fixed order and `flags` keeps the order in which findings were raised - that order is part
    of the output (the scripts/dump_facts.py golden files compare it byte for byte)."""

    def __init__(self, src: str) -> None:
        self.src = src
        self.msg = message_from_string(src)
        self.headers = [(n, _unfold(v)) for n, v in self.msg.items()]
        self.lower_names = [n.lower() for n, _ in self.headers]
        self.flags: list[dict] = []  # {"level": "warn"|"info", "text": ...}
        self.date_dt = _parse_date(self.first("date"))

    def flag(self, level: str, text: str) -> None:
        self.flags.append({"level": level, "text": text})

    def first(self, name: str) -> str | None:
        for n, v in self.headers:
            if n.lower() == name:
                return v
        return None

    def all_of(self, name: str) -> list[str]:
        return [v for n, v in self.headers if n.lower() == name]


def _overview(ctx: _Ctx) -> dict:
    subject_raw = ctx.first("subject") or ""
    return {
        "subject": _decode_words(subject_raw)[:300],
        "from": _decode_words(ctx.first("from") or "")[:300],
        "to": _decode_words(ctx.first("to") or "")[:300],
        "date": ctx.first("date"),
        "date_utc": _fmt_utc(ctx.date_dt),
        "message_id": ctx.first("message-id"),
        "header_count": len(ctx.headers),
        "received_count": ctx.lower_names.count("received"),
        "source_chars": len(ctx.src),
    }


def _header_hygiene(ctx: _Ctx) -> tuple[list, dict, list, list[str]]:
    """Duplicated single-instance headers, letter-case variants, encoded words, template placeholders in headers."""
    dup = []
    for name in SINGLE_INSTANCE_HEADERS:
        vals = ctx.all_of(name)
        if len(vals) > 1:
            dup.append({"name": name, "count": len(vals), "values": [v[:80] for v in vals]})
            ctx.flag("warn", t("forensics.flag.duplicate", name=name, n=len(vals)) + (
                t("forensics.flag.duplicate_differ") if len(set(vals)) > 1 else "."))
    casings: dict[str, set[str]] = {}
    for n, _ in ctx.headers:
        casings.setdefault(n.lower(), set()).add(n)
    casing_variants = {k: sorted(v) for k, v in casings.items() if len(v) > 1}

    encoded_words, non_ascii = [], []
    for n, v in ctx.headers:
        if "=?" in v and re.search(r"=\?[\w-]+\?[bBqQ]\?", v):
            encoded_words.append({"header": n, "raw": v[:160], "decoded": _decode_words(v)[:160]})
        elif not v.isascii():
            non_ascii.append(n)
    if non_ascii:
        ctx.flag("info", t("forensics.flag.non_ascii", headers=", ".join(sorted(set(non_ascii))[:6])))

    placeholders: list[str] = []
    head_blob = "\n".join(f"{n}: {v}" for n, v in ctx.headers)
    for rx in PLACEHOLDER_RES:
        placeholders += [m.group(0) for m in rx.finditer(head_blob)][:3]
    return dup, casing_variants, encoded_words, placeholders


def _received_hops(ctx: _Ctx) -> tuple[list[dict], str | None, str | None, int]:
    """The Received chain with per-hop findings, the trust boundary (when one operator wrote the whole chain)
    and the index of the hop the "sender IP" fact should point to."""
    received = []
    recv_raw = ctx.all_of("received")
    for idx, raw in enumerate(recv_raw):
        hop = parse_received_header(raw)
        ts = None
        if ";" in raw:
            ts = _parse_date(raw.rsplit(";", 1)[1])
        hop_flags = []
        info_hop_flags = set()  # findings that are informational only
        m_id = re.search(r"\bid\s+(\S+?)(?:[;\s]|$)", raw)
        if m_id and re.search(r"[?&=]", m_id.group(1)):
            hop_flags.append(t("forensics.hop.id_params", id=m_id.group(1)[:60]))
        m_for = re.search(r"\bfor\s+<?([^>;\s]+)>?", raw)
        if m_for and "@" not in m_for.group(1):
            hop_flags.append(t("forensics.hop.for_no_address", value=m_for.group(1)[:30]))
        m_tz = re.search(r"([+-]\d{4})\s*\((\w+)\)\s*$", raw.strip())
        if m_tz and m_tz.group(2).upper() in TZ_ABBR and TZ_ABBR[m_tz.group(2).upper()] != int(m_tz.group(1)):
            hop_flags.append(t("forensics.hop.tz_mismatch", offset=m_tz.group(1), name=m_tz.group(2)))
        if ts and ctx.date_dt and ts == ctx.date_dt and idx == len(recv_raw) - 1 and len(recv_raw) > 1:
            same_time = t("forensics.hop.same_time_as_date")
            hop_flags.append(same_time)
            info_hop_flags.add(same_time)
        m_helo = re.search(r"helo=([^\s)\]]+)", raw)
        m_ptr = re.search(r"\bfrom\s+\S+\s+\(([^\s()\[\]]+?)\.?\s+\[[0-9a-fA-F:.]+\]", raw)
        m_with = re.search(r"\bwith\s+([A-Za-z0-9]+)", raw)
        m_tls = re.search(r"\((TLS[\w.]*|version=[^)]*)\)|\b(TLS[\w.]+)", raw)
        received.append({
            "index": idx, "from_host": hop["from_host"], "ip": hop["ip"], "by_host": hop["by_host"],
            "is_private": is_special_ip(hop["ip"]) if hop["ip"] else None,
            "helo": m_helo.group(1) if m_helo else None, "ptr": m_ptr.group(1) if m_ptr else None, "with": m_with.group(1) if m_with else None,
            "tls": (m_tls.group(0)[:160] if m_tls else None), "time_utc": _fmt_utc(ts), "_ts": ts,
            "flags": hop_flags, "raw": hop["raw"][:400],
        })
        for f in hop_flags:
            # with direct acceptance by a large operator an identical time is normal - information only
            level = "info" if f in info_hop_flags else "warn"
            ctx.flag(level, t("forensics.flag.hop", idx=idx, text=f))

    # SMTP-AUTH/DKIM corroboration per hop, positionally correlated (never by text match, which a forged header
    # could defeat) - purely informational: it never changes which hop is the trust boundary, only annotates one.
    hop_auth = hop_specific_auth(ctx.headers, len(received))
    for r in received:
        corroboration = hop_auth.get(r["index"])
        account = corroboration.get("smtp_auth_account") if corroboration else None
        if not corroboration or corroboration.get("auth") != "pass" or not account:
            r["smtp_auth_account"], r["dkim_domain"], r["auth_consistent"] = None, None, None
            continue
        dkim_domain = corroboration.get("dkim_domain")
        account_domain = account.split("@")[-1] if "@" in account else None
        r["smtp_auth_account"] = account
        r["dkim_domain"] = dkim_domain
        r["auth_consistent"] = domains_consistent(account_domain, dkim_domain) if dkim_domain else None

    single_operator = None
    trust_note = None
    trust_index = 0
    if received:
        # A by_host without a dot (e.g. a Kubernetes pod name) says nothing about which operator owns the hop
        # as long as its own recorded IP is private/absent - so it is excluded here rather than counted as a
        # spurious "different family", the same way an unparseable domain (None) already was.
        by_fams = {
            family(registrable_domain(by_host))
            for r in received
            if (by_host := (r["by_host"] or "").strip("[]")) and not is_dotless_internal_hop(by_host, r["ip"])
        }
        by_fams.discard(None)
        oldest_index = len(received) - 1
        oldest_ip = received[oldest_index]["ip"]
        if len(received) > 1 and len(by_fams) == 1 and oldest_ip and not is_special_ip(oldest_ip):
            single_operator = next(iter(by_fams))
            trust_index = oldest_index
            for r in received:
                r["role"] = (
                    t("forensics.role.oldest_operator")
                    if r["index"] == trust_index
                    else t("forensics.role.internal_hop")
                )
            trust_note = t("forensics.trust_note", operator=single_operator, index=trust_index)
            ctx.flag("info", trust_note)
        else:
            # No single operator wrote the whole chain - but the top hop (written by the recipient's own
            # server) may itself be just a relay: walk through same-relay internal hops (the exact algorithm
            # the AbuseIPDB tab uses to pick its report IP) to see if a deeper hop is the real trust boundary.
            walked_index, _walk_confidence = find_boundary_index(recv_raw)
            walked_ip = received[walked_index]["ip"] if walked_index is not None else None
            if walked_index is not None and walked_index > 0 and walked_ip and not is_special_ip(walked_ip):
                trust_index = walked_index
                ctx.flag("warn", t("forensics.walked_warning", ip=received[0]["ip"] or "?"))
                for r in received:
                    if r["index"] < trust_index:
                        r["role"] = t("forensics.role.internal_hop")
                    elif r["index"] == trust_index:
                        r["role"] = t("forensics.role.walked_boundary")
                    else:
                        r["role"] = t("forensics.role.below")
            else:
                trust_index = 0
                received[0]["role"] = t("forensics.role.top")
                for r in received[1:]:
                    r["role"] = t("forensics.role.below")
    return received, single_operator, trust_note, trust_index


def _authentication(ctx: _Ctx, received: list[dict]) -> list[dict]:
    """Authentication-Results, ARC-Authentication-Results and Received-SPF headers as structured entries."""
    top_by_domains = set()  # operator families that wrote Received on the recipient's side
    for r in received:
        d = family(registrable_domain((r["by_host"] or "").strip("[]")))
        if d:
            top_by_domains.add(d)
    auth = []
    for n, v in ctx.headers:
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
    return auth


def _dkim_arc(ctx: _Ctx) -> tuple[list[dict], list[dict]]:
    dkim = []
    for v in ctx.all_of("dkim-signature"):
        tags = _tags(v)
        signed = [h.strip().lower() for h in tags.get("h", "").split(":") if h.strip()]
        bh = tags.get("bh", "")
        hash_hint = {28: "SHA-1 (20 B)", 44: "SHA-256 (32 B)", 88: "SHA-512 (64 B)"}.get(len(bh), t("forensics.dkim_unusual"))
        unsigned = [h for h in ("from", "to", "subject", "date", "reply-to", "message-id", "content-type") if h not in signed]
        dkim.append({
            "d": tags.get("d"), "s": tags.get("s"), "a": tags.get("a"), "c": tags.get("c"), "i": tags.get("i"), "t": tags.get("t"),
            "bh_len": len(bh), "hash_hint": hash_hint, "signed_headers": signed, "unsigned_important": unsigned,
            "legacy_sha1": (tags.get("a") or "").lower().endswith("sha1"),
        })
        if (tags.get("a") or "").lower().endswith("sha1"):
            ctx.flag("warn", t("forensics.flag.dkim_sha1", d=tags.get("d"), a=tags.get("a")))
    if "domainkey-signature" in ctx.lower_names:
        ctx.flag("warn", t("forensics.flag.domainkey"))
    arc = []
    for n, v in ctx.headers:
        if n.lower() == "arc-seal":
            tags = _tags(v)
            arc.append({"i": tags.get("i"), "d": tags.get("d"), "s": tags.get("s"), "cv": tags.get("cv"), "t": tags.get("t")})
    return dkim, arc


def _identity(ctx: _Ctx, dkim: list[dict], auth: list[dict]) -> tuple[list[dict], str, list[str]]:
    """Identity fields and their domain alignment relative to From; also returns the List-Unsubscribe data."""
    from_addr, from_dom = _addr_domain(ctx.first("from"))
    from_reg = registrable_domain(from_dom)
    identity_rows = []

    def add_identity(field: str, value: str | None, domain: str | None) -> None:
        if not value and not domain:
            return
        reg = registrable_domain(domain)
        aligned = None if (not reg or not from_reg or field == "From") else (reg == from_reg)
        identity_rows.append({"field": field, "value": (value or "")[:120], "domain": domain, "aligned": aligned})

    add_identity("From", from_addr, from_dom)
    rt = ctx.first("reply-to")
    if rt:
        add_identity("Reply-To", *_addr_domain(rt))
    add_identity("Return-Path", *_addr_domain(ctx.first("return-path")))
    if ctx.first("sender"):
        add_identity("Sender", *_addr_domain(ctx.first("sender")))
    mid = ctx.first("message-id")
    if mid and "@" in mid:
        add_identity("Message-ID", mid, mid.rsplit("@", 1)[1].strip("> ").lower())
    for d in dkim:
        add_identity("DKIM (d=)", d["d"], (d["d"] or "").lower() or None)
    for a in auth:
        mf = a["details"].get("smtp.mailfrom")
        if mf:
            add_identity(f"{a['header']} smtp.mailfrom", mf, mf.rsplit("@", 1)[-1].lower())
    unsub_hdr = ctx.first("list-unsubscribe") or ""
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
        ctx.flag("warn", t("forensics.flag.misaligned", domain=from_reg, list=", ".join(sorted({f"{r['field']}={r['domain']}" for r in misaligned})[:6])))
    if rt and _addr_domain(rt)[1] and registrable_domain(_addr_domain(rt)[1]) != from_reg:
        ctx.flag("warn", t("forensics.flag.reply_to"))
    for dom in [from_dom] + [r["domain"] for r in identity_rows if r["domain"]]:
        if dom and (dom.startswith("xn--") or ".xn--" in dom or not dom.isascii()):
            ctx.flag("warn", t("forensics.flag.punycode", domain=dom))
            break
    return identity_rows, unsub_hdr, unsub_urls


def _timeline(ctx: _Ctx, received: list[dict]) -> list[dict]:
    timeline = []
    if ctx.date_dt:
        timeline.append({"event": t("forensics.date_declared"), "raw": ctx.first("date"), "_ts": ctx.date_dt})
    for r in reversed(received):
        if r["_ts"]:
            label = f"Received #{r['index']} ({r['by_host'] or '?'})"
            timeline.append({"event": label, "raw": r["time_utc"], "_ts": r["_ts"]})
    prev = None
    for row in timeline:
        row["utc"] = _fmt_utc(row["_ts"])
        row["delta_s"] = int((row["_ts"] - prev).total_seconds()) if prev else None
        prev = row["_ts"]
    if ctx.date_dt and received and received[0]["_ts"]:
        total = int((received[0]["_ts"] - ctx.date_dt).total_seconds())
        if total > 3600:
            ctx.flag("warn", t("forensics.flag.delay", h=total // 3600, m=(total % 3600) // 60))
        elif total < -300:
            ctx.flag("warn", t("forensics.flag.future_date"))
    for r in received:
        r.pop("_ts", None)
    for row in timeline:
        row.pop("_ts", None)
    return timeline


def _epochs(ctx: _Ctx) -> list[dict]:
    """Unix timestamps found in the Message-ID and in signature headers, converted to UTC."""
    mid = ctx.first("message-id")
    epochs = []

    def epoch_add(where: str, num: str) -> None:
        val = int(num)
        secs = val / 1000 if len(num) == 13 else val
        if not (946_684_800 <= secs <= 4_102_444_800):
            return
        dt = datetime.fromtimestamp(secs, tz=timezone.utc)
        epochs.append({"where": where, "value": num, "utc": _fmt_utc(dt),
                       "diff_vs_date_s": int((dt - ctx.date_dt).total_seconds()) if ctx.date_dt else None,
                       "unit": "ms" if len(num) == 13 else "s"})

    if mid:
        for num in re.findall(r"(?<!\d)(\d{13})(?!\d)", mid):
            epoch_add("Message-ID", num)
    for n, v in ctx.headers:
        if n.lower() in ("arc-seal", "arc-message-signature", "dkim-signature"):
            m = re.search(r"(?:^|;)\s*t\s*=\s*(\d{10})\b", v)
            if m:
                epoch_add(n, m.group(1))
    return epochs


def _mime_and_body(ctx: _Ctx, placeholders: list[str]) -> tuple[list[dict], list[dict], dict | None, list[str], list[str]]:
    """MIME tree, attachments, HTML audit, plain-text URLs and the template placeholders of headers plus body."""
    mime_rows: list[dict] = []
    mime_flag_texts: list[str] = []
    leaves: list[Message] = []
    _walk_mime(ctx.msg, 0, mime_rows, mime_flag_texts, leaves)
    for text in mime_flag_texts:
        ctx.flag("warn", text)

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
                ctx.flag("warn", t("forensics.flag.att_double_ext", name=fname[:60], apparent=apparent, ext=ext))
            elif ext in RISKY_EXTENSIONS:
                ctx.flag("warn", t("forensics.flag.att_risky", name=fname[:60], ext=ext))
            continue
        if ctype == "text/html":
            html_parts.append(_leaf_text(leaf))
        elif ctype == "text/plain":
            text_parts.append(_leaf_text(leaf))
    if html_parts and not text_parts:
        ctx.flag("info", t("forensics.flag.no_plain"))

    html_audit = _audit_html("\n".join(html_parts)) if html_parts else None
    body_blob = "\n".join(text_parts + html_parts)
    for rx in PLACEHOLDER_RES:
        placeholders += [m.group(0) for m in rx.finditer(body_blob)][:3]
    placeholders = list(dict.fromkeys(placeholders))[:8]
    if placeholders:
        ctx.flag("warn", t("forensics.flag.placeholders", list=", ".join(f"`{p[:30]}`" for p in placeholders[:5])))

    urls_plain = list(dict.fromkeys(re.findall(r"https?://[^\s<>\"')]+", "\n".join(text_parts))))[:15]
    return mime_rows, attachments, html_audit, urls_plain, placeholders


def _html_flags(ctx: _Ctx, html_audit: dict | None) -> None:
    """Findings about hidden content, forms, scripts, tracking pixels and links of the HTML part."""
    if html_audit:
        h = html_audit
        if h["hidden"]:
            techs = sorted({tech for rec in h["hidden"] for tech in rec["techniques"]})
            ctx.flag("warn", t("forensics.flag.hidden", n=len(h["hidden"]), chars=h["hidden_text_total"], techniques=", ".join(techs)))
        if h["comment_chars"] > 500:
            ctx.flag("warn", t("forensics.flag.big_comment", chars=h["comment_chars"], count=h["comment_count"]))
        if h["mixed_case_tags"]:
            ctx.flag("warn", t("forensics.flag.mixed_case", list=", ".join(f"`{tag}`" for tag in h["mixed_case_tags"][:4])))
        if h["unknown_tag_count"] >= 5:
            ctx.flag("warn", t("forensics.flag.unknown_tags", n=h["unknown_tag_count"], list=", ".join(f"`{tag}`" for tag in h["unknown_tags"][:3])))
        if h["wrapped_anchor"]:
            ctx.flag("warn", t("forensics.flag.wrapped_anchor"))
        for kind, cnt in ((t("forensics.kind.form"), h["forms"]), (t("forensics.kind.script"), h["scripts"]), ("iframe", h["iframes"]), ("object/embed", h["objects"])):
            if cnt:
                ctx.flag("warn", t("forensics.flag.contains", kind=kind, n=cnt))
        tracking = [i for i in h["images"] if i["tracking_hint"]]
        if tracking:
            ctx.flag("info", t("forensics.flag.tracking", n=len(tracking)))
        # Identical findings for repeated links (mailers repeat the same link many times) are reported once with a count.
        link_findings: dict[tuple[str, str], int] = {}
        for link in h["links"]:
            found = []
            if link["text_host_mismatch"]:
                found.append(("warn", t("forensics.flag.link_mismatch", text=link["text"][:40], host=link["host"])))
            if link["scheme"] == "http":
                found.append(("info", t("forensics.flag.link_http", host=(link["host"] or "")[:50])))
            if link["abused_host"]:
                found.append(("info", t("forensics.flag.link_abused", host=link["host"])))
            if link["shortener"]:
                found.append(("warn", t("forensics.flag.link_shortener", host=link["host"])))
            for key in found:
                link_findings[key] = link_findings.get(key, 0) + 1
        for (level, text), count in link_findings.items():
            ctx.flag(level, text if count == 1 else text.rstrip(".") + " " + t("forensics.flag.times", n=count) + ".")
        if any(link["query_params"] >= 4 for link in h["links"]):
            ctx.flag("info", t("forensics.flag.link_params"))


def _ips(ctx: _Ctx, received: list[dict]) -> list[dict]:
    ips = []
    for r in received:
        if r["ip"]:
            ips.append({"ip": r["ip"], "where": f"Received #{r['index']}", "is_private": r["is_private"]})
    for name in ("x-originating-ip", "x-sender-ip"):
        v = ctx.first(name)
        if v:
            candidate = v.strip("[] ")[:45]
            parsed = parse_ip(candidate)
            ips.append({"ip": candidate, "where": name, "is_private": is_special_ip(parsed) if parsed else None})
    if ctx.first("x-originating-ip"):
        ctx.flag("info", t("forensics.flag.x_originating"))

    # ctx.headers with names used by the recipient/provider that sit BELOW all the Received ctx.headers
    if len(received) > 1:
        last_recv_idx = max(i for i, (n, _) in enumerate(ctx.headers) if n.lower() == "received")
        below = {
            n for n, _ in ctx.headers[last_recv_idx + 1:]
            if n.lower().startswith(("x-google-", "x-original-sender", "envelope-to", "x-gm-", "delivered-to"))
        }
        if below:
            ctx.flag("warn", t("forensics.flag.below_received", list=", ".join(sorted(below)[:6])))
    return ips


def compute_facts(src: str) -> dict:
    """Deterministic analysis of an e-mail source; the sections below are called in a fixed order (see _Ctx)."""
    ctx = _Ctx(src)
    overview = _overview(ctx)
    dup, casing_variants, encoded_words, placeholders = _header_hygiene(ctx)
    received, single_operator, trust_note, trust_index = _received_hops(ctx)
    auth = _authentication(ctx, received)
    dkim, arc = _dkim_arc(ctx)
    identity_rows, unsub_hdr, unsub_urls = _identity(ctx, dkim, auth)
    timeline = _timeline(ctx, received)
    epochs = _epochs(ctx)
    mime_rows, attachments, html_audit, urls_plain, placeholders = _mime_and_body(ctx, placeholders)
    _html_flags(ctx, html_audit)
    if unsub_hdr and not ctx.first("list-unsubscribe-post"):
        ctx.flag("info", t("forensics.flag.unsub"))
    filters = _extract_filters(ctx.headers, ctx.flag)
    ips = _ips(ctx, received)

    return {
        "overview": overview,
        "flags": ctx.flags,
        "received": received,
        "trust_note": trust_note,
        "single_operator": single_operator,
        "trust_index": trust_index,
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
        "list_unsubscribe": {"urls": [u[:200] for u in unsub_urls[:5]], "one_click": bool(ctx.first("list-unsubscribe-post"))},
        "ips": ips,
    }
