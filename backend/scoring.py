"""Wynik zbiorczy reputacji IP.

Każde źródło zamieniamy na "ryzyko źródła" r (0-100) nieliniową skalą dobraną do
tego, co dana usługa faktycznie mierzy, a potem łączymy głosy modelem szum-OR:

    wynik = 100 * (1 - PRODUKT(1 - c_i * r_i / 100))

c_i to wiarygodność źródła (limit jego głosu, < 1 - źródła nie są w pełni
niezależne, np. VirusTotal wchłania część tych samych zgłoszeń co AbuseIPDB).
Mocny sygnał nie ginie w średniej, zgodne źródła się wzmacniają, a źródło bez
danych po prostu nie głosuje (brak informacji nie jest dowodem niewinności).
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.models import RiskComponent, RiskScore, ServiceResult

CREDIBILITY = {"abuseipdb": 0.9, "virustotal": 0.8, "greynoise": 0.7, "otx": 0.5}

MEDIUM_FROM = 25
HIGH_FROM = 60

# Znane dobre IP (biała lista AbuseIPDB, GreyNoise benign/RIOT, walidacja OTX) - sufit wyniku,
# chyba że inne źródło ma silny, sprzeczny sygnał.
BENIGN_CAP = 15
CONTRADICTION_RISK = 65

ABUSEIPDB_ANCHORS = [(0, 0), (10, 20), (25, 45), (50, 70), (75, 90), (100, 100)]
# argument: ważona liczba detekcji = malicious + 0.5 * suspicious
VIRUSTOTAL_ANCHORS = [(0, 0), (1, 10), (2.5, 25), (5, 45), (8.5, 65), (15, 85), (21, 100)]
# argument: "efektywna" liczba pulsów OTX (patrz _otx_pulse_weight); sufit 65 - OTX sam nie daje "high"
OTX_ANCHORS = [(0, 0), (1, 10), (3, 25), (6, 45), (12, 65)]

GREYNOISE_RISK = {"malicious": 90, "unknown": 30, "benign": 0}


def interpolate(x: float, anchors: list[tuple[float, float]]) -> float:
    """Liniowa interpolacja między kotwicami; poza zakresem - wartość brzegowa."""
    if x <= anchors[0][0]:
        return anchors[0][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
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
    """Wynik oceny jednego źródła: głos (albo brak), ewentualnie sygnał 'znane dobre'."""

    def __init__(self, component: RiskComponent | None = None, benign: str | None = None, neutral: str | None = None):
        self.component = component
        self.benign = benign  # powód "znane dobre IP"
        self.neutral = neutral  # źródło odpowiedziało, ale nie ma nic do powiedzenia


def _component(source: str, signal: str, value: str, risk: float) -> RiskComponent:
    c = CREDIBILITY[source]
    return RiskComponent(
        source=source, signal=signal, value=value, weight=c, risk=round(risk, 1), contribution=round(c * risk, 1)
    )


def score_abuseipdb(s: dict, raw: dict | None = None) -> Vote:
    confidence = s.get("abuse_confidence_score") or 0
    value = f"{confidence}% ({s.get('total_reports') or 0} zgł. od {s.get('num_distinct_users') or 0} użytk.)"
    benign = "AbuseIPDB: IP na białej liście" if s.get("is_whitelisted") else None
    risk = 0.0 if benign else interpolate(confidence, ABUSEIPDB_ANCHORS)
    return Vote(_component("abuseipdb", "confidence_score", value, risk), benign=benign)


def score_virustotal(s: dict, raw: dict | None = None) -> Vote | None:
    total = s.get("total_engines") or 0
    if not total:
        return None
    malicious = s.get("malicious") or 0
    suspicious = s.get("suspicious") or 0
    weighted = malicious + 0.5 * suspicious
    value = f"{malicious} mal. + {suspicious} podej. z {total} silników"
    return Vote(_component("virustotal", "weighted_detections", value, interpolate(weighted, VIRUSTOTAL_ANCHORS)))


def score_greynoise(s: dict, raw: dict | None = None) -> Vote:
    if not s.get("has_data", True):
        return Vote(neutral="greynoise: brak danych (neutralne - nie wpływa na wynik)")

    classification = s.get("classification")
    business = s.get("business_service")
    if classification != "malicious" and (classification == "benign" or s.get("riot") or business):
        reason = "GreyNoise: znana, niegroźna usługa/skaner"
        if isinstance(business, dict) and business.get("name"):
            reason = f"GreyNoise: znana usługa ({business['name']})"
        return Vote(_component("greynoise", "classification", "benign / znana usługa", 0), benign=reason)

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
        extras.append(f"aktor: {actor}")
    value = label + (f" ({', '.join(extras)})" if extras else "")
    return Vote(_component("greynoise", "classification", value, min(100, risk)))


def _otx_pulse_weight(pulse: dict) -> float:
    """Waga jednego pulsu OTX: świeżość * jakość.

    Świeżość: modyfikacja <= 90 dni = 1.0, <= 365 dni = 0.5, starsze 0.2.
    Jakość: puls wzbogacony (adversary / rodzina malware / MITRE ATT&CK) = 1.0;
    masowa lista automatyczna (>= 200 wskaźników) = 0.4; zwykły puls = 0.7.
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
        benign = "OTX: IP oznaczone jako zwalidowane/fałszywy alarm"

    if pulses:
        effective = sum(_otx_pulse_weight(p) for p in pulses)
        # puls_count może być większy niż lista zwrócona przez API - reszta liczy się jak zwykły, świeży puls
        effective += max(0, count - len(pulses)) * 0.7
    else:
        effective = count * 0.7
    recent = s.get("recent_pulse_count")
    enriched = s.get("enriched_pulse_count")
    value = f"pulsów: {count}"
    if count:
        value += f" (świeżych: {recent if recent is not None else '?'}, wzbogaconych: {enriched if enriched is not None else '?'})"
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
            excluded.append(f"{name} (nie dotyczy domen)")
            continue
        possible += 1
        if res.status != "ok":
            excluded.append(f"{name} ({res.status})")
            continue
        vote = fn(res.summary, res.raw)
        if vote is None:
            excluded.append(f"{name} (brak danych)")
            continue
        if vote.neutral:
            excluded.append(vote.neutral)
            continue
        votes.append(vote)

    excluded.append("cloudflare_radar (dane sieciowe/kontekstowe, nie werdykt - poza wynikiem liczbowym)")

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
            notes.append(
                "Sprzeczne sygnały: " + "; ".join(benign_reasons) + " - ale " +
                ", ".join(c.source for c in contradicting) + " wskazuje wysokie ryzyko. Wynik bez obniżenia."
            )
        elif score > BENIGN_CAP:
            score = BENIGN_CAP
            notes.append("Wynik obniżony do " + str(BENIGN_CAP) + " (znane dobre IP): " + "; ".join(benign_reasons) + ".")
        else:
            notes.append("Znane dobre IP: " + "; ".join(benign_reasons) + ".")

    if possible and len(components) <= 1:
        notes.append(
            "Niska pewność: wynik oparty na " + (f"jednym źródle ({components[0].source})" if components else "braku danych z jakiegokolwiek źródła") + "."
        )

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
