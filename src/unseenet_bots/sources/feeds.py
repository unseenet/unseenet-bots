"""Sources from RSS and Atom feeds whose licences allow reposting.

Each post says who wrote it, where it first appeared, under which licence,
and links to the original - as each publisher asks:

- Global Voices: CC BY 3.0, the whole story, credit at the top of the post
  (https://globalvoices.org/about/global-voices-attribution-policy/);
- The Conversation: CC BY-ND 4.0, but not every article may be republished,
  so only the opening paragraphs with "Read the full article on The
  Conversation" (https://theconversation.com/republishing-guidelines);
- EFF Deeplinks: CC BY 4.0, the whole post;
- NASA Image of the Day: NASA's own text and images are not copyrighted
  (https://www.nasa.gov/nasa-brand-center/images-and-media/); the post says
  NASA does not endorse it.

Images are left out (they often have licences of their own); each post links
to the original, and NASA's picture is linked.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape

from . import Item, Picture, article_markdown, clip, get_bytes, html_to_text, paragraphs

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
DC_CREATOR = "{http://purl.org/dc/elements/1.1/}creator"
MAX_BODY = 40_000            # characters; a post is at most 64 KiB in all
MAX_SUBJECT = 120


def _date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        dt = parsedate_to_datetime(text)                       # RSS: RFC 822
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))   # Atom: RFC 3339
        except ValueError:
            return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _subject(title: str) -> str:
    title = " ".join(html_to_text(title).split())
    return title if len(title) <= MAX_SUBJECT else title[:MAX_SUBJECT - 1].rstrip() + "…"


def _text(el, path: str) -> str:
    found = el.find(path)
    return (found.text or "").strip() if found is not None else ""


def parse_feed(data: bytes) -> list[dict]:
    """Entries of an RSS 2.0 or Atom feed, oldest first, as plain dicts:
    id, title, link, author, published, html (the fullest text there is), summary."""
    root = ET.fromstring(data)
    entries = []
    if root.tag == ATOM + "feed":
        for e in root.findall(ATOM + "entry"):
            link = next((ln.get("href", "") for ln in e.findall(ATOM + "link")
                         if ln.get("rel", "alternate") == "alternate"), "")
            authors = [_text(a, ATOM + "name") for a in e.findall(ATOM + "author")]
            entries.append({"id": _text(e, ATOM + "id") or link, "title": _text(e, ATOM + "title"),
                            "link": link, "author": ", ".join(a for a in authors if a),
                            "published": _date(_text(e, ATOM + "published") or _text(e, ATOM + "updated")),
                            "html": _text(e, ATOM + "content"), "summary": _text(e, ATOM + "summary"),
                            "rights": _text(e, ATOM + "rights")})
    else:
        for e in root.findall("channel/item"):
            link = _text(e, "link")
            entries.append({"id": _text(e, "guid") or link, "title": _text(e, "title"), "link": link,
                            "author": _text(e, DC_CREATOR), "published": _date(_text(e, "pubDate")),
                            "html": _text(e, CONTENT) or _text(e, "description"),
                            "summary": _text(e, "description"), "rights": "",
                            "image": (e.find("enclosure").get("url", "")
                                      if e.find("enclosure") is not None else "")})
    entries.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc))
    return entries


class FeedSource:
    """Base for the feeds below: fetch, parse, one :class:`Item` per entry."""

    name = ""
    url = ""

    def __init__(self, url: str | None = None, fetch=get_bytes):
        self.url, self._get = url or self.url, fetch

    def item(self, entry: dict) -> Item | None:
        raise NotImplementedError

    def fetch_items(self, data: bytes) -> list[Item]:
        return [i for i in (self.item(e) for e in parse_feed(data)) if i is not None]

    def fetch(self, today: date) -> list[Item]:
        return self.fetch_items(self._get(self.url, "application/rss+xml, application/atom+xml"))


def _when(entry: dict) -> str:
    dt = entry.get("published")
    return f"{dt:%B} {dt.day}, {dt:%Y}" if dt else ""


class GlobalVoices(FeedSource):
    """Global Voices: citizen reporting from around the world, whole stories."""

    name = "globalvoices"
    url = "https://globalvoices.org/feed/"

    def item(self, entry):
        body = "\n\n".join(p for p in paragraphs(article_markdown(entry["html"], entry["link"]))
                            if not p.startswith("Originally published on"))   # we say it on top
        if not body:
            return None
        who = f" by {entry['author']}" if entry["author"] else ""
        top = (f"*This story{who} originally appeared on [Global Voices]({entry['link']})"
               f"{' on ' + _when(entry) if _when(entry) else ''}.*")
        more = f"*The rest of the story is on [Global Voices]({entry['link']}).*"
        credit = ("This story is published by Global Voices under CC BY 3.0 "
                  "(https://creativecommons.org/licenses/by/3.0/). Changes: converted to plain "
                  "text and markdown, images left out" + (", shortened" if len(body) > MAX_BODY else "")
                  + ". This post is under the same licence.")
        return Item(id="gv:" + entry["id"], subject=_subject(entry["title"]),
                    body=f"{top}\n\n{clip(body, MAX_BODY, more)}\n\n---\n{credit}\n",
                    published=entry["published"])


class TheConversation(FeedSource):
    """The Conversation: news analysis by researchers. Only the opening
    paragraphs, unchanged, and a link to the whole article, as their
    republishing guidelines allow for extracts."""

    name = "theconversation"
    url = "https://theconversation.com/global/articles.atom"

    def __init__(self, url=None, paragraphs: int = 3, fetch=get_bytes):
        super().__init__(url, fetch)
        self.count = paragraphs

    def item(self, entry):
        paras = [p for p in paragraphs(article_markdown(entry["html"], entry["link"]))
                 if not p.startswith("### ") and "Read more:" not in p[:20]][: self.count]
        if not paras:
            return None
        who = f"By {entry['author']}" if entry["author"] else ""
        lines = ([f"*{who}*", ""] if who else []) + ["\n\n".join(paras), "",
                 f"**[Read the full article on The Conversation]({entry['link']})**", "", "---",
                 "From The Conversation, under CC BY-ND 4.0 "
                 "(https://creativecommons.org/licenses/by-nd/4.0/): the opening paragraphs, "
                 "unchanged except as plain text."]
        return Item(id="tc:" + entry["id"], subject=_subject(entry["title"]),
                    body="\n".join(lines) + "\n", published=entry["published"])


class EFF(FeedSource):
    """EFF Deeplinks: digital rights, privacy and free expression, whole posts."""

    name = "eff"
    url = "https://www.eff.org/rss/updates.xml"

    def item(self, entry):
        body = article_markdown(unescape(entry["html"]) if "&lt;" in entry["html"] else entry["html"],
                                entry["link"])
        # EFF's privacy-friendly embeds: a URL-encoded player and a note about it
        body = "\n\n".join(p for p in paragraphs(body)
                            if not p.startswith("%3C") and "This embed will serve content" not in p)
        if not body:
            return None
        who = f" by {entry['author']}" if entry["author"] else ""
        more = f"*The rest of the post is on [EFF Deeplinks]({entry['link']}).*"
        lines = [f"*Posted{who} on [EFF Deeplinks]({entry['link']})"
                 f"{', ' + _when(entry) if _when(entry) else ''}.*", "",
                 clip(body, MAX_BODY, more), "", "---",
                 "From the Electronic Frontier Foundation (https://www.eff.org), under CC BY 4.0 "
                 "(https://creativecommons.org/licenses/by/4.0/). Changes: converted to plain text "
                 "and markdown, images left out. This post is under the same licence."]
        return Item(id="eff:" + entry["id"], subject=_subject(entry["title"]),
                    body="\n".join(lines) + "\n", published=entry["published"])


class NasaImageOfTheDay(FeedSource):
    """NASA's Image of the Day: the caption, with a link to the picture."""

    name = "nasa-iotd"
    url = "https://www.nasa.gov/feeds/iotd-feed/"

    def item(self, entry):
        caption = article_markdown(entry["html"], entry["link"]) or html_to_text(entry["summary"])
        if not caption:
            return None
        lines = [caption, ""]
        if entry.get("image"):
            lines += [f"**[See the picture]({entry['image']})** - and the "
                      f"[whole page at NASA]({entry['link']}).", ""]
        else:
            lines += [f"**[See the picture at NASA]({entry['link']})**", ""]
        lines += ["---", "NASA Image of the Day (https://www.nasa.gov/image-of-the-day/). NASA "
                         "material is not copyrighted; NASA does not endorse this post or Unseenet."]
        pics = [Picture(entry["image"], alt=html_to_text(entry["title"]), page=entry["link"],
                        licence="Public domain", author="NASA")] if entry.get("image") else []
        return Item(id="nasa:" + entry["id"], subject=_subject(entry["title"]),
                    body="\n".join(lines) + "\n", published=entry["published"], pictures=pics)
