from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.email_parser import extract_body_excerpt, extract_relevant_headers, parse_email
from backend.report_builder import ABUSEIPDB_CATEGORIES, build_comment, validate_hard_checks
from backend.report_utils import sanitize_comment, truncate_chars
from backend.services.abuseipdb import AbuseIpdbService
from backend.services.llm_analyzer import llm_analyzer
from backend.storage import append_report_log

router = APIRouter()

abuseipdb_service = AbuseIpdbService()


class EmailAnalyzeRequest(BaseModel):
    raw_email: str
    use_llm: bool = True


class ReportFields(BaseModel):
    ip: str
    categories: list[int]
    attack_timestamp: str | None = None
    comment: str = ""


def _fallback_comment(facts: dict) -> str:
    """Deterministyczny komentarz używany tylko gdy LLM jest niedostępny/zawiedzie -
    budowany wprost z faktów wyekstrahowanych z e-maila, nie z pól formularza."""
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


@router.post("/email/analyze")
async def analyze_email(req: EmailAnalyzeRequest):
    facts = parse_email(req.raw_email)

    llm_analysis = None
    if req.use_llm and llm_analyzer.is_configured():
        llm_analysis = await llm_analyzer.analyze_email(
            facts,
            extract_relevant_headers(req.raw_email),
            extract_body_excerpt(req.raw_email),
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
        "categories": ABUSEIPDB_CATEGORIES,
        "llm_configured": llm_analyzer.is_configured(),
        "llm_analysis": llm_analysis,
        "usage": usage,
        "report_comment": report_comment,
    }


@router.post("/report/preview")
async def preview_report(fields: ReportFields):
    checks = validate_hard_checks(fields.ip, fields.attack_timestamp, fields.categories)
    return {"checks": checks}


@router.post("/report/submit")
async def submit_report(fields: ReportFields):
    checks = validate_hard_checks(fields.ip, fields.attack_timestamp, fields.categories)
    if not checks["all_passed"]:
        raise HTTPException(status_code=400, detail={"message": "twarde sprawdzenia nie przeszły", "checks": checks})

    if not abuseipdb_service.is_configured():
        raise HTTPException(status_code=400, detail="brak klucza AbuseIPDB API")

    comment = truncate_chars(sanitize_comment(fields.comment))
    timestamp = fields.attack_timestamp or datetime.now(timezone.utc).isoformat()

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
        raise HTTPException(status_code=502, detail=f"błąd AbuseIPDB API: {exc}")

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
