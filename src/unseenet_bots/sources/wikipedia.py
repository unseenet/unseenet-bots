"""Wikipedia's daily feed: "In the news" and "On this day".

Text from Wikipedia is under CC BY-SA 4.0. Each post credits Wikipedia,
links to the articles it draws on (whose histories name the authors), and
says that the post itself is under the same licence.
"""

from __future__ import annotations

import re
from datetime import date

from . import Item, Picture, commons_licence, commons_page, get_json, html_to_markdown, html_to_text

_PICTURED = re.compile(r'href="\./([^"]+)"[^>]*>[^<]*</a>\s*(?:<i>)?\s*\(pictured\)')

FEED = "https://{lang}.wikipedia.org/api/rest_v1/feed/featured/{d:%Y}/{d:%m}/{d:%d}"
LICENCE = "CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)"
MAX_SUBJECT = 120


def _feed(lang: str, today: date, fetch=get_json) -> dict:
    return fetch(FEED.format(lang=lang, d=today))


def _page_url(page: dict) -> str:
    return page.get("content_urls", {}).get("desktop", {}).get("page", "")


def _subject(plain: str) -> str:
    return plain if len(plain) <= MAX_SUBJECT else plain[:MAX_SUBJECT - 1].rstrip() + "…"


class InTheNews:
    """One post per story in Wikipedia's "In the news", so each can be
    commented on. A story is known by its main article, so a story that is
    reworded during the day is not posted again."""

    name = "wikipedia-news"

    def __init__(self, lang: str = "en", fetch=get_json):
        self.lang, self._get = lang, fetch

    def fetch_items(self, data: dict) -> list[Item]:
        base = f"https://{self.lang}.wikipedia.org/wiki/"
        items = []
        for story in data.get("news", []):
            html = story.get("story", "")
            text = html_to_markdown(html, base)
            if not text:
                continue
            main = re.search(r"<b\b[^>]*>\s*<a\b[^>]*href=\"\./([^\"]+)\"", html)
            pages = story.get("links", [])
            key = main.group(1) if main else (pages[0].get("title") if pages else text)
            lines = [text, ""]
            lead = next((p for p in pages if p.get("title") == key), pages[0] if pages else None)
            if lead and lead.get("extract"):
                lines += [f"> {lead['extract']}", ""]
            if pages:
                lines.append("Read more on Wikipedia:")
                lines += [f"- [{p.get('normalizedtitle') or p.get('title', '')}]({_page_url(p)})"
                          for p in pages if _page_url(p)]
                lines.append("")
            lines.append(f"From Wikipedia's \"In the news\" ({base}Portal:Current_events). "
                         f"Text from Wikipedia under {LICENCE}; this post is under the same licence.")
            items.append(Item(id=f"itn:{self.lang}:{key}", subject=_subject(html_to_text(html)),
                              body="\n".join(lines) + "\n", pictures=self._pictured(html, pages)))
        return items

    def _pictured(self, html: str, pages: list[dict]) -> list[Picture]:
        """The story's picture - the page marked "(pictured)" - if it has one. Its
        licence is looked up on Commons only when the bot asks (unseenet-bots#7)."""
        m = _PICTURED.search(html)
        page = next((p for p in pages if m and p.get("title") == m.group(1)), None)
        thumb = (page or {}).get("thumbnail") or {}
        url = thumb.get("source", "")
        if not url.startswith("https://upload.wikimedia.org/"):
            return []
        url = re.sub(r"/\d+px-", "/960px-", url)       # a standard size, enough to read
        return [Picture(url, alt=page.get("normalizedtitle") or page.get("title", ""),
                        page=commons_page(url) or _page_url(page),
                        lookup=lambda: commons_licence(url, self._get))]

    def fetch(self, today: date) -> list[Item]:
        return self.fetch_items(_feed(self.lang, today, self._get))


class OnThisDay:
    """One post a day with the day's selected anniversaries."""

    name = "wikipedia-onthisday"

    def __init__(self, lang: str = "en", count: int = 6, fetch=get_json):
        self.lang, self.count, self._get = lang, count, fetch

    def fetch_items(self, data: dict, today: date) -> list[Item]:
        events = sorted(data.get("onthisday", []), key=lambda e: e.get("year", 0))[: self.count]
        if not events:
            return []
        lines = []
        for e in events:
            pages = [p for p in e.get("pages", []) if _page_url(p)]
            more = f" ([{pages[0].get('normalizedtitle', '')}]({_page_url(pages[0])}))" if pages else ""
            lines.append(f"- **{e.get('year', '?')}**: {e.get('text', '').strip()}{more}")
        day = f"{today:%B} {today.day}"
        lines += ["", f"From Wikipedia's \"On this day\" "
                      f"(https://{self.lang}.wikipedia.org/wiki/Wikipedia:Selected_anniversaries). "
                      f"Text from Wikipedia under {LICENCE}; this post is under the same licence."]
        return [Item(id=f"otd:{self.lang}:{today.isoformat()}", subject=f"On this day: {day}",
                     body="\n".join(lines) + "\n")]

    def fetch(self, today: date) -> list[Item]:
        return self.fetch_items(_feed(self.lang, today, self._get), today)
