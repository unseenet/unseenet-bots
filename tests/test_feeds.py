"""The feed sources, from small made-up feeds in tests/data."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from unseenet_bots.runner import Bot, State, _limit, new_items
from unseenet_bots.sources import article_markdown, clip
from unseenet_bots.sources.feeds import (EFF, GlobalVoices, NasaImageOfTheDay, TheConversation,
                                         UNNews, parse_feed)

DATA = Path(__file__).parent / "data"
RSS = (DATA / "rss.xml").read_bytes()
ATOM = (DATA / "atom.xml").read_bytes()
NOW = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)


def test_parse_rss_and_atom():
    rss = parse_feed(RSS)
    assert [e["title"] for e in rss] == ["Old story", "Newer story & more"]      # oldest first
    assert rss[1]["author"] == "Ana Writer" and rss[1]["image"] == "https://example.org/pic.jpg"
    assert rss[1]["published"] == datetime(2026, 10, 18, 8, 0, tzinfo=timezone.utc)
    [atom] = parse_feed(ATOM)
    assert atom["link"] == "https://example.org/article-1"
    assert atom["author"].startswith("Dr. Re Searcher")


def test_markdown_leaves_out_images_scripts_and_fixes_emphasis():
    md = article_markdown(parse_feed(RSS)[1]["html"], "https://example.org/new")
    assert md.startswith("First **bold** paragraph with [a link](https://example.org/x).")
    assert "Photo" not in md and "alert" not in md and "img" not in md
    assert "- one\n- two" in md


def test_global_voices_credits_at_the_top():
    item = GlobalVoices(fetch=lambda *a: RSS).fetch_items(RSS)[1]
    assert item.body.startswith("*This story by Ana Writer originally appeared on "
                                "[Global Voices](https://example.org/new) on October 18, 2026.*")
    assert "CC BY 3.0" in item.body and "images left out" in item.body
    assert item.subject == "Newer story & more" and item.id == "gv:https://example.org/?p=2"


def test_the_conversation_takes_only_the_opening():
    [item] = TheConversation(paragraphs=2).fetch_items(ATOM)
    assert "One." in item.body and "Two." in item.body and "Three." not in item.body
    assert "Read more:" not in item.body and "### Head" not in item.body
    assert "Read the full article on The Conversation](https://example.org/article-1)" in item.body
    assert "*By Dr. Re Searcher, University of Somewhere*" in item.body


def test_eff_drops_its_embeds_and_reads_escaped_html():
    old, new = EFF().fetch_items(RSS)
    assert "%3C" not in new.body and "This embed" not in new.body
    assert "Escaped *html* body." in old.body and "CC BY 4.0" in old.body


def test_nasa_links_the_picture():
    item = NasaImageOfTheDay().fetch_items(RSS)[1]
    assert "[See the picture](https://example.org/pic.jpg)" in item.body
    assert "does not endorse" in item.body


def test_un_news_summary_link_and_no_pictures():
    from unseenet_bots.sources import get_source
    items = UNNews().fetch_items((DATA / "un.xml").read_bytes())
    assert len(items) == 1                       # the one without a summary is skipped
    item = items[0]
    assert item.subject == "Made-up story about & things"
    assert item.body.startswith("A made-up summary with a space.\n")
    link = "https://news.un.org/en/story/2026/10/1000002"     # the guid, not the redirect
    assert item.link == link and item.id == "un:" + link
    assert f"[Read the whole story on UN News]({link})" in item.body
    assert "not affiliated with or endorsed by the United Nations" in item.body
    assert item.pictures == [] and "agency-photo" not in item.body
    assert isinstance(get_source("un-news"), UNNews)


NGO = (DATA / "ngo.xml").read_bytes()


def test_amnesty_and_hrw_whole_text_without_pictures_or_footer():
    from unseenet_bots.sources import get_source
    for name, org in (("amnesty", "Amnesty International"), ("hrw", "Human Rights Watch")):
        item = get_source(name).fetch_items(NGO)[0]
        assert "First paragraph." in item.body and "Second paragraph." in item.body
        assert "Click to expand" not in item.body and "appeared first" not in item.body
        assert "a.jpg" not in item.body and item.pictures == []
        assert "CC BY-NC-ND 4.0" in item.body and f"{org} does not endorse" in item.body
        assert "Published by Example Org on" in item.body
    # a byline that only repeats the organisation is left out
    assert "*Published on" in get_source("hrw").fetch_items(NGO.replace(
        b"Example Org", b"Human Rights Watch"))[0].body


def test_mongabay_takes_the_opening_with_byline_and_link():
    from unseenet_bots.sources import get_source
    item = get_source("mongabay").fetch_items(NGO)[1]
    assert item.body.startswith("*By Ana Writer*\n")
    assert "stops mid…\n" in item.body and "originally published" not in item.body
    assert "[Read the full article on Mongabay](https://example.org/news/2)" in item.body
    assert item.pictures == []


def test_a_bare_ampersand_does_not_break_a_feed():
    bad = b'<rss><channel><item><title>T</title><link>https://e.org/a?x=1&amp;y=2</link>' \
          b'<description><img src="p.jpg?w=1&dpr=2"/></description></item></channel></rss>'
    (e,) = parse_feed(bad)
    assert (e["title"], e["link"]) == ("T", "https://e.org/a?x=1&y=2")


def test_clip_keeps_whole_paragraphs():
    text = "\n\n".join(f"Paragraph {n} " + "x" * 50 for n in range(10))
    out = clip(text, 200, "MORE")
    assert out.endswith("\n\nMORE") and "Paragraph 2" in out and "Paragraph 5" not in out
    assert clip("short", 200, "MORE") == "short"


def test_old_items_are_skipped_and_daily_limit(tmp_path):
    items = GlobalVoices().fetch_items(RSS)
    assert [i.subject for i in new_items(items, {}, set(), 5, NOW, 48)] == ["Newer story & more"]
    assert len(new_items(items, {}, set(), 5, NOW, None)) == 2
    bot = Bot(name="tc", source="theconversation", group="g", from_name="x",
              max_per_run=3, max_per_day=4)
    state = State(tmp_path / "s.json")
    assert _limit(bot, state, NOW) == 3
    for n in range(3):
        state.mark("tc", f"i{n}", f"<m{n}>", NOW - timedelta(hours=n))
    assert _limit(bot, state, NOW) == 1
    assert _limit(bot, state, NOW + timedelta(days=1, hours=3)) == 3


def test_gzip_sent_unasked_is_unpacked(monkeypatch):
    import gzip
    import io
    import urllib.request

    from unseenet_bots.sources import get_bytes

    class Resp(io.BytesIO):
        headers = {"Content-Encoding": "gzip"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: Resp(gzip.compress(b"<rss/>")))
    assert get_bytes("https://e.org/f") == b"<rss/>"


def test_one_bot_failing_does_not_stop_the_others(tmp_path, monkeypatch, capsys):
    import pytest

    from unseenet_bots import runner
    conf = tmp_path / "bots.toml"
    conf.write_text(f'[defaults]\nstate_file = "{tmp_path}/s.json"\n'
                    '[bots.a]\nsource = "eff"\ngroup = "g@x"\n[bots.b]\nsource = "eff"\ngroup = "g@x"\n')
    ran = []

    async def run_bot(bot, state, dry_run=False):
        ran.append(bot.name)
        if bot.name == "a":
            import xml.etree.ElementTree as ET
            raise ET.ParseError("not well-formed")
    monkeypatch.setattr(runner, "run_bot", run_bot)
    with pytest.raises(SystemExit):
        runner.main(["-c", str(conf), "run"])
    assert ran == ["a", "b"] and "a: failed: ParseError" in capsys.readouterr().err
