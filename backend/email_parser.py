from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from email import message_from_string
from email.message import Message
from email.utils import parsedate_to_datetime

_BTC_RE = re.compile(r"\b(bc1[a-z0-9]{25,39}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
_RANSOM_KEYWORDS = ("bitcoin", "btc", "ransom", "payment", "wallet", "crypto", "decrypt")
_FROM_BY_RE = re.compile(r"from\s+(?P<from>.+?)\s+by\s+(?P<by>\S+)", re.IGNORECASE)
_PAREN_RE = re.compile(r"\(([^)]+)\)")
_BRACKET_RE = re.compile(r"\[([^\]]+)\]")
_HEADER_START_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:")
_INDENTED_HEADER_START_RE = re.compile(r"^\s+([A-Za-z][A-Za-z0-9-]*:\s)")

AGE_LIMIT_DAYS = 60


def _refold_headers(raw_email: str) -> str:
    """Wiele klientów pocztowych/przeglądarek przy "pokaż źródło" gubi wcięcia linii
    kontynuacji (RFC 5322 folding) długich nagłówków - zwłaszcza wielolinijkowych
    `Received`. Dla stdlib `email` linia bez wiodącej spacji, która nie wygląda jak
    `Nazwa-Nagłówka:`, oznacza koniec bloku nagłówków - więc taki wklejony e-mail
    potrafi urwać parsowanie już na pierwszym nagłówku. Douzupełniamy brakujące
    wcięcie tam, gdzie to jednoznaczne (linia w bloku nagłówków, niepusta, nie
    zaczyna się od `Nazwa:` ani od białego znaku). Odwrotny przypadek też się zdarza -
    kolejny nagłówek bywa błędnie wcięty (np. przez narzędzie do wklejania zachowujące
    zagnieżdżenie) - taką linię rozpoznajemy po wzorcu `Nazwa:` mimo wcięcia i cofamy
    wcięcie, żeby stdlib potraktował ją jako nowy nagłówek, a nie kontynuację."""
    lines = raw_email.split("\n")
    out: list[str] = []
    in_headers = True
    for line in lines:
        if in_headers and line.strip() == "":
            in_headers = False
            out.append(line)
            continue
        if in_headers and line.startswith((" ", "\t")):
            indented_header = _INDENTED_HEADER_START_RE.match(line)
            out.append(line.lstrip() if indented_header else line)
        elif in_headers and out and not _HEADER_START_RE.match(line):
            out.append(" " + line)
        else:
            out.append(line)
    return "\n".join(out)


def _parse_ip(candidate: str | None) -> str | None:
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate.strip()))
    except ValueError:
        return None


def _is_special_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def _extract_ip_candidates(text: str) -> list[str]:
    """Zbiera wszystkie adresy IP wspomniane w klauzuli "from" nagłówka Received - zarówno
    w formie [IP] (konwencja MTA na rDNS/prawdziwe IP), jak i w zwykłych nawiasach (bywają
    tam też same nazwy hostów typu "HELO foo", które nie sparsują się jako IP i odpadną).
    Adresy publiczne mają pierwszeństwo nad loopbackiem/prywatnymi - MTA takie jak Microsoft
    EOP potrafią zapisać `[127.0.0.1] (prawdziwe_ip)`, gdzie to właśnie nawias, nie nawias
    kwadratowy, niesie realny adres nadawcy."""
    candidates = []
    for pattern in (_BRACKET_RE, _PAREN_RE):
        for m in pattern.finditer(text):
            ip = _parse_ip(m.group(1))
            if ip:
                candidates.append(ip)
    public = [ip for ip in candidates if not _is_special_ip(ip)]
    return public or candidates


def _parse_received_header(raw_header: str) -> dict:
    normalized = re.sub(r"\s+", " ", raw_header).strip()
    match = _FROM_BY_RE.search(normalized)
    from_raw = match.group("from") if match else ""
    by_host = match.group("by").rstrip(";,") if match else None
    from_host = from_raw.split(" ", 1)[0].strip("[]") if from_raw else None
    candidates = _extract_ip_candidates(from_raw)
    ip = candidates[0] if candidates else _parse_ip(from_host)
    return {"raw": normalized, "from_host": from_host, "by_host": by_host, "ip": ip, "is_boundary": False}


