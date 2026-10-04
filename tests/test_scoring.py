"""backend/scoring.py: the IP/domain reputation score.

Expected numbers are worked out by hand from the formulas in the module docstring (anchor interpolation, then
noisy-OR: score = 100 * (1 - PRODUCT(1 - credibility * risk / 100))), with the anchor tables copied from the
documented design, not obtained by calling the code.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.models import ServiceResult
from backend.scoring import (
    _days_since,
    compute_risk_score,
    interpolate,
    score_abuseipdb,
    score_greynoise,
    score_otx,
    score_virustotal,
)


def ok(service: str, summary: dict, raw: dict | None = None) -> ServiceResult:
    return ServiceResult(service=service, status="ok", summary=summary, raw=raw)


# ---- interpolate ----

ANCHORS = [(0, 0), (10, 100)]


@pytest.mark.parametrize("x, expected", [(0, 0), (5, 50), (10, 100), (2.5, 25), (-3, 0), (99, 100)])
def test_interpolate_linear_and_clamped(x, expected):
    assert interpolate(x, ANCHORS) == pytest.approx(expected)


def test_interpolate_multi_segment():
    anchors = [(0, 0), (10, 20), (30, 40)]
    assert interpolate(10, anchors) == pytest.approx(20)  # an anchor itself
    assert interpolate(20, anchors) == pytest.approx(30)  # halfway through the second segment


# ---- _days_since ----

def test_days_since_handles_missing_and_invalid_input():
    assert _days_since(None) is None
    assert _days_since("") is None
    assert _days_since("not a date") is None


def test_days_since_past_naive_and_zulu_and_future():
    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
    assert _days_since(two_days_ago.isoformat()) == pytest.approx(2.0, abs=0.01)
    assert _days_since(two_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")) == pytest.approx(2.0, abs=0.01)
    assert _days_since(two_days_ago.replace(tzinfo=None).isoformat()) == pytest.approx(2.0, abs=0.01)  # naive = UTC
    assert _days_since((datetime.now(timezone.utc) + timedelta(days=5)).isoformat()) == 0.0  # never negative


# ---- per-source scoring ----

@pytest.mark.parametrize("confidence, risk", [(0, 0), (10, 20), (25, 45), (50, 70), (75, 90), (100, 100)])
def test_abuseipdb_risk_follows_documented_anchors(confidence, risk):
    vote = score_abuseipdb({"abuse_confidence_score": confidence})
    assert vote.component.risk == pytest.approx(risk)
    assert vote.component.weight == 0.9
    assert vote.benign is None


def test_abuseipdb_whitelisted_is_zero_risk_and_benign():
    vote = score_abuseipdb({"abuse_confidence_score": 80, "is_whitelisted": True})
    assert vote.component.risk == 0
    assert vote.benign


def test_abuseipdb_missing_fields_do_not_crash():
    assert score_abuseipdb({}).component.risk == 0


def test_virustotal_without_engines_does_not_vote():
    assert score_virustotal({"total_engines": 0, "malicious": 5}) is None
    assert score_virustotal({}) is None


@pytest.mark.parametrize(
    "malicious, suspicious, risk",
    [(0, 0, 0), (1, 0, 10), (5, 0, 45), (2, 1, 25), (21, 0, 100), (40, 10, 100)],  # weighted = malicious + 0.5 * suspicious
)
def test_virustotal_weighted_detections(malicious, suspicious, risk):
    vote = score_virustotal({"total_engines": 70, "malicious": malicious, "suspicious": suspicious})
    assert vote.component.risk == pytest.approx(risk)
    assert vote.component.weight == 0.8


def test_greynoise_without_data_is_neutral_not_innocent():
    vote = score_greynoise({"has_data": False})
    assert vote.component is None
    assert vote.neutral


@pytest.mark.parametrize("summary", [{"classification": "benign"}, {"riot": True}, {"business_service": {"name": "Some CDN"}}])
def test_greynoise_benign_signals(summary):
    vote = score_greynoise(summary)
    assert vote.benign
    assert vote.component.risk == 0


def test_greynoise_malicious_overrides_riot():
    vote = score_greynoise({"classification": "malicious", "riot": True})
    assert vote.benign is None
    assert vote.component.risk == 90


@pytest.mark.parametrize(
    "summary, risk",
    [
        ({"classification": "unknown"}, 30),
        ({}, 30),  # no classification at all is treated as unknown
        ({"classification": "malicious"}, 90),
        ({"classification": "malicious", "cves": ["CVE-1"]}, 95),
        ({"classification": "malicious", "actor": "SomeGroup"}, 95),
        ({"classification": "malicious", "actor": "unknown"}, 90),  # an "unknown" actor adds nothing
        ({"classification": "unknown", "cves": ["CVE-1", "CVE-2"], "actor": "SomeGroup"}, 45),  # 30 + 10 + 5
        ({"classification": "malicious", "cves": ["CVE-1", "CVE-2", "CVE-3"], "actor": "SomeGroup"}, 100),  # capped
    ],
)
def test_greynoise_risk_and_bonuses(summary, risk):
    assert score_greynoise(summary).component.risk == pytest.approx(risk)


def test_otx_without_pulses_is_zero():
    assert score_otx({"pulse_count": 0}).component.risk == 0


def test_otx_count_only_uses_0_7_per_pulse():
    # no pulse details: 10 pulses * 0.7 = 7.0 effective -> between anchors (6, 45) and (12, 65): 45 + 20 * 1/6
    assert score_otx({"pulse_count": 10}).component.risk == pytest.approx(48.3, abs=0.05)


def test_otx_validated_or_false_positive_is_benign_zero():
    for flag in ({"validation": ["x"]}, {"false_positive": ["y"]}):
        vote = score_otx({"pulse_count": 50, **flag})
        assert vote.benign
        assert vote.component.risk == 0


@pytest.mark.parametrize(
    "pulse, risk",
    [
        ({"adversary": "SomeGroup"}, 10.0),  # fresh (no date) * enriched: weight 1.0 -> effective 1.0 -> risk 10
        ({"malware_families": ["x"]}, 10.0),
        ({}, 7.0),  # fresh * ordinary 0.7 -> effective 0.7 -> 0.7 * 10
        ({"indicator_type_counts": {"IPv4": 200}}, 4.0),  # mass automatic list: 0.4
        ({"modified": "2000-01-01T00:00:00Z"}, 1.4),  # older than a year: freshness 0.2 * 0.7 = 0.14
    ],
)
def test_otx_pulse_quality_and_freshness(pulse, risk):
    vote = score_otx({"pulse_count": 1}, raw={"pulse_info": {"pulses": [pulse]}})
    assert vote.component.risk == pytest.approx(risk, abs=0.05)


def test_otx_pulses_beyond_the_returned_list_count_as_ordinary_fresh_pulses():
    raw = {"pulse_info": {"pulses": [{"adversary": "SomeGroup"}]}}
    # 1.0 (listed, enriched) + 2 * 0.7 (unlisted) = 2.4 -> between (1, 10) and (3, 25): 10 + 15 * 1.4/2 = 20.5
    assert score_otx({"pulse_count": 3}, raw=raw).component.risk == pytest.approx(20.5, abs=0.05)


# ---- compute_risk_score ----

def test_no_services_gives_a_low_empty_score():
    result = compute_risk_score({}, "ip")
    assert result.score == 0
    assert result.level == "low"
    assert result.components == []
    assert result.sources_used == 0
    assert result.sources_possible == 0


def test_single_source_score_and_low_confidence_note():
    result = compute_risk_score({"abuseipdb": ok("abuseipdb", {"abuse_confidence_score": 50})}, "ip")
    assert result.score == pytest.approx(63.0)  # 100 * 0.9 * 0.70
    assert result.level == "high"
    assert result.sources_used == 1 and result.sources_possible == 1
    assert len(result.notes) == 1  # "based on a single source"


def test_two_sources_combine_by_noisy_or():
    results = {
        "abuseipdb": ok("abuseipdb", {"abuse_confidence_score": 50}),  # 0.9 * 0.70 = 0.63
        "virustotal": ok("virustotal", {"total_engines": 70, "malicious": 5}),  # 0.8 * 0.45 = 0.36
    }
    result = compute_risk_score(results, "ip")
    assert result.score == pytest.approx(76.3, abs=0.05)  # 100 * (1 - 0.37 * 0.64)
    assert result.sources_used == 2
    assert result.notes == []


def test_agreeing_sources_score_higher_than_either_alone():
    a = ok("abuseipdb", {"abuse_confidence_score": 50})
    b = ok("virustotal", {"total_engines": 70, "malicious": 5})
    alone = compute_risk_score({"abuseipdb": a}, "ip").score
    together = compute_risk_score({"abuseipdb": a, "virustotal": b}, "ip").score
    assert together > alone


@pytest.mark.parametrize("confidence, level", [(10, "low"), (25, "medium"), (50, "high"), (100, "high")])
def test_level_thresholds(confidence, level):
    # single AbuseIPDB source: 18.0, 40.5, 63.0, 90.0 (all well inside their band)
    result = compute_risk_score({"abuseipdb": ok("abuseipdb", {"abuse_confidence_score": confidence})}, "ip")
    assert result.level == level


def test_failed_source_is_excluded_and_not_counted_as_innocent():
    failed = ServiceResult(service="abuseipdb", status="error", error_message="boom")
    result = compute_risk_score({"abuseipdb": failed}, "ip")
    assert result.score == 0
    assert result.components == []
    assert result.sources_possible == 1
    assert any("abuseipdb (error)" in s for s in result.excluded_sources)
    assert len(result.notes) == 1  # low-confidence note: no data at all


def test_greynoise_without_data_is_excluded_not_voting():
    result = compute_risk_score({"greynoise": ok("greynoise", {"has_data": False})}, "ip")
    assert result.components == []
    assert result.score == 0


def test_known_good_signal_caps_a_moderate_score():
    results = {
        "abuseipdb": ok("abuseipdb", {"abuse_confidence_score": 0, "is_whitelisted": True}),
        "greynoise": ok("greynoise", {"classification": "unknown"}),  # 0.7 * 30 = 21 > cap of 15
    }
    result = compute_risk_score(results, "ip")
    assert result.score == 15.0
    assert result.level == "low"


def test_strong_contradicting_signal_beats_the_known_good_cap():
    results = {
        "greynoise": ok("greynoise", {"classification": "benign"}),
        "abuseipdb": ok("abuseipdb", {"abuse_confidence_score": 100}),  # risk 100 >= 65: not capped
    }
    result = compute_risk_score(results, "ip")
    assert result.score == pytest.approx(90.0)  # 100 * (1 - (1 - 0.9) * (1 - 0))
    assert result.level == "high"
    assert len(result.notes) == 1


def test_ip_only_services_are_ignored_for_domains():
    results = {
        "abuseipdb": ok("abuseipdb", {"abuse_confidence_score": 100}),
        "greynoise": ok("greynoise", {"classification": "malicious"}),
        "virustotal": ok("virustotal", {"total_engines": 70, "malicious": 21}),
    }
    result = compute_risk_score(results, "domain")
    assert [c.source for c in result.components] == ["virustotal"]
    assert result.score == pytest.approx(80.0)  # 0.8 * 100
    assert result.sources_possible == 1  # abuseipdb and greynoise do not count for domains


def test_service_without_result_is_skipped_silently():
    result = compute_risk_score({"virustotal": ok("virustotal", {"total_engines": 70, "malicious": 21})}, "ip")
    assert result.sources_possible == 1
    assert result.score == pytest.approx(80.0)
