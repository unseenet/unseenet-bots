"""Content sources. A source turns something on the web into :class:`Item`s.

To add one: write a module here with a class that has ``name`` and
``fetch(today) -> list[Item]``, and add it to :func:`_registry`. Every item
carries its own credit line, as the source's licence asks.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Protocol

from .. import __version__

USER_AGENT = (f"unseenet-bots/{__version__} "
              "(+https://github.com/unseenet/unseenet-bots)")


@dataclass
class Item:
    id: str            # stable, so a restart does not post it twice
    subject: str
    body: str          # markdown, ending with the credit line
    published: datetime | None = None   # when the source published it (UTC), if known


class Source(Protocol):
    name: str

    def fetch(self, today: date) -> list[Item]: ...


MAX_DOWNLOAD = 8 * 1024 * 1024


def get_bytes(url: str, accept: str = "*/*", timeout: float = 30.0) -> bytes:
    """GET a document, saying who we are (Wikimedia asks for it), at most 8 MiB."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError(f"{url}: larger than {MAX_DOWNLOAD} bytes")
    return data


def get_json(url: str, timeout: float = 30.0) -> dict:
    return json.loads(get_bytes(url, "application/json", timeout).decode("utf-8"))


_TAG = re.compile(r"<[^>]+>")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_LINK = re.compile(r'<a\b[^>]*\bhref="([^"]*)"[^>]*>(.*?)</a>', re.S)
_SPACE = re.compile(r"\s+")


def html_to_markdown(html: str, base: str = "") -> str:
    """Just enough HTML to markdown for short snippets: links, bold and italics,
    everything else as text. Relative links (``./Page``) are made absolute."""
    text = _COMMENT.sub("", html)

    def link(m: re.Match) -> str:
        href, label = m.group(1), _TAG.sub("", m.group(2))
        if href.startswith("./"):
            href = base + href[2:]
        elif href.startswith("//"):
            href = "https:" + href
        return f"[{label}]({href})" if href.startswith("http") else label

    text = _LINK.sub(link, text)
    text = re.sub(r"</?(b|strong)\b[^>]*>", "**", text)
    text = re.sub(r"</?(i|em)\b[^>]*>", "*", text)
    text = _TAG.sub("", text)
    return _SPACE.sub(" ", unescape(text)).strip()


def html_to_text(html: str) -> str:
    """Plain text of an HTML snippet (for subjects)."""
    return _SPACE.sub(" ", unescape(_TAG.sub("", _COMMENT.sub("", html)))).strip()


