"""The two LLM prompt files live in backend/prompts/ (part of the program, not documentation) and really reach the
prompts. A missing file is not an error in the app (the loaders return ""), so a wrong path would silently send the
model an empty guide or policy; these tests catch that.
"""
from __future__ import annotations

import backend.config as cfg
from backend.routers import email_analysis
from backend.services.llm_analyzer import LlmAnalyzer

PROMPTS_DIR = cfg.BASE_DIR / "backend" / "prompts"


def test_prompt_files_are_in_backend_prompts():
    assert cfg.PROMPTS_DIR == PROMPTS_DIR
    assert cfg.ABUSEIPDB_POLICY_FILE == PROMPTS_DIR / "abuseipdb-reporting-policy.md"
    assert cfg.EMAIL_GUIDE_FILE == PROMPTS_DIR / "email-analysis-guide.md"
    assert cfg.ABUSEIPDB_POLICY_FILE.is_file()
    assert cfg.EMAIL_GUIDE_FILE.is_file()


def test_prompt_files_left_docs():
    assert not (cfg.BASE_DIR / "docs" / "abuseipdb-reporting-policy.md").exists()
    assert not (cfg.BASE_DIR / "docs" / "email-analysis-guide.md").exists()


def test_email_guide_reaches_the_system_prompt():
    prompt = email_analysis._system_prompt("en")
    assert "# E-mail source analysis guide" in prompt
    assert prompt.endswith(cfg.EMAIL_GUIDE_FILE.read_text(encoding="utf-8"))


def test_abuseipdb_policy_reaches_the_prompt():
    excerpt = LlmAnalyzer()._policy_excerpt()
    assert excerpt.startswith("# AbuseIPDB reporting rules")
    assert excerpt == cfg.ABUSEIPDB_POLICY_FILE.read_text(encoding="utf-8")[:12000]
