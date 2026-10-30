"""CISA, the US Cybersecurity and Infrastructure Security Agency (#37). Its own work is
US government work, in the public domain in the US, and CISA waives its rights abroad
where it can - so its advisories go whole, credited and linked.

- ``cisa-advisories``: the cybersecurity advisories (not the ICS advisories, which come
  by the dozen). Many are written jointly with other agencies; US agencies' text is
  public domain too, but foreign agencies' is not (UK NCSC, ASD's ACSC, Canada's Cyber
  Centre and others), so an advisory naming one of those goes as its summary and a link.
- ``cisa-kev``: one post a day with the vulnerabilities added to the Known Exploited
  Vulnerabilities catalog the day before, none on days with none.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from . import Item, article_markdown, clip, get_json, paragraphs
from .feeds import MAX_BODY, FeedSource, _subject, _when

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
KEV_PAGE = "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"
PD_NOTE = ("CISA's work is US government work, in the public domain in the US; CISA does "
           "not endorse this post or Unseenet.")

# Foreign agencies that write advisories with CISA: their text is not public domain.
FOREIGN = re.compile(
    r"National Cyber Security Cent(?:re|er)|\bNCSC\b|Australian Signals Directorate|"
    r"Australian Cyber Security Cent|\bACSC\b|Canadian Centre for Cyber Security|"
    r"Communications Security Establishment|Bundesamt für Sicherheit|\bBSI\b|\bANSSI\b|"
    r"\bAIVD\b|\bMIVD\b|National Police Agency|\bNISC\b|National Intelligence Service|"
    r"\bKISA\b|Cyber Security Agency of Singapore|\bCERT-[A-Z]{2}\b|\bNÚKIB\b",
    re.I)


class CisaAdvisories(FeedSource):
    name = "cisa-advisories"
    url = "https://www.cisa.gov/cybersecurity-advisories/cybersecurity-advisories.xml"

    def item(self, entry):
        body = article_markdown(entry["html"], entry["link"])
        if not body:
            return None
        when = _when(entry)
        top = f"*A cybersecurity advisory from [CISA]({entry['link']}){', ' + when if when else ''}.*"
        if FOREIGN.search(body):
            lines = [top, "", _summary(body), "",
                     f"**[Read the whole advisory at CISA]({entry['link']})**", "", "---",
                     "Written by CISA with other agencies, some of them outside the US whose text "
                     "is not in the public domain - so only the summary is here. " + PD_NOTE]
        else:
            more = f"*The rest of the advisory is at [CISA]({entry['link']}).*"
            lines = [top, "", clip(body, MAX_BODY, more), "", "---",
                     "From CISA (https://www.cisa.gov), converted to plain text and markdown. "
                     + PD_NOTE]
        return Item(id="cisa:" + entry["id"], subject=_subject(entry["title"]),
                    body="\n".join(l for l in lines) + "\n", published=entry["published"],
                    link=entry["link"])


def _summary(body: str) -> str:
    """The advisory's executive summary: the text after "Executive Summary", in the same
    paragraph or the next one; else its first paragraph of text."""
    paras = paragraphs(body)
    for n, p in enumerate(paras):
        if p.lstrip("#* ").startswith("Executive Summary"):
            rest = p.lstrip("#* ").removeprefix("Executive Summary").strip(" *:")
            if rest:
                return rest
            return paras[n + 1] if n + 1 < len(paras) else ""
    # older advisories: the first paragraph of real text
    return next((p for p in paras if len(p) > 120 and not p.startswith(("#", "|", "-", "*"))), "")


def _md(text: str) -> str:
    return " ".join(str(text or "").split()).replace("*", "\\*")


class CisaKev:
    """One post a day: the vulnerabilities CISA added to its KEV catalog the day before
    (complete by then), posted the morning after."""

    name = "cisa-kev"

    def __init__(self, url: str = KEV_URL, fetch=get_json):
        self.url, self._get = url, fetch

    def items_for(self, catalog: dict, day: date) -> list[Item]:
        added = [v for v in catalog.get("vulnerabilities", []) if v.get("dateAdded") == day.isoformat()]
        if not added:
            return []
        lines = [f"*CISA added {len(added)} known exploited "
                 f"{'vulnerability' if len(added) == 1 else 'vulnerabilities'} to its "
                 f"[catalog]({KEV_PAGE}) on {day:%B} {day.day}, {day:%Y}.*", ""]
        for v in sorted(added, key=lambda v: v.get("cveID", "")):
            cve = v.get("cveID", "")
            ransom = v.get("knownRansomwareCampaignUse", "")
            lines += [f"### [{cve}](https://nvd.nist.gov/vuln/detail/{cve}): {_md(v.get('vulnerabilityName'))}",
                      "", f"**{_md(v.get('vendorProject'))} {_md(v.get('product'))}**"
                      f"{' · used in ransomware campaigns' if ransom == 'Known' else ''}", "",
                      _md(v.get("shortDescription")), "",
                      f"*Required action:* {_md(v.get('requiredAction'))}"
                      + (f" *Due* {v['dueDate']} *for US federal agencies.*" if v.get("dueDate") else ""),
                      ""]
            links = re.findall(r"https://[^\s;]+", v.get("notes", ""))
            if links:
                lines += ["*Notes:* " + " · ".join(f"<{u}>" for u in links[:5]), ""]
        lines += ["---", f"From CISA's Known Exploited Vulnerabilities catalog ({KEV_PAGE}). " + PD_NOTE]
        subject = (f"{len(added)} known exploited vulnerabilit{'y' if len(added) == 1 else 'ies'} "
                   f"added {day:%B} {day.day}: " + ", ".join(sorted({_md(v.get('vendorProject'))
                                                                    for v in added})))
        return [Item(id=f"kev:{day.isoformat()}", subject=_subject(subject), body="\n".join(lines) + "\n",
                     published=datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
                     + timedelta(days=1), link=KEV_PAGE)]

    def fetch(self, today: date) -> list[Item]:
        catalog = self._get(self.url)
        return [i for d in (today - timedelta(days=2), today - timedelta(days=1))
                for i in self.items_for(catalog, d)]
