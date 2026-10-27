"""Pictures on the bots' posts, only where the licence clearly allows it (#7)."""

import io
import json
from pathlib import Path

import pytest

from unseenet.core import crypto
from unseenet.core.groups import make_manifest
from unseenet.core.poster import Poster
from unseenet.core.store import Store
from unseenet.node.server import Node, NodeConfig

from unseenet_bots.runner import (Bot, allowed_pictures, core_posts_files, credit_line,
                                  post_item, scale_down)
from unseenet_bots.sources import Item, Picture, commons_licence, free_licence
from unseenet_bots.sources.feeds import NasaImageOfTheDay
from unseenet_bots.sources.wikipedia import InTheNews

DATA = Path(__file__).parent / "data"
COMMONS = ("https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/"
           "Example_rocket.jpg/320px-Example_rocket.jpg")


def _commons(licence, artist="<a href='x'>Jane Doe</a>"):
    def fetch(url):
        assert "commons.wikimedia.org/w/api.php" in url and "Example_rocket.jpg" in url
        return {"query": {"pages": {"1": {"imageinfo": [{"extmetadata": {
            "LicenseShortName": {"value": licence}, "Artist": {"value": artist}}}]}}}}
    return fetch


@pytest.mark.parametrize("name,ok", [
    ("Public domain", True), ("PD-USGov-NASA", True), ("CC0", True), ("CC BY 4.0", True),
    ("CC BY-SA 3.0", True), ("CC-BY-SA-4.0", True), ("CC BY-NC 4.0", False),
    ("CC BY-ND 2.0", False), ("CC BY-NC-SA 4.0", False), ("Fair use", False), ("", False),
    (None, False)])
def test_free_licences(name, ok):
    assert free_licence(name) is ok


def test_commons_licence_and_only_commons():
    assert commons_licence(COMMONS, _commons("CC BY-SA 4.0")) == ("CC BY-SA 4.0", "Jane Doe")
    local = "https://upload.wikimedia.org/wikipedia/en/a/ab/Poster.jpg"   # non-free, local
    assert commons_licence(local, lambda url: pytest.fail("never asked")) is None


def test_nasa_offers_its_picture_as_public_domain():
    item = NasaImageOfTheDay().fetch_items((DATA / "rss.xml").read_bytes())[1]
    [pic] = item.pictures
    assert pic.url == "https://example.org/pic.jpg" and pic.licence == "Public domain"


def test_the_pictured_page_of_a_wikipedia_story():
    feed = json.loads((DATA / "featured.json").read_text())
    feed["news"][0]["links"][1]["thumbnail"] = {"source": COMMONS}
    [first, _] = InTheNews(fetch=lambda url: _commons("CC BY 4.0")(url)
                           if "commons" in url else feed).fetch_items(feed)
    [pic] = first.pictures
    assert pic.url == COMMONS.replace("/320px-", "/960px-") and pic.alt == "Example Mission"
    assert pic.page == "https://commons.wikimedia.org/wiki/File:Example_rocket.jpg"
    assert pic.licence is None and pic.lookup() == ("CC BY 4.0", "Jane Doe")
    feed["news"][0]["links"][1]["thumbnail"] = {"source": "https://elsewhere.example/a.jpg"}
    assert InTheNews(fetch=lambda url: feed).fetch_items(feed)[0].pictures == []


def _bot(rule):
    return Bot(name="b", source="nasa-iotd", group="g@aaaaaaaaaaaaaaaa", from_name="b",
               pictures=rule)


def test_the_rule_decides():
    free = Picture("https://x/a.jpg", lookup=lambda: ("CC BY 4.0", "Ann"))
    nc = Picture("https://x/b.jpg", lookup=lambda: ("CC BY-NC 4.0", "Bo"))
    unknown = Picture("https://x/c.jpg", lookup=lambda: None)
    nasa = Picture("https://x/d.jpg", licence="Public domain", author="NASA")
    item = Item("i", "s", "body\n", pictures=[free, nc, unknown, nasa])
    out = []
    assert allowed_pictures(_bot("no"), item, out.append) == []
    assert [p.url for p, _, _ in allowed_pictures(_bot("check"), item, out.append)] == [
        "https://x/a.jpg", "https://x/d.jpg"]
    assert any("CC BY-NC" in line for line in out) and any("unknown" in line for line in out)
    assert [p.url for p, _, _ in allowed_pictures(_bot("yes"), item, out.append)] == [
        "https://x/a.jpg", "https://x/b.jpg", "https://x/d.jpg"]   # yes: what the source vouches


