from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
FRONTEND_DIR = BASE_DIR / "frontend"
LOGI_DIR = BASE_DIR / "logi"

HISTORY_FILE = DATA_DIR / "history.json"
VT_USAGE_FILE = DATA_DIR / "vt_usage.json"
REPORT_LOG_FILE = DATA_DIR / "report_log.json"
ABUSEIPDB_POLICY_FILE = DOCS_DIR / "abuseipdb-reporting-policy.md"

HISTORY_MAX_ENTRIES = 10


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
