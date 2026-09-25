"""Aggregate IP reputation score.

Every source is turned into a "source risk" r (0-100) with a non-linear scale chosen for what the given service
actually measures, and the votes are then combined with a noisy-OR model:

    score = 100 * (1 - PRODUCT(1 - c_i * r_i / 100))

c_i is the credibility of the source (the cap of its vote, < 1 - the sources are not fully independent, e.g.
VirusTotal absorbs part of the same reports as AbuseIPDB). A strong signal does not vanish in an average,
agreeing sources reinforce each other, and a source without data simply does not vote (no information is not
proof of innocence).
"""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import pairwise

from backend.i18n import t
from backend.models import RiskComponent, RiskScore, ServiceResult

CREDIBILITY = {"abuseipdb": 0.9, "virustotal": 0.8, "greynoise": 0.7, "otx": 0.5}

MEDIUM_FROM = 25
HIGH_FROM = 60

# Known good IPs (AbuseIPDB whitelist, GreyNoise benign/RIOT, OTX validation) - a ceiling for the score,
# unless another source has a strong, contradicting signal.
BENIGN_CAP = 15
CONTRADICTION_RISK = 65

ABUSEIPDB_ANCHORS = [(0, 0), (10, 20), (25, 45), (50, 70), (75, 90), (100, 100)]
# argument: weighted number of detections = malicious + 0.5 * suspicious
VIRUSTOTAL_ANCHORS = [(0, 0), (1, 10), (2.5, 25), (5, 45), (8.5, 65), (15, 85), (21, 100)]
# argument: "effective" number of OTX pulses (see _otx_pulse_weight); cap 65 - OTX alone never gives "high"
OTX_ANCHORS = [(0, 0), (1, 10), (3, 25), (6, 45), (12, 65)]

GREYNOISE_RISK = {"malicious": 90, "unknown": 30, "benign": 0}


def interpolate(x: float, anchors: list[tuple[float, float]]) -> float:
    """Linear interpolation between the anchors; outside the range - the edge value."""
    if x <= anchors[0][0]:
        return anchors[0][1]
    for (x0, y0), (x1, y1) in pairwise(anchors):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return anchors[-1][1]


def _days_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)


class Vote:
    """Result of scoring one source: a vote (or none), possibly a 'known good' signal."""

    def __init__(self, component: RiskComponent | None = None, benign: str | None = None, neutral: str | None = None):
        self.component = component
        self.benign = benign  # reason for "known good IP"
        self.neutral = neutral  # the source answered but has nothing to say


def _component(source: str, signal: str, value: str, risk: float) -> RiskComponent:
    c = CREDIBILITY[source]
    return RiskComponent(
        source=source, signal=signal, value=value, weight=c, risk=round(risk, 1), contribution=round(c * risk, 1)
    )


def score_abuseipdb(s: dict, raw: dict | None = None) -> Vote:
    confidence = s.get("abuse_confidence_score") or 0
    value = t("score.abuseipdb_value", confidence=confidence, reports=s.get("total_reports") or 0, users=s.get("num_distinct_users") or 0)
    benign = t("score.abuseipdb_whitelisted") if s.get("is_whitelisted") else None
    risk = 0.0 if benign else interpolate(confidence, ABUSEIPDB_ANCHORS)
    return Vote(_component("abuseipdb", "confidence_score", value, risk), benign=benign)


def score_virustotal(s: dict, raw: dict | None = None) -> Vote | None:
    total = s.get("total_engines") or 0
    if not total:
        return None
    malicious = s.get("malicious") or 0
    suspicious = s.get("suspicious") or 0
    weighted = malicious + 0.5 * suspicious
    value = t("score.vt_value", malicious=malicious, suspicious=suspicious, total=total)
    return Vote(_component("virustotal", "weighted_detections", value, interpolate(weighted, VIRUSTOTAL_ANCHORS)))


def score_greynoise(s: dict, raw: dict | None = None) -> Vote:
    if not s.get("has_data", True):
        return Vote(neutral=t("score.greynoise_no_data"))

    classification = s.get("classification")
    business = s.get("business_service")
    if classification != "malicious" and (classification == "benign" or s.get("riot") or business):
        reason = t("score.greynoise_benign")
        if isinstance(business, dict) and business.get("name"):
            reason = t("score.greynoise_service", name=business["name"])
        return Vote(_component("greynoise", "classification", t("score.greynoise_benign_value"), 0), benign=reason)

    label = classification or "unknown"
    risk = float(GREYNOISE_RISK.get(label, GREYNOISE_RISK["unknown"]))
    extras = []
    cves = s.get("cves") or []
    if cves:
        risk += min(10, 5 * len(cves))
        extras.append(f"{len(cves)} CVE")
    actor = s.get("actor")
    if actor and str(actor).lower() != "unknown":
        risk += 5
        extras.append(t("score.greynoise_actor", actor=actor))
    value = label + (f" ({', '.join(extras)})" if extras else "")
    return Vote(_component("greynoise", "classification", value, min(100, risk)))