def _registrable_domain(host: str | None) -> str | None:
    """Ostatnie 2 człony nazwy hosta (np. 'sub.foo.outlook.com' -> 'outlook.com').
    Zwraca None dla adresów IP (nie da się dla nich ustalić "domeny zaufania")."""
    if not host or _parse_ip(host) is not None:
        return None
    labels = host.lower().split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host.lower()


def _find_boundary_hop(received_headers: list[str]) -> tuple[dict | None, list[dict], str, str]:
    """Nagłówki Received są dopisywane na górze przy każdym hopie, więc `received_headers[0]`
    to najnowszy (ostatnia dostawa), a najstarszy (pierwsze wejście do sieci) jest na końcu listy.
    W łańcuchu wielohopowym jednego dostawcy (np. Microsoft 365) większość początkowych hopów to
    transfery wewnętrzne między jego własnymi serwerami - mogą używać adresów IP formalnie
    "publicznych" (nie RFC1918/loopback), więc samo sprawdzenie "czy IP jest prywatne" ich nie
    odsieje. Zamiast tego idziemy od najnowszego hopu w dół i porównujemy domenę hosta "from" z
    domeną hosta "by" pierwszego hopu (przyjętą jako zaufana) - dopóki się zgadzają, to hop
    wewnętrzny. Pierwszy hop, w którym się rozjeżdżają (albo "from" to sam adres IP/placeholder typu
    [127.0.0.1], co jest typowym zapisem bramki pocztowej dla faktycznie łączącego się klienta) to
    granica zaufanej infrastruktury - jego IP jest tym, które warto zgłaszać."""
    hops = [_parse_received_header(h) for h in received_headers]
    if not hops:
        return None, [], "low", "Brak nagłówków Received w e-mailu."

    trusted_suffix = _registrable_domain(hops[0]["by_host"])
    boundary_index = len(hops) - 1
    left_trusted_domain = False
    for i, hop in enumerate(hops):
        if trusted_suffix and _registrable_domain(hop["from_host"]) == trusted_suffix:
            continue
        boundary_index = i
        left_trusted_domain = True
        break

    # Hop graniczny może nie mieć rozpoznanego IP (np. nietypowy format nagłówka) - w takim
    # przypadku szukamy dalej w stronę najstarszych hopów, gdzie IP jednak się pojawi.
    ip_index = boundary_index
    while ip_index < len(hops) and hops[ip_index]["ip"] is None:
        ip_index += 1
    if ip_index == len(hops):
        ip_index = boundary_index

    hops[ip_index]["is_boundary"] = True
    boundary = hops[ip_index]

    if boundary["ip"] is None:
        confidence = "low"
        reasoning = "Nie udało się wyłuskać adresu IP z żadnego nagłówka Received - zweryfikuj ręcznie."
    elif left_trusted_domain:
        confidence = "high"
        reasoning = (
            f"Hop graniczny: 'from {boundary['from_host']}' nie należy już do zaufanej domeny "
            f"'{trusted_suffix}' (wyznaczonej z nagłówka 'by' najnowszego hopu) - to pierwsze "
            "miejsce w łańcuchu, gdzie własna infrastruktura odbiorcy zapisuje adres faktycznie "
            "łączącego się nadawcy."
        )
    elif trusted_suffix is None:
        confidence = "medium"
        reasoning = "Pojedynczy nagłówek Received, bez rozpoznawalnej domeny 'by' - przyjęto jego IP wprost."
    else:
        confidence = "low"
        reasoning = (
            f"Cały łańcuch Received pozostaje w domenie '{trusted_suffix}' - nie znaleziono "
            "jednoznacznej granicy zaufanej infrastruktury, przyjęto najstarszy hop jako najbardziej "
            "prawdopodobny. Zweryfikuj ręcznie."
        )

    return boundary, hops, confidence, reasoning


def _parse_auth_results(header_value: str) -> dict[str, str]:
    out = {}
    for mechanism in ("spf", "dkim", "dmarc"):
        m = re.search(rf"{mechanism}=(\w+)", header_value, re.IGNORECASE)
        if m:
            out[mechanism] = m.group(1).lower()
    return out


_COMMON_DISPLAY_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv",
    "jpg", "jpeg", "png", "gif", "bmp", "zip", "rar",
}


