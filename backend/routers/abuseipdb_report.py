"""AbuseIPDB tab: preparing and sending an abuse report (https://docs.abuseipdb.com/#report-endpoint).

/email/analyze: facts from the pasted e-mail, the address candidates, an optional LLM opinion and a comment draft.
Then /ip-info (what AbuseIPDB already knows), /report/preview (hard checks, personal-data scan and the exact API
payload), /report/redact, /report/submit and /report/history (the local log with the daily limit). The hard checks
(age, IP, category) and the 15-minute cooldown are always validated here, never only in the frontend; the API's own
refusals (quota, repeat rule, invalid data, key) are turned into readable errors.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import MAX_SOURCE_CHARS
from backend.email_parser import (
    extract_addresses,
    parse_email,
    parse_message,
)
from backend.email_forensics import normalize_source, prepare_for_llm
from backend.i18n import current_lang, t
from backend.report_builder import ABUSEIPDB_CATEGORIES, build_comment, local_assessment, validate_hard_checks
from backend.report_utils import (
    find_pii,
    is_reportable_ip,
    own_identifiers,
    redact_pii,
    sanitize_comment,
    truncate_chars,
)
from backend.services.abuseipdb import AbuseIpdbError, AbuseIpdbService
from backend.services.llm_analyzer import llm_analyzer
from backend.storage import append_report_log, load_report_log, successful_reports

router = APIRouter()

abuseipdb_service = AbuseIpdbService()


# AbuseIPDB accepts a repeated report of the same IP from the same account only after this many minutes
REPORT_COOLDOWN_MINUTES = 15
RECENT_DAYS = 7  # window of "already reported recently" shown before a report


def _previous_reports(ip: str) -> dict:
    """Own earlier reports of this IP (from the local log) and whether the AbuseIPDB cooldown still applies."""
    entries = successful_reports(ip)
    if not entries:
        return {"count": 0, "last_submitted_at": None, "cooldown_left_minutes": 0}
    last = entries[0]["submitted_at"]
    elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(last)
    left = max(0, REPORT_COOLDOWN_MINUTES - int(elapsed / timedelta(minutes=1)))
    return {"count": len(entries), "last_submitted_at": last, "cooldown_left_minutes": left}


class EmailAnalyzeRequest(BaseModel):
    raw_email: str = Field(max_length=MAX_SOURCE_CHARS)
    use_llm: bool = True


class ReportFields(BaseModel):
    ip: str
    categories: list[int]
    attack_timestamp: str | None = None
    comment: str = ""
    own_terms: list[str] = Field(default_factory=list, max_length=20)  # the reporter's identifiers, for the PII scan


class RedactRequest(BaseModel):
    comment: str = Field(max_length=5000)
    own_terms: list[str] = Field(default_factory=list, max_length=20)


def _reported_ips() -> set[str]:
    return {e["ip"] for e in load_report_log() if e.get("success")}


def _ip_candidates(facts: dict, llm: dict | None) -> list[dict]:
    """Every public address the message mentions in its Received chain (and the one the model suggests instead), so
    that the user can pick another one to report. Only the boundary hop is a real sender; the other hops are usually
    the recipient's or the provider's own infrastructure."""
    reported = _reported_ips()
    out: list[dict] = []

    def add(ip: str | None, role: str, host: str | None = None) -> None:
        if ip and ip not in {c["ip"] for c in out} and is_reportable_ip(ip)[0]:
            out.append({"ip": ip, "role": role, "host": host, "reported": ip in reported})

    for hop in facts.get("received_chain") or []:
        add(hop.get("ip"), "boundary" if hop.get("is_boundary") else "hop", hop.get("from_host"))
    if llm and not llm.get("error"):
        add((llm.get("source_ip_check") or {}).get("suggested_ip"), "llm")
    return out


def _fallback_comment(facts: dict) -> str:
    """Deterministic comment used only when the LLM is unavailable or fails - built directly from the facts
    extracted from the e-mail, not from the form fields."""
    ransom = None
    if facts.get("btc_addresses_found"):
        ransom = {"wallet": facts["btc_addresses_found"][0]}
    elif facts.get("ransom_keywords_found"):
        ransom = {"amount": None}
    return build_comment(
        facts.get("trusted_source_ip") or "?",
        facts.get("spoofing_suspected", False),
        facts.get("attachments") or [],
        ransom,
        facts.get("message_id"),
    )


_IP_PORT_RE = re.compile(r"(\b\d{1,3}(?:\.\d{1,3}){3}):\d{1,5}\b")
_PORT_MENTION_RE = re.compile(r"\bports?\b\W{0,3}\d", re.IGNORECASE)


def _strip_ports(comment: str) -> str:
    """The LLM cannot know which port was attacked (an e-mail carries no such fact), so any port it wrote is
    removed: whole sentences that name a port and `ip:port` suffixes."""
    comment = _IP_PORT_RE.sub(r"\1", comment)
    return " ".join(s for s in re.split(r"(?<=[.!?])\s+", comment) if not _PORT_MENTION_RE.search(s))


def _api_timestamp(value: str | None) -> str:
    """ISO 8601 in UTC without fractions (e.g. 2026-09-25T07:04:00+00:00) - the plainest form the API accepts."""
    if value:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = datetime.now(timezone.utc)
    return ts.astimezone(timezone.utc).replace(microsecond=0).isoformat()


@router.post("/email/analyze")
async def analyze_email(req: EmailAnalyzeRequest):
    msg = parse_message(req.raw_email)
    facts = parse_email(msg)

    # The model gets the same prepared source as the Email tab (text parts decoded from base64, binary parts replaced
    # by a size + sha256 marker, headers untouched). The facts above are still computed from the original source.
    prepared, _prep_notes = prepare_for_llm(normalize_source(req.raw_email))

    llm_analysis = None
    if req.use_llm and llm_analyzer.is_configured():
        llm_analysis = await llm_analyzer.analyze_email(
            facts,
            prepared,
            current_lang(),
        )

    usage = llm_analysis.pop("_usage", None) if isinstance(llm_analysis, dict) else None

    report_comment = None
    if llm_analysis and not llm_analysis.get("error") and llm_analysis.get("report_comment"):
        report_comment = llm_analysis["report_comment"]
    if not report_comment:
        report_comment = _fallback_comment(facts)
    report_comment = truncate_chars(sanitize_comment(_strip_ports(report_comment)))

    addr = extract_addresses(msg)
    return {
        "facts": facts,
        "ip_candidates": _ip_candidates(facts, llm_analysis),
        "own_terms": own_identifiers(addr["recipients"]),
        "local_assessment": local_assessment(msg, facts),
        "categories": ABUSEIPDB_CATEGORIES,
        "llm_configured": llm_analyzer.is_configured(),
        "llm_analysis": llm_analysis,
        "usage": usage,
        "llm_input": {"chars": len(prepared)},
        "report_comment": report_comment,
    }


@router.get("/categories")
def categories():
    """AbuseIPDB category table (id -> name), single source of truth for the frontend chips."""
    return ABUSEIPDB_CATEGORIES


@router.post("/report/preview")
async def preview_report(fields: ReportFields):
    checks = validate_hard_checks(fields.ip, fields.attack_timestamp, fields.categories)
    comment = truncate_chars(sanitize_comment(fields.comment))
    return {
        "checks": checks,
        "previous": _previous_reports(fields.ip),
        "pii": find_pii(comment, fields.own_terms),
        "payload": {
            "ip": fields.ip,
            "categories": sorted(set(fields.categories)),
            "timestamp": _api_timestamp(fields.attack_timestamp) if checks["age_ok"] else None,
            "comment": comment,
        },
    }


@router.post("/report/redact")
async def redact(req: RedactRequest):
    """The comment with the reporter's identifiers, other e-mail addresses and internal IPs replaced by placeholders."""
    return {"comment": truncate_chars(sanitize_comment(redact_pii(req.comment, req.own_terms)))}


