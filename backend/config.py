"""Central configuration: filesystem locations (data/, logs/, docs/, frontend/), size and retention limits, and the
`settings` object that reads API keys from the gitignored .env file. Imported by almost every other module; it has
no logic beyond defining these values.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
FRONTEND_DIR = BASE_DIR / "frontend"
LOGS_DIR = BASE_DIR / "logs"
ANALYSES_DIR = DATA_DIR / "analyses"

HISTORY_FILE = DATA_DIR / "history.json"  # the single-file history of versions before 2.4.25, read only to migrate it
HISTORY_DIR = DATA_DIR / "history"
HISTORY_INDEX_FILE = HISTORY_DIR / "index.json"
HISTORY_ENTRIES_DIR = HISTORY_DIR / "entries"
VT_USAGE_FILE = DATA_DIR / "vt_usage.json"
REPORT_LOG_FILE = DATA_DIR / "report_log.json"
API_USAGE_FILE = DATA_DIR / "api_usage.json"
ABUSEIPDB_POLICY_FILE = DOCS_DIR / "abuseipdb-reporting-policy.md"
EMAIL_GUIDE_FILE = DOCS_DIR / "email-analysis-guide.md"

HISTORY_MAX_ENTRIES = 100
LOG_RETENTION_DAYS = 30  # daily log files older than this are deleted (today counts as day 1)

# Request size limits (a local tool, but nothing should be able to make it parse or store unbounded input).
MAX_SOURCE_CHARS = 3_000_000  # e-mail source
MAX_HISTORY_DATA_CHARS = 10_000_000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    urlscan_api_key: str = ""
    virustotal_api_key: str = ""
    otx_api_key: str = ""
    cloudflare_radar_api_key: str = ""
    abuseipdb_api_key: str = ""
    greynoise_api_key: str = ""

    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-4.5"


settings = Settings()