def test_the_credit_line():
    pic = Picture("https://x/a.jpg", alt="A rocket", page="https://commons/File:a.jpg")
    assert credit_line(pic, "CC BY 4.0", "Ann", True) == \
        "*Picture: A rocket by Ann, CC BY 4.0 - [https://commons/File:a.jpg](https://commons/File:a.jpg)*"
    assert credit_line(pic, "CC BY 4.0", "", False).startswith("*[Picture](https://x/a.jpg): A rocket,")


def _jpeg(px):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (px, px // 2), (10, 120, 200)).save(buf, "JPEG")
    return buf.getvalue()


def test_big_pictures_are_scaled_down():
    pytest.importorskip("PIL")
    from PIL import Image
    small = _jpeg(800)
    assert scale_down(small) is small
    big = scale_down(_jpeg(4000))
    assert max(Image.open(io.BytesIO(big)).size) == 1600
    assert scale_down(b"not a picture") == b"not a picture"


async def _node_with(attachments):
    owner, key = crypto.Identity.generate(), crypto.Identity.generate()
    extra = {"attachments": attachments} if attachments else None
    manifest = make_manifest(owner, "alt.space.nasa", "channel", posters=[key.key_text],
                             comments="open", pow_bits=12, extra=extra)
    node = Node(Store(), NodeConfig(min_pow=8, forward_delay=(0, 0), blobs={"max_size": 1048576})
                if attachments else NodeConfig(min_pow=8, forward_delay=(0, 0)))
    node.accept(manifest.to_bytes())
    server = await node.serve("127.0.0.1", 0)
    return node, server, manifest, key, f"127.0.0.1:{server.sockets[0].getsockname()[1]}"


@pytest.mark.parametrize("allow", [True, False])
async def test_posted_with_the_picture_or_a_link(tmp_path, allow):
    if not core_posts_files():
        pytest.skip("this core's Poster posts no files (unseenet 0.5)")
    pytest.importorskip("PIL")
    att = {"max_size": 1 << 20, "types": ["image/*"]} if allow else None
    try:
        node, server, manifest, key, addr = await _node_with(att)
    except TypeError:
        pytest.skip("this core's node has no blob settings")
    bot = Bot(name="nasa", source="nasa-iotd", group=manifest.group, from_name="NASA (bot)",
              pictures="yes", nodes=[addr])
    item = Item("nasa:1", "A rocket", "The caption.\n", pictures=[
        Picture("https://example.org/rocket.jpg", alt="A rocket", page="https://nasa/1",
                licence="Public domain", author="NASA")])
    out = []
    async with Poster(key, [addr], tor="none", state=str(tmp_path / "k.state.json")) as p:
        result = await post_item(p, bot, item, True, out.append,
                                 fetch=lambda url, accept: _jpeg(400))
    assert result.ok, out
    raw = next(node.store.by_number(manifest.group, n)[1] for n in node.store.numbers(manifest.group)
               if b"Message-Kind: post" in node.store.by_number(manifest.group, n)[1])
    assert (b"Blobs: " in raw) is allow
    assert b"Public domain" in raw and b"https://nasa/1" in raw
    server.close()



def test_the_language_header():
    """UN-RFC 0052 5a: a bot's posts say its source's language."""
    from unseenet_bots.runner import language_header
    assert language_header(Bot(name="a", source="x", group="g", from_name="A", options={"lang": "en"})) == \
        [("Content-Language", "en")]
    assert language_header(Bot(name="b", source="x", group="g", from_name="B", profile={"lang": ["da"]})) == \
        [("Content-Language", "da")]
    assert language_header(Bot(name="c", source="x", group="g", from_name="C", profile={"lang": ["en", "da"]})) == []
    assert language_header(Bot(name="d", source="x", group="g", from_name="D")) == []


async def test_a_post_says_its_language(tmp_path):
    try:
        node, server, manifest, key, addr = await _node_with(None)
    except TypeError:
        pytest.skip("this core's node has no blob settings")
    bot = Bot(name="nasa", source="nasa-iotd", group=manifest.group, from_name="NASA (bot)",
              nodes=[addr], options={"lang": "en"})
    async with Poster(key, [addr], tor="none", state=str(tmp_path / "k.state.json")) as p:
        result = await post_item(p, bot, Item("nasa:2", "A moon", "The caption.\n"), False, print)
    assert result.ok
    raw = next(node.store.by_number(manifest.group, n)[1] for n in node.store.numbers(manifest.group)
               if b"Message-Kind: post" in node.store.by_number(manifest.group, n)[1])
    assert b"Content-Language: en" in raw
    server.close()
