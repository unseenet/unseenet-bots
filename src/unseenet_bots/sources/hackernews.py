"""Hacker News' front page, as headlines only (#35), from the official API
(https://github.com/HackerNews/API): the stories on the front page with at least
``min_score`` points, each with its link and the link to its HN discussion. The titles
are the submitters'; the linked articles are their publishers', so no text or pictures."""

from __future__ import annotations

from datetime import date, datetime, timezone

from . import Item, get_json

API = "https://hacker-news.firebaseio.com/v0"
DISCUSSION = "https://news.ycombinator.com/item?id={}"


class HackerNews:
    name = "hackernews"
    headlines_only = True

    def __init__(self, min_score: int = 300, count: int = 30, fetch=get_json):
        self.min_score, self.count, self._get = int(min_score), int(count), fetch

    def item(self, story: dict) -> Item | None:
        if (not story or story.get("type") != "story" or story.get("dead") or story.get("deleted")
                or not story.get("title") or story.get("score", 0) < self.min_score):
            return None
        discussion = DISCUSSION.format(story["id"])
        when = (datetime.fromtimestamp(story["time"], timezone.utc) if story.get("time") else None)
        return Item(id=f"hn:{story['id']}", subject=" ".join(story["title"].split()), body="",
                    published=when, link=story.get("url") or discussion,
                    site="Hacker News", discussion=discussion)

    def fetch(self, today: date) -> list[Item]:
        ids = self._get(f"{API}/topstories.json")[: self.count]
        items = [self.item(self._get(f"{API}/item/{i}.json")) for i in ids]
        return [i for i in items if i is not None]
