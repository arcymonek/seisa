from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.email_parser import extract_relevant_headers, parse_email
from backend.report_builder import ABUSEIPDB_CATEGORIES, build_comment, validate_hard_checks
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
    spoofing_confirmed: bool = False
    attachments: list[dict] = []
    ransom: dict | None = None
    message_id: str | None = None


class AssistRequest(BaseModel):
    ip: str
    categories: list[int] = []
    attachments: list[dict] = []
    ransom: dict | None = None
    facts: dict | None = None
    prompt: str = ""


@router.post("/email/analyze")
async def analyze_email(req: EmailAnalyzeRequest):
    facts = parse_email(req.raw_email)

    llm_analysis = None
    if req.use_llm and llm_analyzer.is_configured():
        llm_analysis = await llm_analyzer.analyze_email(facts, extract_relevant_headers(req.raw_email))

    return {
        "facts": facts,
        "categories": ABUSEIPDB_CATEGORIES,
        "llm_configured": llm_analyzer.is_configured(),
        "llm_analysis": llm_analysis,
    }


@router.post("/report/preview")
async def preview_report(fields: ReportFields):
    checks = validate_hard_checks(fields.ip, fields.attack_timestamp, fields.categories)
    comment = build_comment(
        fields.ip,
        fields.spoofing_confirmed,
        fields.attachments,
        fields.ransom,
        fields.message_id,
    )
    return {"comment": comment, "checks": checks}


@router.post("/report/assist")
async def assist_report(req: AssistRequest):
    if not llm_analyzer.is_configured():
        return {"configured": False, "checklist": None, "answer": None}

    context = {
        "ip": req.ip,
        "categories": [{"id": c, "name": ABUSEIPDB_CATEGORIES.get(c, "nieznana")} for c in req.categories],
        "attachments": req.attachments,
        "ransom": req.ransom,
        "facts_from_email": req.facts,
    }
    result = await llm_analyzer.assist_report(context, req.prompt)
    if result is None:
        return {"configured": False, "checklist": None, "answer": None}
    if "error" in result:
        return {"configured": True, "error": result["error"], "checklist": None, "answer": None}
    return {"configured": True, **result}


@router.post("/report/submit")
async def submit_report(fields: ReportFields):
    checks = validate_hard_checks(fields.ip, fields.attack_timestamp, fields.categories)
    if not checks["all_passed"]:
        raise HTTPException(status_code=400, detail={"message": "twarde sprawdzenia nie przeszły", "checks": checks})

    if not abuseipdb_service.is_configured():
        raise HTTPException(status_code=400, detail="brak klucza AbuseIPDB API")

    comment = build_comment(
        fields.ip, fields.spoofing_confirmed, fields.attachments, fields.ransom, fields.message_id
    )
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
