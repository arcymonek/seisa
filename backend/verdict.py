"""Language-independent verdict protocol of the e-mail analysis.

The first line of the LLM answer is a machine-readable line with canonical English codes, whatever language
the analysis itself is written in:

    VERDICT: <legit|phishing|spam|scam|malware|inconclusive> | CONFIDENCE: <high|medium|low>

Analyses saved before the protocol was made language-neutral use the Polish tokens (WERDYKT / PEWNOSC with
legalna, oszustwo, niejednoznaczna, wysoka, srednia, niska). Those are still accepted and mapped to the
canonical codes on read; stored files are never rewritten just for that.
"""
from __future__ import annotations

import re

VERDICTS = ("legit", "phishing", "spam", "scam", "malware", "inconclusive")
CONFIDENCES = ("high", "medium", "low")

_LEGACY_VERDICTS = {"legalna": "legit", "oszustwo": "scam", "niejednoznaczna": "inconclusive"}
_LEGACY_CONFIDENCES = {"wysoka": "high", "srednia": "medium", "niska": "low"}

_VERDICT_ALT = "|".join(VERDICTS + tuple(_LEGACY_VERDICTS))
_CONFIDENCE_ALT = "|".join(CONFIDENCES + tuple(_LEGACY_CONFIDENCES))

VERDICT_LINE_RE = re.compile(
    rf"^\s*(?:VERDICT|WERDYKT):\s*({_VERDICT_ALT})\s*\|\s*(?:CONFIDENCE|PEWNOSC):\s*({_CONFIDENCE_ALT})",
    re.IGNORECASE,
)


def normalize_verdict(value: str | None) -> str | None:
    if not value:
        return None
    value = value.lower()
    return _LEGACY_VERDICTS.get(value, value)


def normalize_confidence(value: str | None) -> str | None:
    if not value:
        return None
    value = value.lower()
    return _LEGACY_CONFIDENCES.get(value, value)


def parse_verdict(text: str) -> tuple[str | None, str | None]:
    """(verdict, confidence) from the first line of an analysis, canonical codes; (None, None) if absent."""
    first_line = text.lstrip().split("\n", 1)[0]
    m = VERDICT_LINE_RE.match(first_line)
    if not m:
        return None, None
    return normalize_verdict(m.group(1)), normalize_confidence(m.group(2))
