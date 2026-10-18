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
from datetime import date
from html import unescape
from typing import Protocol

from .. import __version__

USER_AGENT = (f"unseenet-bots/{__version__} "
              "(+https://github.com/unseenet/unseenet-bots)")


@dataclass
class Item:
    id: str            # stable, so a restart does not post it twice
    subject: str
    body: str          # markdown, ending with the credit line


class Source(Protocol):
    name: str

    def fetch(self, today: date) -> list[Item]: ...


def get_json(url: str, timeout: float = 30.0) -> dict:
    """GET a JSON document, saying who we are (Wikimedia asks for it)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


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


def _registry() -> dict[str, type]:
    from .wikipedia import InTheNews, OnThisDay
    return {cls.name: cls for cls in (InTheNews, OnThisDay)}


def get_source(name: str, **options) -> Source:
    sources = _registry()
    if name not in sources:
        raise ValueError(f"unknown source {name!r}; known: {', '.join(sorted(sources))}")
    return sources[name](**options)