@router.get("/report/history")
async def report_history(limit: int = 100):
    """The local log of report attempts (newest first) with the number sent today (UTC) and the last rate limit
    the API told us about."""
    entries = load_report_log()
    today = datetime.now(timezone.utc).date().isoformat()
    sent_today = sum(1 for e in entries if e.get("success") and str(e.get("submitted_at", "")).startswith(today))
    last_limit = next((e["rate_limit"] for e in entries if e.get("rate_limit")), None)
    return {"entries": entries[: max(1, min(limit, 500))], "sent_today": sent_today, "rate_limit": last_limit}


@router.get("/ip-info")
async def ip_info(ip: str):
    """What AbuseIPDB already knows about the IP (last 90 days), shown before reporting it."""
    ok, _ = is_reportable_ip(ip)
    if not ok or not abuseipdb_service.is_configured():
        return {"status": "unavailable"}
    result = await abuseipdb_service.query_ip(ip)
    if result.status != "ok":
        return {"status": "unavailable"}
    s = result.summary
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)).isoformat()
    verbose = ((result.raw or {}).get("data") or {}).get("reports") or []
    recent = [
        {"reported_at": r.get("reportedAt"), "categories": r.get("categories") or []}
        for r in verbose
        if (r.get("reportedAt") or "") >= cutoff
    ]
    return {
        "status": "ok",
        "total_reports": s.get("total_reports"),
        "num_distinct_users": s.get("num_distinct_users"),
        "abuse_confidence_score": s.get("abuse_confidence_score"),
        "last_reported_at": s.get("last_reported_at"),
        "is_whitelisted": s.get("is_whitelisted"),
        "isp": s.get("isp"),
        "usage_type": s.get("usage_type"),
        "country_code": s.get("country_code"),
        "recent_reports": recent,
        "recent_days": RECENT_DAYS,
    }


