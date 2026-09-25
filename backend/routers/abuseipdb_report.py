from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.i18n import current_lang, t
from backend.email_parser import BODY_EXCERPT_LIMIT, body_text_length, extract_body_excerpt, extract_relevant_headers, parse_email
from backend.report_builder import ABUSEIPDB_CATEGORIES, build_comment, local_assessment, validate_hard_checks
from backend.report_utils import is_reportable_ip, sanitize_comment, truncate_chars
from backend.services.abuseipdb import AbuseIpdbService
from backend.services.llm_analyzer import llm_analyzer
from backend.storage import append_report_log, successful_reports

router = APIRouter()

abuseipdb_service = AbuseIpdbService()


# AbuseIPDB accepts a repeated report of the same IP from the same account only after this many minutes
REPORT_COOLDOWN_MINUTES = 15


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
    raw_email: str
    use_llm: bool = True


class ReportFields(BaseModel):
    ip: str
    categories: list[int]
    attack_timestamp: str | None = None
    comment: str = ""


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
    facts = parse_email(req.raw_email)
    body_chars = body_text_length(req.raw_email)

    llm_analysis = None
    if req.use_llm and llm_analyzer.is_configured():
        llm_analysis = await llm_analyzer.analyze_email(
            facts,
            extract_relevant_headers(req.raw_email),
            extract_body_excerpt(req.raw_email),
            current_lang(),
        )

    usage = llm_analysis.pop("_usage", None) if isinstance(llm_analysis, dict) else None

    report_comment = None
    if llm_analysis and not llm_analysis.get("error") and llm_analysis.get("report_comment"):
        report_comment = llm_analysis["report_comment"]
    if not report_comment:
        report_comment = _fallback_comment(facts)
    report_comment = truncate_chars(sanitize_comment(report_comment))

    return {
        "facts": facts,
        "local_assessment": local_assessment(req.raw_email, facts),
        "categories": ABUSEIPDB_CATEGORIES,
        "llm_configured": llm_analyzer.is_configured(),
        "llm_analysis": llm_analysis,
        "usage": usage,
        "llm_input": {"body_chars": body_chars, "body_limit": BODY_EXCERPT_LIMIT},
        "report_comment": report_comment,
    }


@router.post("/report/preview")
async def preview_report(fields: ReportFields):
    checks = validate_hard_checks(fields.ip, fields.attack_timestamp, fields.categories)
    return {"checks": checks, "previous": _previous_reports(fields.ip)}


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
    return {
        "status": "ok",
        "total_reports": s.get("total_reports"),
        "num_distinct_users": s.get("num_distinct_users"),
        "abuse_confidence_score": s.get("abuse_confidence_score"),
        "last_reported_at": s.get("last_reported_at"),
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

    try:
        result = await abuseipdb_service.submit_report(fields.ip, fields.categories, comment, timestamp)
    except Exception as exc:
        append_report_log(
            {
                "ip": fields.ip,
                "categories": fields.categories,
                "comment": comment,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "success": False,
                "error": str(exc),
            }
        )
        raise HTTPException(status_code=502, detail=t("report.api_error", message=exc))

    append_report_log(
        {
            "ip": fields.ip,
            "categories": fields.categories,
            "comment": comment,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "result": result,
        }
    )
    return {"success": True, "result": result}
