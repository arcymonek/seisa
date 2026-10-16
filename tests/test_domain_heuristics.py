"""backend/domain_heuristics.py: every signal on its own, the age boundaries and the ceiling of 75 (a local hint can lift
a domain to "medium", never to "high" alone: the scoring model sets "high" from 60 and the cap keeps one weak source
below certainty). No network.

The look-alike example is the classic one: "xn--pple-43d.example" is "apple" written with a CYRILLIC small a (U+0430)
in the first position (IDNA, RFC 5891/3492) - a Latin and a Cyrillic letter in one label."""
from __future__ import annotations

import pytest

from backend.domain_heuristics import MAX_RISK, Signal, analyze, total_risk


def ids(domain, age=None):
    return [s.id for s in analyze(domain, age)]


def by_id(domain, age=None):
    return {s.id: s for s in analyze(domain, age)}


def test_an_ordinary_domain_has_no_signal():
    assert analyze("example.org", 4000) == []
    assert analyze("example.org", None) == []  # age unknown: no "young" claim


@pytest.mark.parametrize(("age", "risk"), [(0, 40), (29, 40), (30, 20), (89, 20)])
def test_young_domain_risk_by_age(age, risk):
    assert by_id("example.org", age)["young"].risk == risk


@pytest.mark.parametrize("age", [90, 91, 3650])
def test_domain_at_least_90_days_old_is_not_young(age):
    assert "young" not in ids("example.org", age)


def test_mixed_scripts_in_one_label_is_a_homograph():
    signals = by_id("xn--pple-43d.example")
    assert signals["homograph"].risk == 40 and "punycode" not in signals
    assert chr(0x430) + "pple" in signals["homograph"].text  # the decoded name is shown


def test_a_single_script_idn_is_only_punycode():
    signals = by_id("xn--e1afmkfd.example")  # a Cyrillic word, no Latin letter in the label
    assert signals["punycode"].risk == 15 and "homograph" not in signals


def test_invalid_punycode_does_not_break_the_check():
    assert isinstance(analyze("xn--zz--.example", None), list)  # an undecodable label is simply taken as it is


@pytest.mark.parametrize("tld", ["top", "xyz", "zip"])
def test_suspicious_tld(tld):
    assert by_id(f"example.{tld}")["tld"].risk == 10


def test_ordinary_tld_has_no_signal():
    assert "tld" not in ids("example.org") and "tld" not in ids("example.com")


def test_random_looking_label_needs_length_entropy_and_digits():
    assert by_id("a8k3j2x9q1z7.example")["random"].risk == 15
    assert "random" not in ids("abcdefghijkl.example")      # long and varied, but no digits
    assert "random" not in ids("a1b2.example")              # digits, but short
    assert "random" not in ids("1111111111aa.example")      # long, many digits, but low entropy
    assert "random" not in ids("xn--a8k3j2x9q1z7.example")  # punycode labels are judged by the punycode signal


def test_lure_word_needs_a_hyphen_or_three_labels():
    assert by_id("secure-login.example.org")["lure"].risk == 15
    assert by_id("login.bank.example.org")["lure"].risk == 15
    assert "lure" not in ids("login.example")               # a plain two-label name with the word is not enough
    assert "lure" not in ids("example.login")               # the word in the TLD does not count (only the body)


def test_lure_text_lists_every_word_found():
    text = by_id("paypal-secure.example.org")["lure"].text
    assert "paypal" in text and "secure" in text


def test_trailing_dot_and_capitals_do_not_matter():
    assert ids("SECURE-LOGIN.Example.TOP.") == ids("secure-login.example.top")


def test_total_risk_adds_up_below_the_ceiling():
    assert total_risk([Signal("a", 10, ""), Signal("b", 15, "")]) == 25
    assert total_risk([]) == 0


def test_total_risk_never_exceeds_the_ceiling():
    assert MAX_RISK == 75
    assert total_risk([Signal("a", 40, ""), Signal("b", 40, "")]) == 75
    assert total_risk(analyze("xn--pple-43d.top", 3)) == 75  # young 40 + homograph 40 + tld 10 = 90, capped