class _Markdown(HTMLParser):
    """HTML of an article to markdown: paragraphs, headings, lists, quotes, links,
    bold and italics. Images, figures, scripts, iframes and forms are left out
    (images often have licences of their own)."""

    SKIP = {"script", "style", "iframe", "figure", "figcaption", "form", "button",
            "noscript", "svg", "video", "audio", "picture", "aside", "nav", "select"}
    HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
    BLOCKS = {"p", "div", "section", "article", "header", "footer", "table", "tr",
              "ul", "ol", "li", "blockquote", "pre"} | HEADINGS

    def __init__(self, base: str = ""):
        super().__init__(convert_charrefs=True)
        origin = re.match(r"^(https?://[^/]+)", base)
        self.base, self.origin = base, origin.group(1) if origin else ""
        self.blocks: list[str] = []        # finished paragraphs
        self.cur: list[str] = []           # the paragraph being written
        self.lead = ""                     # "### ", "- ", "1. " for the current block
        self.skip = 0
        self.quote = 0
        self.lists: list[list] = []        # [kind, counter]
        self.links: list[tuple[int, str]] = []
        self.marks: list[tuple[int, str, str]] = []     # (start, tag, "**" or "*")

    def _flush(self) -> None:
        text = _SPACE.sub(" ", "".join(self.cur)).strip()
        text = re.sub(r"\*\*\s*\*\*", "", text)
        if text:
            line = self.lead + text
            self.blocks.append("> " * self.quote + line)
        self.cur, self.lead = [], ""

    def _href(self, href: str) -> str:
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("./"):
            return self.base + href[2:]
        if href.startswith("/"):
            return self.origin + href
        return href

    def handle_starttag(self, tag, attrs):
        if self.skip or tag in self.SKIP:
            if tag in self.SKIP:
                self.skip += 1
            return
        if tag in self.BLOCKS:
            self._flush()
            self.marks = []
        if tag in self.HEADINGS:
            self.lead = "### "
        elif tag == "blockquote":
            self.quote += 1
        elif tag in ("ul", "ol"):
            self.lists.append([tag, 0])
        elif tag == "li":
            kind = self.lists[-1] if self.lists else ["ul", 0]
            kind[1] += 1
            indent = "  " * max(0, len(self.lists) - 1)
            self.lead = indent + (f"{kind[1]}. " if kind[0] == "ol" else "- ")
        elif tag == "br":
            self.cur.append(" ")
        elif tag in ("b", "strong", "i", "em"):
            self.marks.append((len(self.cur), tag, "**" if tag in ("b", "strong") else "*"))
        elif tag == "a":
            self.links.append((len(self.cur), self._href(dict(attrs).get("href") or "")))

    def handle_endtag(self, tag):
        if self.skip:
            if tag in self.SKIP:
                self.skip -= 1
            return
        if tag in ("b", "strong", "i", "em"):
            for n in range(len(self.marks) - 1, -1, -1):
                at, open_tag, mark = self.marks[n]
                if open_tag == tag:
                    del self.marks[n]
                    raw = "".join(self.cur[at:])
                    inner = _SPACE.sub(" ", raw).strip().strip("*").strip()
                    if inner:          # markdown wants **text**, not ** text **
                        lead = " " if raw[:1].isspace() else ""
                        tail = " " if raw[-1:].isspace() else ""
                        self.cur[at:] = [f"{lead}{mark}{inner}{mark}{tail}"]
                    else:
                        self.cur[at:] = [raw]
                    break
        elif tag == "a" and self.links:
            at, href = self.links.pop()
            label = _SPACE.sub(" ", "".join(self.cur[at:])).strip()
            if href.startswith(("http://", "https://")) and label:
                self.cur[at:] = [f"[{label}]({href})"]
        elif tag in self.BLOCKS:
            self._flush()
            if tag == "blockquote" and self.quote:
                self.quote -= 1
            elif tag in ("ul", "ol") and self.lists:
                self.lists.pop()

    def handle_data(self, data):
        if not self.skip:
            self.cur.append(data)

    def markdown(self) -> str:
        self._flush()
        out = []
        for block in self.blocks:
            # list items and quote lines stay together; other blocks are paragraphs
            tight = out and re.match(r"^(> )*\s*(- |\d+\. )", block) \
                and re.match(r"^(> )*\s*(- |\d+\. )", out[-1])
            out.append(("\n" if tight else "\n\n") + block if out else block)
        return "".join(out).strip()


def article_markdown(html: str, base: str = "") -> str:
    """A whole article's HTML as markdown paragraphs (see :class:`_Markdown`)."""
    p = _Markdown(base)
    p.feed(html)
    p.close()
    return p.markdown()


def paragraphs(markdown: str) -> list[str]:
    return [b for b in markdown.split("\n\n") if b.strip()]


def clip(markdown: str, limit: int, more: str) -> str:
    """Whole paragraphs up to ``limit`` characters; ``more`` says where the rest is.
    Articles must fit in a post (64 KiB including headers)."""
    if len(markdown) <= limit:
        return markdown
    out, size = [], 0
    for para in paragraphs(markdown):
        if size + len(para) > limit and out:
            break
        out.append(para)
        size += len(para) + 2
    return "\n\n".join(out) + "\n\n" + more


def _registry() -> dict[str, type]:
    from .feeds import EFF, GlobalVoices, NasaImageOfTheDay, TheConversation
    from .wikipedia import InTheNews, OnThisDay
    return {cls.name: cls for cls in (InTheNews, OnThisDay, GlobalVoices, TheConversation,
                                      EFF, NasaImageOfTheDay)}


def get_source(name: str, **options) -> Source:
    sources = _registry()
    if name not in sources:
        raise ValueError(f"unknown source {name!r}; known: {', '.join(sorted(sources))}")
    return sources[name](**options)
