"""New arXiv papers in a category (#39), from arXiv's RSS feed (rss.arxiv.org, as
arXiv asks programs to use). Only the metadata - title, authors, abstract - which
arXiv makes available under CC0; never the paper, which has its own licence and is
linked on its abstract page. arXiv asks for thanks for its interoperability.

By default one **daily digest** per category - the day's new papers as links with
their authors - since cs.AI alone has well over a hundred a day; ``per_paper = true``
posts each new paper with its abstract instead (use ``max_per_day``)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

from . import Item, get_bytes
from .feeds import MAX_BODY, _date, _subject

ARXIV_NS = "{http://arxiv.org/schemas/atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
THANKS = ("Metadata from arXiv (https://arxiv.org), CC0; each paper has its own licence, "
          "on its page. Thank you to arXiv for use of its open access interoperability.")


def _authors(text: str, most: int = 4) -> str:
    names = [n.strip() for n in re.sub(r"\s*\([^)]*\)", "", text or "").split(",") if n.strip()]
    return ", ".join(names[:most]) + (" et al." if len(names) > most else "")


def _esc(text: str) -> str:
    return " ".join((text or "").split()).replace("[", "\\[").replace("]", "\\]").replace("*", "\\*")


class Arxiv:
    name = "arxiv"

    def __init__(self, category: str = "cs.CR", per_paper: bool = False,
                 types: list[str] | None = None, fetch=get_bytes):
        if not re.fullmatch(r"[a-z-]+(\.[A-Za-z-]+)?", category):
            raise ValueError(f"not an arXiv category: {category!r}")
        self.category, self.per_paper = category, bool(per_paper)
        self.types = set(types or ["new"])
        self._get = fetch

    def papers(self, data: bytes) -> tuple[list[dict], object]:
        ch = ET.fromstring(data).find("channel")
        out = []
        for it in ch.findall("item"):
            if (it.findtext(ARXIV_NS + "announce_type") or "").strip() not in self.types:
                continue
            desc = it.findtext("description") or ""
            abstract = desc.split("Abstract:", 1)[1].strip() if "Abstract:" in desc else ""
            link = (it.findtext("link") or "").strip()
            out.append({"id": link.rsplit("/", 1)[-1], "title": it.findtext("title") or "",
                        "link": link, "authors": it.findtext(DC + "creator") or "",
                        "abstract": abstract})
        return out, _date(ch.findtext("pubDate"))

    def items_from(self, data: bytes) -> list[Item]:
        papers, when = self.papers(data)
        if not papers:
            return []
        if self.per_paper:
            return [Item(id=f"arxiv:{p['id']}", subject=_subject(p["title"]),
                         body=(f"*{_esc(_authors(p['authors'], 8))}*\n\n{_esc(p['abstract'])}\n\n"
                               f"**[The paper on arXiv]({p['link']})**\n\n---\n{THANKS}\n"),
                         published=when, link=p["link"]) for p in papers]
        day = when.date() if when else None
        listing = f"https://arxiv.org/list/{self.category}/new"
        lines = [f"*{len(papers)} new papers in {self.category} on arXiv"
                 + (f", {day:%B} {day.day}, {day:%Y}" if day else "") + f".* [The listing]({listing})", ""]
        size = 0
        for n, p in enumerate(papers):
            line = f"- [{_esc(p['title'])}]({p['link']}) - {_esc(_authors(p['authors']))}"
            if size + len(line) > MAX_BODY:
                lines.append(f"- *… and {len(papers) - n} more in [the listing]({listing}).*")
                break
            lines.append(line)
            size += len(line) + 1
        lines += ["", "---", THANKS]
        subject = (f"{self.category}: {len(papers)} new papers"
                   + (f", {day:%B} {day.day}" if day else ""))
        return [Item(id=f"arxiv:{self.category}:{day.isoformat() if day else 'x'}", subject=subject,
                     body="\n".join(lines) + "\n", published=when, link=listing)]

    def fetch(self, today: date) -> list[Item]:
        return self.items_from(self._get(f"https://rss.arxiv.org/rss/{self.category}",
                                         "application/rss+xml"))
