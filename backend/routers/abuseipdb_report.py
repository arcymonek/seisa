from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.email_parser import parse_email
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
    port: int | None = None
    attack_timestamp: str | None = None
    description: str = ""
    spoofing_confirmed: bool = False
    attachments: list[dict] = []
    ransom: dict | None = None
    message_id: str | None = None


class SubmitRequest(ReportFields):
    manual_confirmations: dict[str, bool] = {}


@router.post("/email/analyze")
async def analyze_email(req: EmailAnalyzeRequest):
    facts = parse_email(req.raw_email)

    llm_analysis = None
    if req.use_llm and llm_analyzer.is_configured():
        llm_analysis = await llm_analyzer.analyze_email(facts)

    return {
        "facts": facts,
        "categories": ABUSEIPDB_CATEGORIES,
        "llm_configured": llm_analyzer.is_configured(),
        "llm_analysis": llm_analysis,
    }


@router.post("/report/preview")
async def preview_report(fields: ReportFields):
    checks = validate_hard_checks(fields.ip, fields.attack_timestamp, fields.categories, fields.description)
    comment = build_comment(
        fields.ip,
        fields.port,
        fields.description,
        fields.spoofing_confirmed,
        fields.attachments,
        fields.ransom,
        fields.message_id,
    )
    return {"comment": comment, "checks": checks}


@router.post("/report/submit")
async def submit_report(req: SubmitRequest):
    checks = validate_hard_checks(req.ip, req.attack_timestamp, req.categories, req.description)
    if not checks["all_passed"]:
        raise HTTPException(status_code=400, detail={"message": "twarde sprawdzenia nie przeszły", "checks": checks})

    required_manual = {"received_verified", "not_spoofed_source", "category_matches", "pii_redacted"}
    if not required_manual.issubset(req.manual_confirmations.keys()) or not all(
        req.manual_confirmations.get(k) for k in required_manual
    ):
        raise HTTPException(status_code=400, detail="brak potwierdzenia wszystkich pozycji checklisty")

    if not abuseipdb_service.is_configured():
        raise HTTPException(status_code=400, detail="brak klucza AbuseIPDB API")

    comment = build_comment(
        req.ip, req.port, req.description, req.spoofing_confirmed, req.attachments, req.ransom, req.message_id
    )
    timestamp = req.attack_timestamp or datetime.now(timezone.utc).isoformat()

    try:
        result = await abuseipdb_service.submit_report(req.ip, req.categories, comment, timestamp)
    except Exception as exc:
        append_report_log(
            {
                "ip": req.ip,
                "categories": req.categories,
                "comment": comment,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "success": False,
                "error": str(exc),
            }
        )
        raise HTTPException(status_code=502, detail=f"błąd AbuseIPDB API: {exc}")

    append_report_log(
        {
            "ip": req.ip,
            "categories": req.categories,
            "comment": comment,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "result": result,
        }
    )
    return {"success": True, "result": result}
