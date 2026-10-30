"""One item from the archive at a time (#36), and comics with their pictures (#40)."""

import asyncio
import random
from datetime import datetime, timedelta, timezone

import pytest

from unseenet_bots.runner import (Bot, State, archive_pick, archive_posted, load_config,
                                  post_item)
from unseenet_bots.sources import Item, get_source
from unseenet_bots.sources.comics import PepperCarrot, Xkcd

NOW = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)


class Archive:
    def __init__(self, keys):
        self.keys = keys

    def archive(self, today):
        return self.keys

    @staticmethod
    def archive_id(k):
        return f"s:{k}"

    def archive_item(self, k):
        return None if k == 9 else Item(f"s:{k}", f"Item {k}", "Body.\n",
                                         published=datetime(2010, 5, k, tzinfo=timezone.utc))


def test_archive_picks_one_not_posted_and_waits(tmp_path):
    state = State(tmp_path / "s.json")
    state.mark("b", "s:1", "<m1>")
    bot = Bot(name="b", source="xkcd", group="g", from_name="b", mode="archive", order="oldest")
    (item,) = archive_pick(Archive([1, 2, 3]), bot, state, NOW, out=lambda m: None)
    assert item.id == "s:2" and item.body == "*From the archive: first published May 2, 2010.*\n\nBody.\n"
    archive_posted(state, bot, NOW)
    lines = []
    assert archive_pick(Archive([1, 2, 3]), bot, state, NOW + timedelta(hours=23), out=lines.append) == []
    assert "waiting" in lines[0]
    assert archive_pick(Archive([1, 2, 3]), bot, state, NOW + timedelta(hours=25), out=lambda m: None)


def test_archive_starts_over_and_skips_what_is_gone(tmp_path):
    state = State(tmp_path / "s.json")
    for k in (1, 2):
        state.mark("b", f"s:{k}", "<m>")
    bot = Bot(name="b", source="xkcd", group="g", from_name="b", mode="archive", order="oldest")
    (item,) = archive_pick(Archive([1, 2]), bot, state, NOW, out=lambda m: None)
    assert item.id == "s:1"                                   # all posted: from the start again
    (item,) = archive_pick(Archive([9, 4]), bot, state, NOW, out=lambda m: None)
    assert item.id == "s:4"                                   # 9 is gone
    rnd = Bot(name="r", source="xkcd", group="g", from_name="r", mode="archive")
    picks = {archive_pick(Archive(list(range(1, 9))), rnd, State(tmp_path / "t.json"), NOW,
                          out=lambda m: None, rng=random.Random(n))[0].id for n in range(10)}
    assert len(picks) > 1                                     # random by default


def test_archive_mode_needs_a_source_with_an_archive(tmp_path):
    p = tmp_path / "bots.toml"
    p.write_text('[bots.e]\nsource = "eff"\ngroup = "g@x"\nmode = "archive"\n')
    with pytest.raises(SystemExit, match="no archive"):
        load_config(p)
    p.write_text('[bots.x]\nsource = "xkcd"\ngroup = "g@x"\nmode = "archive"\nevery_hours = 12\n'
                 'order = "oldest"\npicture_px = 1000\n')
    _, (bot,) = load_config(p)
    assert (bot.mode, bot.every_hours, bot.order, bot.picture_px) == ("archive", 12, "oldest", 1000)


def test_a_reply_carries_its_references():
    calls = []

    class P:
        async def post(self, group, subject, body, **kw):
            calls.append((subject, kw.get("references")))

            class R:
                ok = True
            return R()
    bot = Bot(name="b", source="xkcd", group="g", from_name="b")
    asyncio.run(post_item(P(), bot, Item("x", "Re: T", "Part 2\n"), False, out=lambda m: None,
                          references=["<first@x>"]))
    asyncio.run(post_item(P(), bot, Item("y", "T", "Part 1\n"), False, out=lambda m: None))
    assert calls == [("Re: T", ["<first@x>"]), ("T", None)]


XKCD = {"num": 353, "safe_title": "Python", "title": "Python", "alt": "I wrote 20 short *programs*.",
        "img": "https://imgs.xkcd.com/comics/python.png", "year": "2007", "month": "12", "day": "5"}


def test_xkcd_comic_title_text_and_credit():
    x = Xkcd(fetch=lambda url: XKCD)
    (item,) = x.fetch(None)
    assert (item.id, item.subject) == ("xkcd:353", "xkcd 353: Python")
    assert item.body.startswith("*I wrote 20 short \\*programs\\*.*\n")
    assert "CC BY-NC 2.5" in item.body and "[xkcd 353: Python](https://xkcd.com/353/)" in item.body
    (pic,) = item.pictures
    assert (pic.licence, pic.author) == ("CC BY-NC 2.5", "Randall Munroe")
    assert 404 not in x.archive(None) and x.archive(None)[-1] == 353
    assert Xkcd(fetch=lambda url: dict(XKCD, img="https://imgs.xkcd.com/comics/")).fetch(None) == []


def test_peppercarrot_episode_is_a_thread_with_its_credits():
    eps = [{"name": "ep02_Rainbow-potions", "translated_languages": ["en", "fr"],
            "pages": {"title": "T.jpg", "cover": "C.jpg", "credits": "CR.jpg",
                      **{str(n): f"P{n}.jpg" for n in range(1, 7)}}}]
    info = {"id": 2, "published": "2014-07-01", "public": 1,
            "credits": {"art": ["David Revoy <https://x>"], "beta-readers": ["Ana <a>", "Bo <b>"]}}

    def fetch(url):
        return eps if url.endswith("episodes-v1.json") else info
    (item,) = PepperCarrot(fetch=fetch).fetch(None)
    assert item.subject == "Pepper&Carrot, episode 2: Rainbow potions"
    assert "- Art: David Revoy" in item.body and "- Beta readers: Ana, Bo" in item.body
    assert "CC BY 4.0" in item.body and "2 parts" in item.body
    assert [p.url.rsplit("/", 1)[1] for p in item.pictures] == ["en_T.jpg", "en_P1.jpg", "en_P2.jpg", "en_P3.jpg"]
    (part,) = item.follow_ups
    assert part.subject.startswith("Re: ") and part.id == "pc:ep02_Rainbow-potions:2"
    assert [p.url.rsplit("/", 1)[1] for p in part.pictures] == ["en_P4.jpg", "en_P5.jpg", "en_P6.jpg", "en_CR.jpg"]
    assert all(p.licence == "CC BY 4.0" for p in item.pictures + part.pictures)
    assert get_source("peppercarrot", fetch=fetch).archive(None) == ["ep02_Rainbow-potions"]