def _otx_pulse_weight(pulse: dict) -> float:
    """Weight of one OTX pulse: freshness * quality.

    Freshness: modified <= 90 days ago = 1.0, <= 365 days = 0.5, older 0.2.
    Quality: an enriched pulse (adversary / malware family / MITRE ATT&CK) = 1.0;
    a mass automatic list (>= 200 indicators) = 0.4; an ordinary pulse = 0.7.
    """
    age = _days_since(pulse.get("modified") or pulse.get("created"))
    freshness = 1.0 if age is None or age <= 90 else 0.5 if age <= 365 else 0.2
    enriched = bool(pulse.get("adversary") or pulse.get("malware_families") or pulse.get("attack_ids"))
    bulk = sum((pulse.get("indicator_type_counts") or {}).values()) >= 200
    quality = 1.0 if enriched else 0.4 if bulk else 0.7
    return freshness * quality


def score_otx(s: dict, raw: dict | None = None) -> Vote:
    pulses = ((raw or {}).get("pulse_info") or {}).get("pulses") or []
    count = s.get("pulse_count", 0)
    benign = None
    if s.get("validation") or s.get("false_positive"):
        benign = t("score.otx_validated")

    if pulses:
        effective = sum(_otx_pulse_weight(p) for p in pulses)
        # pulse_count may be larger than the list returned by the API - the rest counts as an ordinary, fresh pulse
        effective += max(0, count - len(pulses)) * 0.7
    else:
        effective = count * 0.7
    recent = s.get("recent_pulse_count")
    enriched = s.get("enriched_pulse_count")
    value = t("score.otx_pulses", count=count)
    if count:
        value += " " + t("score.otx_detail", recent=recent if recent is not None else "?", enriched=enriched if enriched is not None else "?")
    risk = 0.0 if benign else interpolate(effective, OTX_ANCHORS)
    return Vote(_component("otx", "pulses", value, risk), benign=benign)


def compute_risk_score(results: dict[str, ServiceResult], indicator_type: str) -> RiskScore:
    votes: list[Vote] = []
    excluded: list[str] = []
    scorers = {
        "abuseipdb": score_abuseipdb,
        "virustotal": score_virustotal,
        "greynoise": score_greynoise,
        "otx": score_otx,
    }
    possible = 0

    for name, fn in scorers.items():
        res = results.get(name)
        if res is None:
            continue
        if indicator_type != "ip" and name in ("abuseipdb", "greynoise"):
            excluded.append(t("score.not_for_domains", name=name))
            continue
        possible += 1
        if res.status != "ok":
            excluded.append(f"{name} ({res.status})")
            continue
        vote = fn(res.summary, res.raw)
        if vote is None:
            excluded.append(t("score.no_data", name=name))
            continue
        if vote.neutral:
            excluded.append(vote.neutral)
            continue
        votes.append(vote)

    excluded.append(t("score.cloudflare_excluded"))

    components = [v.component for v in votes if v.component]
    remaining = 1.0
    for c in components:
        remaining *= 1 - c.weight * c.risk / 100
    score = (1 - remaining) * 100

    notes: list[str] = []
    benign_reasons = [v.benign for v in votes if v.benign]
    if benign_reasons:
        contradicting = [c for c in components if c.risk >= CONTRADICTION_RISK]
        if contradicting:
            notes.append(t("score.note_contradiction", reasons="; ".join(benign_reasons), sources=", ".join(c.source for c in contradicting)))
        elif score > BENIGN_CAP:
            score = BENIGN_CAP
            notes.append(t("score.note_capped", cap=BENIGN_CAP, reasons="; ".join(benign_reasons)))
        else:
            notes.append(t("score.note_known_good", reasons="; ".join(benign_reasons)))

    if possible and len(components) <= 1:
        basis = t("score.basis_single", source=components[0].source) if components else t("score.basis_nodata")
        notes.append(t("score.note_low_confidence", basis=basis))

    score = round(score, 1)
    level = "high" if score >= HIGH_FROM else "medium" if score >= MEDIUM_FROM else "low"
    return RiskScore(
        level=level,
        score=score,
        components=components,
        excluded_sources=excluded,
        sources_used=len(components),
        sources_possible=possible,
        notes=notes,
    )
