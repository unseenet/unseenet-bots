"""Sources from a saved feed, and the runner against a local Unseenet node."""

import json
from datetime import date
from pathlib import Path

from unseenet.core import crypto
from unseenet.core.groups import make_manifest
from unseenet.core.poster import Poster
from unseenet.core.store import Store
from unseenet.node.server import Node, NodeConfig

from unseenet_bots.runner import Bot, State, run_bot
from unseenet_bots.sources import html_to_markdown
from unseenet_bots.sources.wikipedia import InTheNews, OnThisDay

FEED = json.loads((Path(__file__).parent / "data" / "featured.json").read_text())
TODAY = date(2026, 10, 18)


def test_html_to_markdown():
    md = html_to_markdown('<!--x--><b><a href="./A_B">A &amp; B</a></b> <i>(it)</i>',
                          "https://en.wikipedia.org/wiki/")
    assert md == "**[A & B](https://en.wikipedia.org/wiki/A_B)** *(it)*"


def test_in_the_news():
    items = InTheNews(fetch=lambda url: FEED).fetch(TODAY)
    assert [i.id for i in items] == ["itn:en:Example_landing", "itn:en:Example_Cup"]
    first = items[0]
    assert first.subject == "The Example Mission (pictured) lands on the Moon."
    assert "[lands on the Moon](https://en.wikipedia.org/wiki/Example_landing)" in first.body
    assert "> The Example landing was a lunar landing." in first.body
    assert "CC BY-SA 4.0" in first.body and first.body.endswith("\n")
    assert items[1].subject == "In sport, the Example Cup ends & is won."


def test_on_this_day():
    urls = []
    [item] = OnThisDay(fetch=lambda url: urls.append(url) or FEED).fetch(TODAY)
    assert urls == ["https://en.wikipedia.org/api/rest_v1/feed/featured/2026/10/18"]
    assert item.id == "otd:en:2026-10-18" and item.subject == "On this day: October 18"
    assert item.body.index("1201") < item.body.index("1932")       # oldest first
    assert "([Bridge](https://en.wikipedia.org/wiki/Bridge))" in item.body


async def test_runner_posts_once(tmp_path):

    owner, bot_key = crypto.Identity.generate(), crypto.Identity.generate()
    manifest = make_manifest(owner, "alt.news", "channel", posters=[bot_key.key_text],
                             comments="open", pow_bits=12)   # FLOOR_POW (UN-RFC 0025, 5)
    node = Node(Store(), NodeConfig(min_pow=8, forward_delay=(0, 0)))
    node.accept(manifest.to_bytes())
    server = await node.serve("127.0.0.1", 0)
    addr = f"127.0.0.1:{server.sockets[0].getsockname()[1]}"
    key_file = tmp_path / "bot.key"
    key_file.write_text(bot_key.seed.hex())

    bot = Bot(name="news", source="wikipedia-news", group=manifest.group,
              from_name="News bot", key_file=str(key_file), nodes=[addr],
              options={"fetch": lambda url: FEED})
    state = State(tmp_path / "state.json")

    def poster(*a, **kw):
        return Poster(*a, tor="none", **kw)

    lines = []
    assert await run_bot(bot, state, today=TODAY, poster_factory=poster, out=lines.append) == 2
    assert (tmp_path / "bot.key.state.json").exists()     # the key's chain, beside the key
    assert await run_bot(bot, State(tmp_path / "state.json"), today=TODAY,
                         poster_factory=poster, out=lines.append) == 0      # nothing twice
    assert set(json.loads((tmp_path / "state.json").read_text())["news"]) == {
        "itn:en:Example_landing", "itn:en:Example_Cup"}
    # posted as Markdown (UN-RFC 0031), which the sources write
    bodies = [node.store.by_number(manifest.group, n)[1] for n in node.store.numbers(manifest.group)]
    posts = [b for b in bodies if b"Message-Kind: post" in b]
    assert len(posts) == 2
    assert all(b"Content-Type: text/markdown" in b for b in posts)
    # and nothing twice even without the state file: the channel's threads are checked
    assert await run_bot(bot, State(tmp_path / "other.json"), today=TODAY,
                         poster_factory=poster, out=lines.append) == 0
    server.close()


def _profiled(group="alt.space.nasa@aaaaaaaaaaaaaaaa", **extra):
    return Bot(name="nasa", source="nasa-iotd", group=group, from_name="NASA (bot)",
               profile={"about": "NASA's Image of the Day, with its caption.",
                        "links": {"web": "https://www.nasa.gov/image-of-the-day/"},
                        "lang": "en", "not_affiliated_with": "NASA", **extra})


def test_a_bot_profile_has_the_mark_the_footer_and_the_links():
    from unseenet_bots.runner import bot_profile
    prof = bot_profile(_profiled())
    assert prof["bot"] is True and prof["about_type"].startswith("text/markdown")
    about = prof["about"]
    assert about.startswith("NASA's Image of the Day")
    assert "Not affiliated with NASA." in about and "comment below each post" in about
    assert "[alt.space.nasa](unseenet:join?g=alt.space.nasa@aaaaaaaaaaaaaaaa)" in about
    assert prof["links"] == [{"kind": "web", "value": "https://www.nasa.gov/image-of-the-day/"}]
    assert prof["lang"] == ["en"]
    assert bot_profile(Bot(name="x", source="eff", group="g@a", from_name="x")) is None


def test_too_long_an_about_is_refused():
    import pytest
    from unseenet_bots.runner import bot_profile
    with pytest.raises(ValueError, match="2048"):
        bot_profile(_profiled(about="x" * 2100))


async def test_the_profile_is_published_once_and_again_when_it_changes(tmp_path):
    from unseenet.core import profiles as prof
    from unseenet_bots.runner import profile_bot, publish_profile

    bot_key = crypto.Identity.generate()
    node = Node(Store(), NodeConfig(min_pow=8, forward_delay=(0, 0)))
    server = await node.serve("127.0.0.1", 0)
    addr = f"127.0.0.1:{server.sockets[0].getsockname()[1]}"
    key_file = tmp_path / "bot.key"
    key_file.write_text(bot_key.seed.hex())
    bot = _profiled()
    bot.key_file, bot.nodes = str(key_file), [addr]
    state = State(tmp_path / "state.json")

    def poster(*a, **kw):
        return Poster(*a, tor="none", **kw)

    lines = []
    assert await profile_bot(bot, state, poster_factory=poster, out=lines.append)
    pid = prof.profile_id(bot_key.public_key)
    first = node.store.manifest(pid)
    assert first is not None and "Not affiliated with NASA" in json.dumps(first.raw)
    async with poster(bot_key, [addr], state=str(key_file) + ".state.json") as p:
        assert not await publish_profile(bot, State(tmp_path / "state.json"), p, lines.append)
        bot.profile["about"] = "NASA's Image of the Day."            # changed: again
        assert await publish_profile(bot, state, p, lines.append)
    assert "NASA's Image of the Day.\\n\\n" in json.dumps(node.store.manifest(pid).raw)
    out = []
    await profile_bot(bot, state, dry_run=True, out=out.append)
    assert '"bot": true' in out[0]
    server.close()
