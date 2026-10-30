"""CISA's advisories and KEV catalog (#37), and Our World in Data's insights (#38)."""

from datetime import date, datetime, timezone

from unseenet_bots.runner import Bot, allowed_pictures
from unseenet_bots.sources import get_source
from unseenet_bots.sources.cisa import CisaKev, _summary


def _rss(body_html: str) -> bytes:
    return ("<rss><channel><item><title>An advisory</title>"
            "<link>https://www.cisa.gov/a/1</link><guid>https://www.cisa.gov/a/1</guid>"
            "<pubDate>Sun, 18 Oct 2026 08:00:00 +0000</pubDate>"
            f"<description><![CDATA[{body_html}]]></description></item></channel></rss>").encode()


def test_cisa_advisory_whole_when_only_us_agencies_wrote_it():
    src = get_source("cisa-advisories")
    (item,) = src.fetch_items(_rss("<p>Executive Summary</p><p>CISA, the FBI and NSA warn of X "
                                   "and much more.</p><p>Details follow.</p>"))
    assert "Details follow." in item.body and "public domain" in item.body
    assert "only the summary" not in item.body


def test_cisa_advisory_summary_only_with_a_foreign_agency():
    src = get_source("cisa-advisories")
    (item,) = src.fetch_items(_rss("<p>Executive Summary</p><p>The authoring agencies warn of X.</p>"
                                   "<p>The UK National Cyber Security Centre (NCSC) found Y.</p>"))
    assert "The authoring agencies warn of X." in item.body
    assert "found Y" not in item.body and "only the summary" in item.body
    assert "[Read the whole advisory at CISA](https://www.cisa.gov/a/1)" in item.body


def test_summary_in_the_same_paragraph_or_the_first_text():
    assert _summary("**Executive Summary:** The gist.\n\nMore.") == "The gist."
    long = "A first paragraph of real text " * 5
    assert _summary(f"# Title\n\n{long.strip()}\n\nMore.") == long.strip()


CATALOG = {"vulnerabilities": [
    {"cveID": "CVE-2026-2", "vendorProject": "Acme", "product": "Router", "dateAdded": "2026-10-29",
     "vulnerabilityName": "Acme Router *Bad* Thing", "shortDescription": "It is bad.",
     "requiredAction": "Patch it.", "dueDate": "2026-11-19", "knownRansomwareCampaignUse": "Known",
     "notes": "https://acme.example/adv ; https://nvd.nist.gov/vuln/detail/CVE-2026-2"},
    {"cveID": "CVE-2026-1", "vendorProject": "Other", "product": "App", "dateAdded": "2026-10-29",
     "vulnerabilityName": "Other App Flaw", "shortDescription": "Also bad.", "requiredAction": "Patch.",
     "knownRansomwareCampaignUse": "Unknown"},
    {"cveID": "CVE-2026-3", "vendorProject": "Late", "product": "X", "dateAdded": "2026-10-30"},
]}


def test_kev_one_post_for_yesterday_none_for_today():
    items = CisaKev(fetch=lambda url: CATALOG).fetch(date(2026, 10, 30))
    assert [i.id for i in items] == ["kev:2026-10-29"]           # 2026-10-30 is not complete yet
    item = items[0]
    assert item.subject == "2 known exploited vulnerabilities added October 29: Acme, Other"
    assert item.body.index("CVE-2026-1") < item.body.index("CVE-2026-2")
    assert "Acme Router \\*Bad\\* Thing" in item.body and "used in ransomware campaigns" in item.body
    assert "*Due* 2026-11-19" in item.body and "<https://acme.example/adv>" in item.body
    assert item.published == datetime(2026, 10, 30, tzinfo=timezone.utc)
    assert CisaKev(fetch=lambda url: CATALOG).fetch(date(2026, 10, 25)) == []


def _atom(img_alt: str) -> bytes:
    return ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>An insight</title>'
            '<id>https://ourworldindata.org/data-insights/x</id>'
            '<link rel="alternate" href="https://ourworldindata.org/data-insights/x"/>'
            '<published>2026-10-29T00:00:00.000Z</published><author><name>Max Roser</name></author>'
            '<content type="html"><![CDATA[<p>The text.</p><img src="https://owid.example/c.png?w=1&amp;h=2" '
            f'alt="{img_alt}"/>]]></content></entry></feed>').encode()


def test_owid_takes_only_its_own_charts():
    (own,) = get_source("owid").fetch_items(_atom("A chart. License: CC BY to Our World in Data."))
    assert own.body.startswith("*Originally published by Max Roser at [Our World in Data]")
    assert "not an author" in own.body and "The text." in own.body
    (pic,) = own.pictures
    assert (pic.url, pic.licence) == ("https://owid.example/c.png?w=1&h=2", "CC BY 4.0")
    bot = Bot(name="o", source="owid", group="g", from_name="o", pictures="check")
    assert len(allowed_pictures(bot, own, out=lambda m: None)) == 1
    (other,) = get_source("owid").fetch_items(_atom("A chart. Source: World Bank."))
    assert other.pictures == []
