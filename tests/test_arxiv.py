"""New arXiv papers (#39): metadata only, a daily digest or one post per paper."""

import pytest

from unseenet_bots.sources import get_source

FEED = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>cs.CR updates</title><pubDate>Fri, 30 Oct 2026 00:00:00 -0400</pubDate>
<item><title>A [new] paper</title><link>https://arxiv.org/abs/2610.00001</link>
<description>arXiv:2610.00001v1 Announce Type: new  Abstract: We show *things*.</description>
<arxiv:announce_type>new</arxiv:announce_type>
<dc:creator>Ana One (Uni A), Bo Two, Cy Three, Di Four, Ed Five</dc:creator></item>
<item><title>Replaced</title><link>https://arxiv.org/abs/2601.00002</link>
<description>Abstract: Old.</description><arxiv:announce_type>replace</arxiv:announce_type>
<dc:creator>Old Author</dc:creator></item>
</channel></rss>"""


def test_daily_digest_of_new_papers():
    (item,) = get_source("arxiv", category="cs.CR", fetch=lambda *a: FEED).fetch(None)
    assert item.id == "arxiv:cs.CR:2026-10-30"
    assert item.subject == "cs.CR: 1 new papers, October 30"
    assert ("- [A \\[new\\] paper](https://arxiv.org/abs/2610.00001) - "
            "Ana One, Bo Two, Cy Three, Di Four et al.") in item.body
    assert "Replaced" not in item.body and "We show" not in item.body
    assert "CC0" in item.body and "open access interoperability" in item.body


def test_one_post_per_paper_with_its_abstract():
    (item,) = get_source("arxiv", category="cs.CR", per_paper=True, fetch=lambda *a: FEED).fetch(None)
    assert (item.id, item.subject) == ("arxiv:2610.00001", "A [new] paper")
    assert "We show \\*things\\*." in item.body and "(Uni A)" not in item.body
    assert "[The paper on arXiv](https://arxiv.org/abs/2610.00001)" in item.body


def test_nothing_new_nothing_posted_and_a_bad_category():
    empty = FEED.replace(b">new<", b">cross<")
    assert get_source("arxiv", fetch=lambda *a: empty).fetch(None) == []
    with pytest.raises(ValueError):
        get_source("arxiv", category="cs.CR/../x")