def _extract_attachments(msg: Message) -> list[dict]:
    """`declared_extension` to prawdziwe (ostatnie) rozszerzenie pliku. `apparent_extension`
    wykrywa klasyczny trik phishingowy z podwójnym rozszerzeniem (np. "faktura.pdf.exe") -
    ustawiane tylko gdy przedostatni segment nazwy wygląda jak popularne, "niewinne"
    rozszerzenie dokumentu/obrazu, inne niż to prawdziwe."""
    attachments = []
    for part in msg.walk():
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        segments = filename.split(".")
        declared_ext = segments[-1].lower() if len(segments) > 1 else ""
        apparent_ext = None
        if len(segments) > 2:
            candidate = segments[-2].lower()
            if candidate in _COMMON_DISPLAY_EXTENSIONS and candidate != declared_ext:
                apparent_ext = candidate
        attachments.append(
            {
                "filename": filename,
                "size_bytes": len(payload),
                "content_type": part.get_content_type(),
                "declared_extension": declared_ext,
                "apparent_extension": apparent_ext,
            }
        )
    return attachments


def _extract_body_text(msg: Message) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                try:
                    parts.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore"))
                except Exception:
                    continue
        return "\n".join(parts)
    try:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
    except Exception:
        return ""


_LLM_RELEVANT_HEADERS = ("Received", "Received-SPF", "Authentication-Results", "Date", "From", "Message-ID")


def extract_relevant_headers(raw_email: str) -> str:
    """Zwięzły blok nagłówków istotnych do weryfikacji łańcucha dostawy (Received i
    uwierzytelnianie) - bez treści e-maila i bez szumu w postaci wielkich, nieistotnych
    bloków (np. base64 X-Microsoft-Antispam-Message-Info). Używane jako dowód wysyłany
    opcjonalnej warstwie LLM do niezależnej weryfikacji hopu granicznego."""
    msg = message_from_string(_refold_headers(raw_email))
    lines = []
    for name in _LLM_RELEVANT_HEADERS:
        for value in msg.get_all(name) or []:
            lines.append(f"{name}: " + re.sub(r"\s+", " ", value).strip())
    return "\n".join(lines)


def parse_email(raw_email: str) -> dict:
    msg = message_from_string(_refold_headers(raw_email))

    received_headers = msg.get_all("Received") or []
    boundary_hop, hop_chain, ip_confidence, ip_reasoning = _find_boundary_hop(received_headers)
    trusted_ip = boundary_hop["ip"] if boundary_hop else None

    auth_header = msg.get("Authentication-Results", "")
    auth_results = _parse_auth_results(auth_header)

    date_header = msg.get("Date")
    date_parsed = None
    age_days = None
    if date_header:
        try:
            date_parsed = parsedate_to_datetime(date_header)
            if date_parsed.tzinfo is None:
                date_parsed = date_parsed.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - date_parsed).days
        except (TypeError, ValueError):
            pass

    body = _extract_body_text(msg)
    btc_matches = sorted(set(_BTC_RE.findall(body)))
    ransom_hint = any(kw in body.lower() for kw in _RANSOM_KEYWORDS)

    ip_ok, ip_reject_reason = (True, None)
    if trusted_ip:
        try:
            ip = ipaddress.ip_address(trusted_ip)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                ip_ok, ip_reject_reason = False, "adres prywatny/zarezerwowany"
        except ValueError:
            ip_ok, ip_reject_reason = False, "nieprawidłowy adres IP"
    else:
        ip_ok, ip_reject_reason = False, "nie znaleziono wiarygodnego publicznego IP w łańcuchu Received"

    age_ok = age_days is not None and age_days <= AGE_LIMIT_DAYS

    return {
        "trusted_source_ip": trusted_ip,
        "ip_ok": ip_ok,
        "ip_reject_reason": ip_reject_reason,
        "ip_confidence": ip_confidence,
        "ip_reasoning": ip_reasoning,
        "received_chain": [
            {"from_host": h["from_host"], "ip": h["ip"], "by_host": h["by_host"], "is_boundary": h["is_boundary"]}
            for h in hop_chain
        ],
        "from": msg.get("From"),
        "to": msg.get("To"),
        "subject": msg.get("Subject"),
        "message_id": msg.get("Message-ID"),
        "date": date_header,
        "date_parsed": date_parsed.isoformat() if date_parsed else None,
        "age_days": age_days,
        "age_ok": age_ok,
        "spf": auth_results.get("spf"),
        "dkim": auth_results.get("dkim"),
        "dmarc": auth_results.get("dmarc"),
        "spoofing_suspected": auth_results.get("spf") == "fail" or auth_results.get("dmarc") == "fail",
        "attachments": _extract_attachments(msg),
        "btc_addresses_found": btc_matches,
        "ransom_keywords_found": ransom_hint,
    }