@router.post("/report/submit")
async def submit_report(fields: ReportFields):
    checks = validate_hard_checks(fields.ip, fields.attack_timestamp, fields.categories)
    if not checks["all_passed"]:
        raise HTTPException(status_code=400, detail={"message": t("report.hard_checks_failed"), "checks": checks})

    if not abuseipdb_service.is_configured():
        raise HTTPException(status_code=400, detail=t("report.no_key"))

    left = _previous_reports(fields.ip)["cooldown_left_minutes"]
    if left:
        raise HTTPException(status_code=409, detail=t("report.cooldown", minutes=left, limit=REPORT_COOLDOWN_MINUTES))

    comment = truncate_chars(sanitize_comment(fields.comment))
    timestamp = _api_timestamp(fields.attack_timestamp)
    categories = sorted(set(fields.categories))
    record = {
        "id": uuid4().hex,
        "ip": fields.ip,
        "categories": categories,
        "comment": comment,
        "attack_timestamp": timestamp,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result, rate_limit = await abuseipdb_service.submit_report(fields.ip, categories, comment, timestamp)
    except AbuseIpdbError as exc:
        append_report_log({**record, "success": False, "error": str(exc), "rate_limit": exc.rate_limit or None})
        raise HTTPException(status_code=_error_status(exc), detail=_error_text(exc)) from exc
    except Exception as exc:
        append_report_log({**record, "success": False, "error": str(exc)})
        raise HTTPException(status_code=502, detail=t("report.api_error", message=exc)) from exc

    data = result.get("data") or {}
    append_report_log(
        {**record, "success": True, "result": result, "abuse_confidence_score": data.get("abuseConfidenceScore"), "rate_limit": rate_limit or None}
    )
    return {"success": True, "result": result, "rate_limit": rate_limit}


def _is_daily_limit(exc: AbuseIpdbError) -> bool:
    """A 429 is either the daily quota (the API then reports no requests left) or the same-IP repeat rule."""
    if exc.rate_limit.get("remaining") == 0:
        return True
    return "daily" in exc.detail.lower() and "once in" not in exc.detail.lower()


def _error_status(exc: AbuseIpdbError) -> int:
    """Our status for an API error: 429 quota, 409 repeat of the same IP, 422 refused input, 401/403 key, else 502."""
    if exc.status == 429:
        return 429 if _is_daily_limit(exc) else 409
    if exc.status in (401, 403):
        return 401
    return 422 if exc.status == 422 else 502


def _error_text(exc: AbuseIpdbError) -> str:
    if exc.status == 429:
        if _is_daily_limit(exc):
            reset = exc.rate_limit.get("reset")
            when = datetime.fromtimestamp(reset, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if reset else "?"
            return t("report.daily_limit", when=when, limit=exc.rate_limit.get("limit") or "?")
        return t("report.duplicate_remote", limit=REPORT_COOLDOWN_MINUTES)
    if exc.status in (401, 403):
        return t("report.key_rejected")
    if exc.status == 422:
        return t("report.rejected", message=exc.detail)
    return t("report.api_error", message=exc)
