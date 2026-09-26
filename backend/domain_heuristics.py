"""Local, explainable signals about a domain name and its age - no network, nothing sent anywhere.

Each signal is a weak hint (a young domain, a look-alike script, a random-looking label ...) with a risk 0-100; the
scoring model treats them as one low-credibility source, so they can lift a domain to "medium" but never to "high"
on their own.
"""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass

from backend.i18n import t

SUSPICIOUS_TLDS = frozenset("top xyz click zip mov tk ml ga cf gq icu buzz cyou rest".split())
LURE_WORDS = ("login", "signin", "secure", "verify", "account", "update", "billing", "wallet", "paypal", "bank")
MAX_RISK = 75.0


@dataclass(frozen=True)
class Signal:
    id: str
    risk: float
    text: str


def _entropy(text: str) -> float:
    return -sum(text.count(c) / len(text) * math.log2(text.count(c) / len(text)) for c in set(text))


def _scripts(label: str) -> set[str]:
    scripts = set()
    for ch in label:
        if ch.isalpha():
            scripts.add(unicodedata.name(ch, "UNKNOWN").split()[0])
    return scripts


def _unicode_labels(domain: str) -> list[str]:
    labels = []
    for label in domain.split("."):
        if label.startswith("xn--"):
            try:
                label = label.encode("ascii").decode("idna")
            except UnicodeError:
                pass
        labels.append(label)
    return labels


def analyze(domain: str, age_days: int | None) -> list[Signal]:
    signals: list[Signal] = []
    domain = domain.lower().rstrip(".")
    labels = domain.split(".")

    if age_days is not None and age_days < 90:
        signals.append(Signal("young", 40 if age_days < 30 else 20, t("heur.young", days=age_days)))

    if any(label.startswith("xn--") for label in labels):
        mixed = any(len(_scripts(label)) > 1 for label in _unicode_labels(domain))
        if mixed:
            signals.append(Signal("homograph", 40, t("heur.homograph", decoded=".".join(_unicode_labels(domain)))))
        else:
            signals.append(Signal("punycode", 15, t("heur.punycode", decoded=".".join(_unicode_labels(domain)))))

    if labels[-1] in SUSPICIOUS_TLDS:
        signals.append(Signal("tld", 10, t("heur.tld", tld=labels[-1])))

    body = labels[:-1]
    longest = max(body, key=len, default="")
    if len(longest) >= 10 and not longest.startswith("xn--"):
        digits = sum(c.isdigit() for c in longest) / len(longest)
        if _entropy(longest) >= 3.5 and digits >= 0.2:
            signals.append(Signal("random", 15, t("heur.random", label=longest)))

    hits = [w for w in LURE_WORDS if any(w in label for label in body)]
    if hits and (len(body) >= 3 or any("-" in label for label in body)):
        signals.append(Signal("lure", 15, t("heur.lure", words=", ".join(hits))))
    return signals


def total_risk(signals: list[Signal]) -> float:
    return min(MAX_RISK, sum(s.risk for s in signals))
