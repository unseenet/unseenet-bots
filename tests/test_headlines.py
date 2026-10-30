"""Headlines only (#35): the title, the link, the site and the discussion - no text or
picture from the source, also not on the link card."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from unseenet_bots.runner import Bot, headline_item, item_card, load_config
from unseenet_bots.sources import Item, Picture, get_source
from unseenet_bots.sources.hackernews import HackerNews

DATA = Path(__file__).parent / "data"


def test_headline_item_has_no_text_or_pictures():
    item = Item("x:1", "A [big] story", "The publisher's whole text.", link="https://www.example.org/a",
                pictures=[Picture("https://example.org/p.jpg")], discussion="https://lobste.rs/s/1")
    h = headline_item(item)
    assert h.body == ("**[A \\[big\\] story](https://www.example.org/a)**\n\n"
                      "*example.org* · [Discussion on lobste.rs](https://lobste.rs/s/1)\n")
    assert h.pictures == [] and "publisher" not in h.body
    assert headline_item(Item("x:2", "No link", "text")) is None
    named = headline_item(Item("x:3", "T", "", link="https://arstechnica.com/x", site="Ars Technica"))
    assert "*Ars Technica*\n" in named.body
    own = headline_item(Item("x:4", "T", "", link="https://arstechnica.com/x", site="Ars Technica",
                             discussion="https://arstechnica.com/x#comments"))
    assert own.body.endswith("*Ars Technica* · [Comments](https://arstechnica.com/x#comments)\n")
    lob = headline_item(Item("x:5", "T", "", link="https://tangled.org/f", site="Lobsters",
                             discussion="https://lobste.rs/s/1"))
    assert "*tangled.org* · [Discussion on Lobsters](https://lobste.rs/s/1)" in lob.body


def test_headlines_source_takes_the_comments_link():
    items = get_source("headlines", url="https://example.org/rss", site="Example",
                       fetch=lambda *a: (DATA / "lobsters.xml").read_bytes()).fetch(None)
    assert [i.subject for i in items] == ["A federated forge"]
    i = items[0]
    assert (i.link, i.site, i.discussion) == ("https://tangled.example/forge", "Example",
                                              "https://lobste.rs/s/abc/forge")
    assert i.body == ""                           # the runner writes it


def test_tracking_parameters_go():
    from unseenet_bots.sources.feeds import _untracked
    assert _untracked("https://r.org/a/?utm_source=rss&id=3&utm_campaign=f") == "https://r.org/a/?id=3"
    assert _untracked("https://r.org/a/?utm_source=rss") == "https://r.org/a/"


def test_headlines_source_needs_its_mode(tmp_path):
    def conf(mode):
        p = tmp_path / "bots.toml"
        p.write_text(f'[bots.l]\nsource = "headlines"\ngroup = "g@x"\n{mode}'
                     'options = { url = "https://example.org/rss" }\n')
        return p
    with pytest.raises(SystemExit, match="headlines only"):
        load_config(conf(""))
    _, (bot,) = load_config(conf('mode = "headlines"\n'))
    assert bot.mode == "headlines"
    with pytest.raises(SystemExit, match="mode is"):
        load_config(conf('mode = "loud"\n'))


def test_hackernews_front_page_above_a_score():
    stories = {
        1: {"id": 1, "type": "story", "title": "Big  news", "url": "https://ex.org/1", "score": 500,
            "time": 1793000000},
        2: {"id": 2, "type": "story", "title": "Small news", "url": "https://ex.org/2", "score": 20},
        3: {"id": 3, "type": "story", "title": "Ask HN: why?", "score": 400},
        4: {"id": 4, "type": "job", "title": "Hiring", "score": 900},
        5: None,
    }

    def fetch(url):
        if url.endswith("topstories.json"):
            return [1, 2, 3, 4, 5]
        return stories[int(url.rsplit("/", 1)[1].split(".")[0])]
    items = HackerNews(min_score=300, fetch=fetch).fetch(None)
    assert [i.id for i in items] == ["hn:1", "hn:3"]
    assert items[0].discussion == "https://news.ycombinator.com/item?id=1"
    assert items[0].published == datetime.fromtimestamp(1793000000, timezone.utc)
    assert items[1].link == items[1].discussion and items[1].site == "Hacker News"
    assert headline_item(items[1]).body.endswith("*Hacker News*\n")      # Ask HN: no second link
    assert "*ex.org* · [Discussion on Hacker News]" in headline_item(items[0]).body


def test_card_keeps_only_title_site_and_icon():
    class Draft:
        def __init__(self):
            self.title, self.desc, self.site, self.picture, self.note = "T", "Their text", "S", object(), ""

    class P:
        async def make_card(self, url, language="en"):
            return Draft()
    bot = Bot(name="b", source="headlines", group="g", from_name="b", mode="headlines", pictures="yes")
    item = Item("x", "T", "", link="https://example.org/a")
    card = asyncio.run(item_card(P(), bot, item, out=lambda m: None))
    assert (card.title, card.desc, card.picture, card.site) == ("T", "", None, "S")
    full = Bot(name="b", source="nasa-iotd", group="g", from_name="b", pictures="yes")
    card = asyncio.run(item_card(P(), full, item, out=lambda m: None))
    assert card.desc == "Their text" and card.picture is not None


def test_card_picture_keeps_the_page_preview_only_when_chosen():
    class Draft:
        def __init__(self):
            self.title, self.desc, self.site, self.picture, self.note = "T", "D", "S", object(), ""

    class P:
        async def make_card(self, url, language="en"):
            return Draft()
    item = Item("x", "T", "", link="https://example.org/a")
    off = Bot(name="b", source="un-news", group="g", from_name="b", pictures="no")
    on = Bot(name="b", source="un-news", group="g", from_name="b", pictures="no", card_picture=True)
    assert asyncio.run(item_card(P(), off, item, out=lambda m: None)).picture is None
    assert asyncio.run(item_card(P(), on, item, out=lambda m: None)).picture is not None
    head = Bot(name="h", source="headlines", group="g", from_name="h", mode="headlines", card_picture=True)
    assert asyncio.run(item_card(P(), head, item, out=lambda m: None)).picture is None
