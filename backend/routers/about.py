"""Info tab: which integrations have an API key (never the keys themselves), today's VirusTotal usage and the recent
releases from the git log (empty when Seisa does not run from a git checkout)."""
from __future__ import annotations

import re
import subprocess

from fastapi import APIRouter

from backend.config import BASE_DIR, settings
from backend.ratelimit import VT_PER_DAY, vt_rate_limiter

router = APIRouter()

CHANGES_LIMIT = 12
_RELEASE = re.compile(r"^Seisa (\d+\.\d+\.\d+): (.+)$")


def _recent_changes() -> list[dict]:
    try:
        out = subprocess.run(
            ["git", "log", "-n", str(CHANGES_LIMIT), "--format=%s"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=3, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = (_RELEASE.match(line) for line in out.splitlines())
    return [{"version": m.group(1), "summary": m.group(2)} for m in found if m]


@router.get("/about")
def about():
    keyed = {
        "virustotal": settings.virustotal_api_key,
        "otx": settings.otx_api_key,
        "cloudflare_radar": settings.cloudflare_radar_api_key,
        "abuseipdb": settings.abuseipdb_api_key,
        "greynoise": settings.greynoise_api_key,
        "urlscan": settings.urlscan_api_key,
    }
    llm_on = bool(settings.openrouter_api_key)
    return {
        "services": [{"id": name, "configured": bool(key)} for name, key in keyed.items()]
        + [{"id": "whois_rdns", "configured": None}],
        "llm": {"configured": llm_on, "model": settings.openrouter_model if llm_on else None},
        "virustotal_usage": {"used": vt_rate_limiter.daily_count(), "limit": VT_PER_DAY},
        "changes": _recent_changes(),
    }
