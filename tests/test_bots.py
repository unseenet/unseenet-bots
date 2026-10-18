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
                             comments="open", pow_bits=8)
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
    assert await run_bot(bot, State(tmp_path / "state.json"), today=TODAY,
                         poster_factory=poster, out=lines.append) == 0      # nothing twice
    assert set(json.loads((tmp_path / "state.json").read_text())["news"]) == {
        "itn:en:Example_landing", "itn:en:Example_Cup"}
    # and nothing twice even without the state file: the channel's threads are checked
    assert await run_bot(bot, State(tmp_path / "other.json"), today=TODAY,
                         poster_factory=poster, out=lines.append) == 0
    server.close()
