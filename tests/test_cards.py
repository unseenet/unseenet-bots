"""Link cards on the bots' posts (#27, UN-RFC 0059): a card for the item's page, its
picture only where the bot posts what its source vouches for - else without one."""

import io
from datetime import datetime, timezone
from pathlib import Path

import pytest

from unseenet.core.poster import Poster, PosterError

from unseenet_bots.runner import Bot, core_makes_cards, load_config, post_item
from unseenet_bots.sources import Item
from unseenet_bots.sources.feeds import NasaImageOfTheDay

from test_pictures import _node_with

DATA = Path(__file__).parent / "data"
LINK = "https://www.nasa.gov/image-detail/moon"

pytestmark = pytest.mark.skipif(not core_makes_cards(), reason="this core's Poster makes no cards")


def _png(w=1200, h=630):
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (w, h), (20, 30, 90)).save(out, "PNG")
    return out.getvalue()


def _pil() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


def _maker(asked, fail=False):
    async def make_card(self, url, language="en"):
        from unseenet.client import media
        from unseenet.client.session import CardDraft
        asked.append(url)
        if fail:
            raise PosterError("the page did not answer")
        return CardDraft(url=url, title="The Moon rising", desc="Over the sea", site="NASA",
                         made=datetime(2026, 10, 30, tzinfo=timezone.utc),
                         picture=media.card_picture(_png()) if _pil() else None)
    return make_card


def _item(**kw):
    return Item("nasa:1", "The Moon", f"The caption. [NASA]({LINK})\n", link=LINK, **kw)


def _raw(node, group):
    return next(node.store.by_number(group, n)[1] for n in node.store.numbers(group)
                if b"Message-Kind: post" in node.store.by_number(group, n)[1])


@pytest.mark.parametrize("pictures,picture", [("yes", True), ("check", False), ("no", False)])
async def test_a_card_and_its_picture_by_the_rule(tmp_path, monkeypatch, pictures, picture):
    pytest.importorskip("PIL")
    asked = []
    monkeypatch.setattr(Poster, "make_card", _maker(asked))
    node, server, manifest, key, addr = await _node_with({"max_size": 1 << 20, "types": ["image/*"]})
    bot = Bot(name="nasa", source="nasa-iotd", group=manifest.group, from_name="NASA (bot)",
              pictures=pictures, nodes=[addr])
    out = []
    async with Poster(key, [addr], tor="none", state=str(tmp_path / "k.state.json")) as p:
        result = await post_item(p, bot, _item(), True, out.append, cards_ok=True)
    assert result.ok, out
    raw = _raw(node, manifest.group)
    assert asked == [LINK] and b"Link-Card: " in raw
    assert (b"Blobs: " in raw) is picture          # the page's picture only when vouched for
    server.close()


async def test_a_card_where_the_group_takes_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(Poster, "make_card", _maker([]))
    node, server, manifest, key, addr = await _node_with(None)
    bot = Bot(name="nasa", source="nasa-iotd", group=manifest.group, from_name="NASA (bot)",
              pictures="yes", nodes=[addr])
    async with Poster(key, [addr], tor="none", state=str(tmp_path / "k.state.json")) as p:
        result = await post_item(p, bot, _item(), False, print, cards_ok=True)
    assert result.ok
    raw = _raw(node, manifest.group)
    assert b"Link-Card: " in raw and b"Blobs: " not in raw
    server.close()


@pytest.mark.parametrize("cards,fail", [(False, False), (True, True)])
async def test_no_card_turned_off_or_not_made(tmp_path, monkeypatch, cards, fail):
    asked = []
    monkeypatch.setattr(Poster, "make_card", _maker(asked, fail=fail))
    node, server, manifest, key, addr = await _node_with(None)
    bot = Bot(name="nasa", source="nasa-iotd", group=manifest.group, from_name="NASA (bot)",
              nodes=[addr], cards=cards)
    out = []
    async with Poster(key, [addr], tor="none", state=str(tmp_path / "k.state.json")) as p:
        result = await post_item(p, bot, _item(), False, out.append, cards_ok=True)
    assert result.ok                                # the post goes either way
    assert b"Link-Card: " not in _raw(node, manifest.group)
    assert asked == ([LINK] if cards else [])
    server.close()


def test_feed_items_know_their_page_and_the_setting(tmp_path):
    item = NasaImageOfTheDay().fetch_items((DATA / "rss.xml").read_bytes())[1]
    assert item.link.startswith("http")
    cfg = tmp_path / "bots.toml"
    cfg.write_text('[bots.a]\nsource = "nasa-iotd"\ngroup = "g"\n'
                   '[bots.b]\nsource = "nasa-iotd"\ngroup = "g"\ncards = "no"\n')
    _, [a, b] = load_config(cfg)
    assert a.cards is True and b.cards is False
