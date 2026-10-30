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
  NASA does not endorse it;
- UN News: news material may be used with credit when the UN is told
  (https://unognewsroom.org/copyright), so the feed's summary and a link;
  never its pictures (UN Photo needs written permission for the web).

Images are left out (they often have licences of their own); each post links
to the original, and NASA's picture is linked.
"""

from __future__ import annotations

import re
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
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        # some feeds (Rest of World) put a bare "&" in an attribute; escape those and retry
        root = ET.fromstring(re.sub(rb"&(?!#?[A-Za-z0-9]+;)", b"&amp;", data))
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
                            "comments": _text(e, "comments"),
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
                    published=entry["published"], link=entry["link"])


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
                    body="\n".join(lines) + "\n", published=entry["published"], link=entry["link"])


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
                    body="\n".join(lines) + "\n", published=entry["published"], link=entry["link"])


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
                    body="\n".join(lines) + "\n", published=entry["published"], pictures=pics,
                    link=entry["link"])


class UNNews(FeedSource):
    """UN News: the feed's own short summary of each story, a link to the whole
    story and a credit line. The UN allows news material "as long as the
    appropriate credit is given and the United Nations is advised"
    (https://unognewsroom.org/copyright); the project has told the UN. No
    pictures: UN Photo needs written permission for the web and many pictures
    are from other agencies, so run this source with ``pictures = "no"``."""

    name = "un-news"
    url = "https://news.un.org/feed/subscribe/en/news/all/rss.xml"

    def item(self, entry):
        summary = " ".join(html_to_text(entry["summary"]).split())
        # the feed links through a redirect; the guid is the story's own address
        link = entry["id"] if entry["id"].startswith("https://news.un.org/") else entry["link"]
        if not summary or not link:
            return None
        when = _when(entry)
        lines = [summary, "", f"**[Read the whole story on UN News]({link})**", "", "---",
                 f"From UN News (https://news.un.org/en/){', ' + when if when else ''}: the "
                 "story's summary, unchanged except as plain text. Unseenet is not affiliated "
                 "with or endorsed by the United Nations."]
        return Item(id="un:" + link, subject=_subject(entry["title"]),
                    body="\n".join(lines) + "\n", published=entry["published"], link=link)


def _ngo_body(entry: dict) -> str:
    """The text without picture captions ("Click to expand Image ...") or WordPress's
    "The post ... appeared first on ..." footer."""
    return "\n\n".join(p for p in paragraphs(article_markdown(entry["html"], entry["link"]))
                       if not p.startswith(("Click to expand Image", "The post [")))


def _byline(entry: dict, org: str) -> str:
    """"by <author>" unless the feed names only the organisation itself."""
    who = " ".join((entry.get("author") or "").split())
    return f" by {who}" if who and who != org else ""


class Amnesty(FeedSource):
    """Amnesty International's news, whole: their own material is CC BY-NC-ND 4.0
    (https://www.amnesty.org/en/about-us/permissions/); pictures credited to others are
    not, and all pictures are left out. Unchanged but for plain text and markdown."""

    name = "amnesty"
    url = "https://www.amnesty.org/en/feed/"

    def item(self, entry):
        body = _ngo_body(entry)
        if not body:
            return None
        more = f"*The rest is on [Amnesty International]({entry['link']}).*"
        lines = [f"*Published{_byline(entry, 'Amnesty International')} on "
                 f"[Amnesty International]({entry['link']})"
                 f"{', ' + _when(entry) if _when(entry) else ''}.*", "",
                 clip(body, MAX_BODY, more), "", "---",
                 "© Amnesty International, under CC BY-NC-ND 4.0 "
                 "(https://creativecommons.org/licenses/by-nc-nd/4.0/): unchanged except as plain "
                 "text and markdown, pictures left out. Amnesty International does not endorse "
                 "this post or Unseenet."]
        return Item(id="amnesty:" + entry["id"], subject=_subject(entry["title"]),
                    body="\n".join(lines) + "\n", published=entry["published"], link=entry["link"])


class HumanRightsWatch(FeedSource):
    """Human Rights Watch's news, whole: CC BY-NC-ND 4.0
    (https://www.hrw.org/permissions). The pictures and their captions are left out."""

    name = "hrw"
    url = "https://www.hrw.org/rss/news"

    def item(self, entry):
        body = _ngo_body(entry)
        if not body:
            return None
        more = f"*The rest is on [Human Rights Watch]({entry['link']}).*"
        lines = [f"*Published{_byline(entry, 'Human Rights Watch')} on "
                 f"[Human Rights Watch]({entry['link']})"
                 f"{', ' + _when(entry) if _when(entry) else ''}.*", "",
                 clip(body, MAX_BODY, more), "", "---",
                 "© Human Rights Watch, under CC BY-NC-ND 4.0 "
                 "(https://creativecommons.org/licenses/by-nc-nd/4.0/): unchanged except as plain "
                 "text and markdown, pictures and captions left out. Human Rights Watch does not "
                 "endorse this post or Unseenet."]
        return Item(id="hrw:" + entry["id"], subject=_subject(entry["title"]),
                    body="\n".join(lines) + "\n", published=entry["published"], link=entry["link"])


class Mongabay(FeedSource):
    """Mongabay's conservation news: the feed's own opening of each article, unchanged,
    with "Read the full article on Mongabay", as their republishing guidelines allow
    (https://news.mongabay.com/copyright/creative-commons/). No pictures."""

    name = "mongabay"
    url = "https://news.mongabay.com/feed/"

    def item(self, entry):
        opening = " ".join(html_to_text(entry["html"] or entry["summary"]).split())
        opening = opening.split("This article was originally published on Mongabay")[0]
        opening = opening.removesuffix("[…]").removesuffix("[...]").rstrip()
        if not opening:
            return None
        lines = ([f"*By {' '.join(entry['author'].split())}*", ""] if entry["author"] else []) + [
            opening + (" …" if not opening.endswith((".", "”", "\"", "?", "!", "…")) else ""), "",
            f"**[Read the full article on Mongabay]({entry['link']})**", "", "---",
            "From Mongabay (https://news.mongabay.com): the opening of the article, unchanged "
            "except as plain text. Mongabay does not endorse this post or Unseenet."]
        return Item(id="mongabay:" + entry["id"], subject=_subject(entry["title"]),
                    body="\n".join(lines) + "\n", published=entry["published"], link=entry["link"])



def _untracked(url: str) -> str:
    """A link without its ``utm_*`` tracking parameters."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_")]
    return urlunsplit(parts._replace(query=urlencode(query)))


class Headlines(FeedSource):
    """Any RSS or Atom feed, as headlines only (#35): the title, the link, the site and
    the feed's discussion link (Lobsters' ``<comments>``) - never its text or pictures,
    for sources whose terms allow no republishing (ProPublica, Rest of World, Ars
    Technica, The Register, LWN, Lobsters). Runs only with ``mode = "headlines"``.
    ``options = { url = "...", site = "Ars Technica" }``."""

    name = "headlines"
    headlines_only = True

    def __init__(self, url: str | None = None, site: str = "", fetch=get_bytes):
        if not (url or self.url):
            raise ValueError("the headlines source needs options.url, the feed's address")
        super().__init__(url, fetch)
        self.site = site

    def item(self, entry):
        if not entry["link"] or not entry["title"].strip():
            return None
        comments = entry.get("comments", "")
        return Item(id="hl:" + (entry["id"] or entry["link"]), subject=_subject(entry["title"]),
                    body="", published=entry["published"], link=_untracked(entry["link"]),
                    site=self.site,
                    discussion=comments if comments.startswith("https://") else "")
