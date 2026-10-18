# unseenet-bots

Bots that keep [Unseenet](https://unseenet.org) channels filled with
current content, and an example of how to build a bot on the Unseenet
core library.

**Status:** early. Two sources work (Wikipedia *In the news* and *On
this day*); more are listed in issue #1.

## Idea

- One bot is one key, a *poster* in a channel (never the owner), with
  `bot: true` in its profile (UN-RFC 0030 section 6).
- One source per bot: fetch, turn into a post with a credit line
  (author, source, licence, link), post on a schedule.
- Built only on the public core API of
  [unseenet/unseenet](https://github.com/unseenet/unseenet), so it
  doubles as an example for anybody writing their own bot.
- Readers can comment if the channel has `comments: open`
  (UN-RFC 0030).

## Running it

```sh
pip install git+https://github.com/unseenet/unseenet-bots.git
cp bots.example.toml bots.toml            # fill in groups and key files
unseenet-bots -c bots.toml new-key ~/.config/unseenet-bots/news.key
#   -> make the printed key a poster in the channel (Make poster)
unseenet-bots -c bots.toml run --dry-run  # see what would be posted
unseenet-bots -c bots.toml run            # post what is new
```

Each `run` fetches every source once and posts what has not been posted
before (remembered in a state file, and checked against the channel's
newest threads). Schedule it, e.g. every hour, with the systemd units in
`contrib/`. It starts its own Tor, or uses a running one if
`UNSEENET_TOR_SOCKS` names its SOCKS port. Sources are fetched directly
from the web, not over Tor.

| Source | Posts | Licence |
|---|---|---|
| `wikipedia-news` | one post per story in Wikipedia's *In the news* | CC BY-SA 4.0 |
| `wikipedia-onthisday` | one post a day with the day's anniversaries | CC BY-SA 4.0 |

Open the channel for comments (*Edit group* → *Readers may comment on
posts*, UN-RFC 0030) so readers can talk about each post.

## Writing a source

A source is a class with a `name` and `fetch(today) -> list[Item]` in
`src/unseenet_bots/sources/`. An `Item` has a stable `id` (so nothing is
posted twice), a `subject` and a markdown `body` that ends with the
credit line its licence asks for. See `wikipedia.py`, and *Writing a bot*
in the Unseenet docs for the core API underneath.

## Content and licences

Only sources whose licences allow reposting are used, and each post
credits its source as the licence asks. News agencies whose terms
forbid redistribution are not used. The first sources are listed in
issue #1.

Whoever runs a bot is responsible for its content and for following
the source's licence.

## Licence

The code is licensed under the Apache License 2.0. Content posted by
the bots keeps the licence of its source.
