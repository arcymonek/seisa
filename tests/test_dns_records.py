"""backend/services/dns_records.py with a fake resolver (no network): what is reported for an ordinary domain, a domain
that does not exist, a dangling name server, a null MX and a wildcard.

Expected values come from the RFCs: TXT data is split in 255-byte strings that are joined without a separator
(RFC 7208 section 3.3), a null MX is the single record "0 ." (RFC 7505), a missing name is NXDOMAIN (RFC 1035), a name
that exists without the asked type is NoAnswer."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import dns.exception
import dns.resolver
import pytest

from backend.services import dns_records


def run(coro):
    return asyncio.run(coro)


class FakeResolver:
    """`zone` maps (name, type) to a list of rdata texts, or to an exception class to raise. A name that is in no key
    at all is NXDOMAIN; a known name with another type is NoAnswer."""

    def __init__(self, zone, wildcard=None):
        self.zone = zone
        self.wildcard = wildcard or {}
        self.names = {name for name, _ in zone}
        self.asked = []

    def is_probe(self, name):
        """The random name of the wildcard check: an unknown label right under a name of the zone (not _dmarc)."""
        label, _, parent = name.partition(".")
        return name not in self.names and parent in self.names and not label.startswith("_")

    async def resolve(self, name, rdtype):
        self.asked.append(name)
        if self.is_probe(name):
            if self.wildcard.get(rdtype):
                return [SimpleNamespace(to_text=lambda v=v: v) for v in self.wildcard[rdtype]]
            raise dns.resolver.NXDOMAIN()
        entry = self.zone.get((name, rdtype))
        if isinstance(entry, type) and issubclass(entry, Exception):
            raise entry()
        if entry is None:
            if name in self.names:
                raise dns.resolver.NoAnswer()
            raise dns.resolver.NXDOMAIN()
        return [SimpleNamespace(to_text=lambda v=v: v) for v in entry]


@pytest.fixture
def resolver(monkeypatch):
    def install(zone, wildcard=None):
        fake = FakeResolver(zone, wildcard)
        monkeypatch.setattr(dns_records, "_resolver", lambda: fake)
        return fake

    return install


ZONE = {
    ("example.org", "A"): ["93.184.216.34"],
    ("example.org", "AAAA"): ["2606:2800:21f:cb07:6820:80da:af6b:8b2c"],
    ("example.org", "NS"): ["B.iana-servers.example.", "a.iana-servers.example."],
    ("example.org", "MX"): ["20 mx2.example.org.", "10 MX1.example.org."],
    ("example.org", "CAA"): ['0 issue "letsencrypt.org"'],
    ("example.org", "TXT"): ['"google-site-verification=x"', '"v=spf1 include:_spf.example.org " "-all"'],
    ("_dmarc.example.org", "TXT"): ['"v=DMARC1; p=reject"'],
    ("a.iana-servers.example", "A"): ["198.51.100.1"],
    ("b.iana-servers.example", "A"): ["198.51.100.2"],
}


def test_an_ordinary_domain(resolver):
    resolver(ZONE)
    summary = run(dns_records.resolve_domain("example.org"))
    assert summary["exists"] is True
    assert summary["a"] == ["93.184.216.34"] and summary["aaaa"] == ["2606:2800:21f:cb07:6820:80da:af6b:8b2c"]
    assert summary["ns"] == ["a.iana-servers.example", "b.iana-servers.example"]  # lower case, no trailing dot, sorted
    assert summary["mx"] == ["mx1.example.org", "mx2.example.org"]  # by preference
    assert summary["caa"] == ['0 issue "letsencrypt.org"']
    assert summary["spf"] == "v=spf1 include:_spf.example.org -all"  # the two strings joined with nothing in between
    assert summary["dmarc"] == "v=DMARC1; p=reject"
    assert summary["wildcard"] is False
    assert "ns_missing" not in summary


def test_a_trailing_dot_in_the_asked_name_is_ignored(resolver):
    resolver(ZONE)
    assert run(dns_records.resolve_domain("example.org."))["a"] == ["93.184.216.34"]


def test_a_domain_that_does_not_exist(resolver):
    resolver({})
    summary = run(dns_records.resolve_domain("nothing-here.example"))
    assert summary["exists"] is False
    assert "a" not in summary and "ns" not in summary and "mx" not in summary


def test_a_name_that_exists_without_address_records_still_exists(resolver):
    resolver({("example.org", "NS"): ["ns1.example.org."], ("ns1.example.org", "A"): ["198.51.100.3"]})
    summary = run(dns_records.resolve_domain("example.org"))
    assert summary["exists"] is True and "a" not in summary and summary["ns"] == ["ns1.example.org"]


def test_a_name_server_whose_own_name_does_not_exist_is_reported_as_dangling(resolver):
    zone = {**ZONE, ("example.org", "NS"): ["a.iana-servers.example.", "ns9.gone.example."]}
    resolver(zone)
    summary = run(dns_records.resolve_domain("example.org"))
    assert summary["ns_missing"] == ["ns9.gone.example"]  # the other name server resolves, so it is not listed


def test_a_timeout_at_a_name_server_proves_nothing(resolver):
    zone = {**ZONE, ("a.iana-servers.example", "A"): dns.exception.Timeout}
    resolver(zone)
    assert "ns_missing" not in run(dns_records.resolve_domain("example.org"))


def test_null_mx_means_the_domain_takes_no_mail(resolver):
    resolver({**ZONE, ("example.org", "MX"): ["0 ."]})
    summary = run(dns_records.resolve_domain("example.org"))
    assert "mx" not in summary  # no host to list (RFC 7505)


def test_wildcard_is_detected_by_a_random_name_that_resolves(resolver):
    resolver(ZONE, wildcard={"A": ["93.184.216.34"]})
    assert run(dns_records.resolve_domain("example.org"))["wildcard"] is True


def test_the_wildcard_probe_name_is_random_and_does_not_name_seisa(resolver):
    """The probe name lands in the logs of the checked domain's name servers (audit A2-B7): it must not tell the owner,
    possibly the phisher, which tool asked."""
    probes = []
    for _ in range(2):
        fake = resolver(ZONE)
        run(dns_records.resolve_domain("example.org"))
        probes += [name for name in fake.asked if fake.is_probe(name)]
    assert len(probes) == 2 and probes[0] != probes[1]
    assert all("seisa" not in name.lower() for name in probes)
    assert all(len(name.split(".")[0]) >= 12 for name in probes)  # long enough not to hit a real name by chance


def test_dns_failures_are_empty_answers_not_errors(resolver):
    zone = {("example.org", t): dns.resolver.NoNameservers for t in ("A", "AAAA", "NS", "MX", "CAA", "TXT")}
    zone[("_dmarc.example.org", "TXT")] = dns.exception.Timeout
    resolver(zone)
    summary = run(dns_records.resolve_domain("example.org"))
    assert summary["exists"] is True  # only NXDOMAIN says a name does not exist
    assert "a" not in summary and "spf" not in summary and "dmarc" not in summary


def test_only_the_first_spf_and_dmarc_record_is_kept(resolver):
    zone = {**ZONE, ("example.org", "TXT"): ['"v=spf1 -all"', '"v=spf1 +all"'], ("_dmarc.example.org", "TXT"): ['"v=DMARC1; p=none"', '"v=DMARC1; p=reject"']}
    resolver(zone)
    summary = run(dns_records.resolve_domain("example.org"))
    assert summary["spf"] == "v=spf1 -all" and summary["dmarc"] == "v=DMARC1; p=none"


def test_txt_helper_joins_split_strings():
    assert dns_records._txt(['"v=spf1 " "-all"', '"plain"']) == ["v=spf1 -all", "plain"]
