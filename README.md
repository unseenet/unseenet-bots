# unseenet-bots

Bots that keep [Unseenet](https://unseenet.org) channels filled with
current content, and an example of how to build a bot on the Unseenet
core library.

**Status:** early. Six sources work, listed below.

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
pip install unseenet-bots
cp bots.example.toml bots.toml            # fill in groups and key files
unseenet-bots -c bots.toml new-key ~/.config/unseenet-bots/news.key
#   -> make the printed key a poster in the channel (Make poster)
unseenet ripen --key-file ~/.config/unseenet-bots/news.key --to 0 \
    --node NODE.onion --publish            # once: 7-11 minutes, see below
unseenet-bots -c bots.toml run --dry-run  # see what would be posted
unseenet-bots -c bots.toml run            # post what is new
```

**A new key ripens first** (UN-RFC 0025): nodes take posts only from keys
that have done a few minutes of work, which is what keeps throwaway keys
from spamming. Do it once at setup with `unseenet ripen` as above; its
chain goes in `<key file>.state.json`, beside the key, where the runner
finds it (it holds nothing secret). A first `run` without it would ripen
then, and take as long. Ripening on to level 3 removes the extra postage
a young key pays: `unseenet ripen --key-file KEY --to 3 --node NODE --publish`
in the background, about 2.5-4 days on one core at low priority.

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
| `globalvoices` | whole stories from Global Voices, credited at the top | CC BY 3.0 |
| `theconversation` | the opening paragraphs of articles from The Conversation, and a link to the rest; use `max_per_day`, as their terms do not allow republishing every article | CC BY-ND 4.0 |
| `eff` | whole posts from EFF's Deeplinks blog | CC BY 4.0 |
| `nasa-iotd` | NASA's Image of the Day: the caption and a link to the picture | not copyrighted |

Images are left out of every post, because they often have licences of
their own; each post links to the original. Only items from the last two
days are posted (`max_age_hours`), so a new bot does not fill its channel
with old news.

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

## Versions and releases

Versions follow [semantic versioning](https://semver.org/) on the same
principles as [unseenet](https://github.com/unseenet/unseenet/blob/main/docs/development.md#versioning):
tags `vX.Y.Z` on `main`, the changes in [CHANGELOG.md](CHANGELOG.md), and
releases on [PyPI](https://pypi.org/p/unseenet-bots). Each release names the
minor version of unseenet it works with (`unseenet>=0.4.1,<0.5`).

To release: move the entries under `## [Unreleased]` in `CHANGELOG.md` to a
new `## [X.Y.Z] - YYYY-MM-DD` section, set `__version__` in
`src/unseenet_bots/__init__.py`, commit, then
`git tag -a vX.Y.Z -m "unseenet-bots X.Y.Z" && git push origin vX.Y.Z`.

## Licence

The code is licensed under the Apache License 2.0. Content posted by
the bots keeps the licence of its source.
