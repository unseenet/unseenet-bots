"""Comics whose licence allows the pictures (#40), new ones and from the archive (#36).

- ``xkcd``: Randall Munroe's xkcd, CC BY-NC 2.5 (https://xkcd.com/license.html): free
  to copy and share non-commercially with credit, as Unseenet is. The comic, its title
  text and a link, from the JSON API.
- ``peppercarrot``: David Revoy's Pepper&Carrot, CC BY 4.0 (https://www.peppercarrot.com),
  with the credits the site asks for on republication (art, scenario and the rest from
  the episode's info.json). An episode has more pages than a post may carry (four
  files, UN-RFC 0027), so it is a thread: the first post and replies, in page order.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from . import Item, Picture, get_json

XKCD = "https://xkcd.com"
PC = "https://www.peppercarrot.com"
PC_SOURCES = f"{PC}/0_sources"
FILES_PER_POST = 4                       # UN-RFC 0027: at most four files on a post


def _md(text: str) -> str:
    return " ".join(str(text or "").split()).replace("*", "\\*").replace("_", "\\_")


class Xkcd:
    name = "xkcd"

    def __init__(self, fetch=get_json):
        self._get = fetch

    @staticmethod
    def archive_id(num) -> str:
        return f"xkcd:{num}"

    def item(self, info: dict) -> Item | None:
        img, num = info.get("img", ""), info.get("num")
        if not num or not img.startswith("https://imgs.xkcd.com/comics/") or img.endswith("/"):
            return None                               # interactive comics have no picture
        page = f"{XKCD}/{num}/"
        title = " ".join((info.get("safe_title") or info.get("title") or "").split())
        try:
            when = datetime(int(info["year"]), int(info["month"]), int(info["day"]), tzinfo=timezone.utc)
        except (KeyError, ValueError):
            when = None
        lines = [f"*{_md(info.get('alt'))}*" if info.get("alt") else "", "",
                 f"[xkcd {num}: {_md(title)}]({page})", "", "---",
                 "xkcd by Randall Munroe (https://xkcd.com), under CC BY-NC 2.5 "
                 "(https://creativecommons.org/licenses/by-nc/2.5/). The text in italics is the "
                 "comic's title text. Randall Munroe does not endorse this post or Unseenet."]
        pic = Picture(img, alt=f"xkcd {num}: {title}", page=page, licence="CC BY-NC 2.5",
                      author="Randall Munroe")
        return Item(id=self.archive_id(num), subject=f"xkcd {num}: {title}",
                    body="\n".join(lines).lstrip("\n") + "\n", published=when, pictures=[pic],
                    link=page)

    def fetch(self, today: date) -> list[Item]:
        item = self.item(self._get(f"{XKCD}/info.0.json"))
        return [item] if item else []

    def archive(self, today: date) -> list[int]:
        latest = self._get(f"{XKCD}/info.0.json")["num"]
        return [n for n in range(1, latest + 1) if n != 404]     # 404 is a joke: no comic

    def archive_item(self, num: int) -> Item | None:
        return self.item(self._get(f"{XKCD}/{num}/info.0.json"))


def _person(text: str) -> str:
    """'David Revoy <https://framagit.org/Deevad>' -> 'David Revoy'."""
    return str(text).split("<")[0].strip()


class PepperCarrot:
    """Pepper&Carrot, in English, one episode a thread. ``px`` on the bot keeps the
    pages small enough for the channel (``picture_px``); the pages come from the
    site's low-res folder, 1200 px wide."""

    name = "peppercarrot"

    def __init__(self, lang: str = "en", fetch=get_json):
        self.lang, self._get = lang, fetch

    @staticmethod
    def archive_id(name: str) -> str:
        return f"pc:{name}"

    def _episodes(self) -> list[dict]:
        return self._get(f"{PC_SOURCES}/episodes-v1.json")

    def item_for(self, ep: dict) -> Item | None:
        name, pages = ep.get("name", ""), ep.get("pages", {})
        info = self._get(f"{PC_SOURCES}/{name}/info.json")
        if not info.get("public", 1) or self.lang not in ep.get("translated_languages", [self.lang]):
            return None
        number = int(info.get("id") or name[2:4])
        title = name.split("_", 1)[1].replace("-", " ") if "_" in name else name
        page_url = f"{PC}/{self.lang}/webcomic/{name}.html"
        order = (["title"] + sorted((k for k in pages if k.isdigit()), key=int)
                 + (["credits"] if "credits" in pages else []))
        pics = [Picture(f"{PC_SOURCES}/{name}/low-res/{self.lang}_{pages[k]}", page=page_url,
                        alt=(f"Pepper&Carrot episode {number}, "
                             + ("title page" if k == "title" else "credits page" if k == "credits"
                                else f"page {k}")),
                        licence="CC BY 4.0", author="David Revoy")
                for k in order if k in pages]
        if not pics:
            return None
        credits = info.get("credits", {})
        credit_lines = [f"- {role.replace('-', ' ').capitalize()}: "
                        + ", ".join(_md(_person(p)) for p in people)
                        for role, people in credits.items() if people]
        try:
            when = datetime.fromisoformat(info["published"]).replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            when = None
        subject = f"Pepper&Carrot, episode {number}: {title}"
        chunks = [pics[i:i + FILES_PER_POST] for i in range(0, len(pics), FILES_PER_POST)]
        head = [f"**[Episode {number}: {_md(title)}]({page_url})** - Pepper&Carrot by David Revoy.", ""]
        if len(chunks) > 1:
            head += [f"The episode is in {len(chunks)} parts: this post and the replies under it, "
                     "in page order.", ""]
        head += ["Credits:", *credit_lines, "", "---",
                "Pepper&Carrot (https://www.peppercarrot.com) by David Revoy, under CC BY 4.0 "
                "(https://creativecommons.org/licenses/by/4.0/). David Revoy does not endorse "
                "this post or Unseenet."]
        parts = [Item(id=f"{self.archive_id(name)}:{n}", subject=f"Re: {subject}",
                      body=f"*Episode {number}, part {n} of {len(chunks)}.*\n", pictures=chunk,
                      link=page_url)
                 for n, chunk in enumerate(chunks[1:], 2)]
        return Item(id=self.archive_id(name), subject=subject, body="\n".join(head) + "\n",
                    published=when, pictures=chunks[0], link=page_url, follow_ups=parts)

    def fetch(self, today: date) -> list[Item]:
        eps = self._episodes()
        item = self.item_for(eps[-1]) if eps else None
        return [item] if item else []

    def archive(self, today: date) -> list[str]:
        return [ep["name"] for ep in self._episodes()]

    def archive_item(self, name: str) -> Item | None:
        ep = next((e for e in self._episodes() if e.get("name") == name), None)
        return self.item_for(ep) if ep else None
