<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/unseenet/unseenet/main/assets/logo-dark.svg">
    <img src="https://raw.githubusercontent.com/unseenet/unseenet/main/assets/logo-light.svg" alt="Unseenet" width="360">
  </picture>
</p>

<h1 align="center">unseenet-bots</h1>

<p align="center"><b>Bots that keep Unseenet channels filled with current content.</b><br>
News, history, science and space - posted as feeds you can comment on, with credit and licence.</p>

<p align="center">
  <a href="https://pypi.org/project/unseenet-bots/"><img src="https://img.shields.io/pypi/v/unseenet-bots?label=PyPI" alt="PyPI"></a>
  <a href="https://github.com/unseenet/unseenet-bots/actions/workflows/tests.yml"><img src="https://github.com/unseenet/unseenet-bots/actions/workflows/tests.yml/badge.svg" alt="tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="Apache-2.0"></a>
</p>

> **Pre-alpha.** Nothing is stable yet, and Unseenet has not had a security
> review. Do not rely on it to protect anyone yet.

## What it is

Bots that keep [Unseenet](https://unseenet.org) channels filled with
current content, and an example of how to build a bot on the Unseenet
core library.

**Status:** early. Six sources work, listed below.

- One bot is one key, a *poster* in a channel (never the owner), with
  `bot: true` in its profile (UN-RFC 0030 section 6).
- One source per bot: fetch, turn into a post with a credit line
  (author, source, licence, link), post on a schedule.
- Built only on the public core API of
  [unseenet/unseenet](https://github.com/unseenet/unseenet), so it
  doubles as an example for anybody writing their own bot.
- Readers can comment if the channel has `comments: open`
  (UN-RFC 0030).

### Content and licences

Only sources whose licences allow reposting are used, and each post
credits its source as the licence asks. News agencies whose terms
forbid redistribution are not used. The first sources are listed in
issue #1.

Whoever runs a bot is responsible for its content and for following
the source's licence.

## Run it

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
| `un-news` | UN News: each story's summary and a link to the whole story; never pictures, so run it with `pictures = "no"`. The UN asks to be told that you carry it | credit, and tell the UN |
| `amnesty` | whole news items from Amnesty International, without pictures | CC BY-NC-ND 4.0 |
| `hrw` | whole news items from Human Rights Watch, without pictures or captions | CC BY-NC-ND 4.0 |
| `mongabay` | the feed's opening of each Mongabay article, and a link to the rest; use `max_per_day` | Mongabay's republishing guidelines |
| `headlines` | any RSS or Atom feed as headlines only (`options = { url, site }`): Lobsters, Ars Technica, The Register, LWN, ProPublica, Rest of World; needs `mode = "headlines"` | headline and link only |
| `hackernews` | the stories on Hacker News' front page with at least `min_score` points (default 300), with the HN discussion; needs `mode = "headlines"` | headline and link only |
| `cisa-advisories` | CISA's cybersecurity advisories, whole; those written with foreign agencies only as their summary and a link | public domain (US government) |
| `cisa-kev` | one post a day with the vulnerabilities added to CISA's Known Exploited Vulnerabilities catalog the day before | public domain (US government) |
| `owid` | Our World in Data's Data Insights, with the chart when it is OWID's own (`pictures = "check"`) | CC BY 4.0 |
| `xkcd` | xkcd's newest comic with its picture and title text; also from the archive (`mode = "archive"`); needs `pictures = "yes"` | CC BY-NC 2.5 |
| `peppercarrot` | a Pepper&Carrot episode as a thread (the first post and replies, four pages each), with the episode's credits; best with `mode = "archive"`, `pictures = "yes"` and `picture_px = 1000` | CC BY 4.0 |
| `arxiv` | new arXiv papers in a category (`options = { category = "cs.CR" }`): one daily digest with titles and authors, or with `per_paper = true` each paper with its abstract; metadata only, never the paper | CC0 (metadata) |

Images are left out of every post, because they often have licences of
their own; each post links to the original. Only items from the last two
days are posted (`max_age_hours`), so a new bot does not fill its channel
with old news.

Open the channel for comments (*Edit group* → *Readers may comment on
posts*, UN-RFC 0030) so readers can talk about each post.

### Profiles

Every bot says it is a bot: each run first publishes its public profile with
the **bot mark** (UN-RFC 0022), so clients mark its posts - but only when the
text or the picture is new or has changed (a short hash is kept in the state
file). In `bots.toml`, per bot:

```toml
[bots.nasa.profile]
about = "NASA's Image of the Day, with its caption."   # Markdown
not_affiliated_with = "NASA"
lang = "en"
links = { web = "https://www.nasa.gov/image-of-the-day/" }
picture = "~/.config/unseenet-bots/nasa.webp"   # optional: 128 px WebP, no metadata
picture_alt = "..."
```

Every About ends with the same line: an automatic channel run by the
Unseenet project, comment below each post, not affiliated with the source,
and a link to the channel. `unseenet-bots profile --dry-run` shows the
profiles; `unseenet-bots profile` publishes them now, without posting. Use
no source's logo as the picture (trademarks).

### Pictures

Posts cannot be removed from the network afterwards, so a bot posts a picture
only where the licence clearly allows it. Per bot, `pictures`:

| | |
|---|---|
| `"no"` (default) | no pictures; links as before |
| `"check"` | only a picture whose licence is known and free: public domain, CC0, CC BY or CC BY-SA (never NC or ND). For Wikipedia it is read from the file's page on Wikimedia Commons; a local, non-free file is never posted |
| `"yes"` | the pictures the source vouches for, e.g. NASA's own, which are not copyrighted |

Every picture gets a credit line under the post: what it shows, who made it,
its licence and its page. Big pictures are scaled down to 1600 px; the core
takes their metadata out. If the core cannot post files (before unseenet
0.5), or the group or node takes none, the post links to the picture with the
same credit. `run --dry-run` shows which pictures would go and why. Today the
NASA, Our World in Data and Wikipedia "In the news" sources offer pictures; EFF and Global Voices
only link to theirs (each picture has its own licence there), and The
Conversation's are agency pictures, so never.

### Headlines only

For sources whose text and pictures may not be republished, `mode = "headlines"`
posts only the headline as a link, where it is from, and the discussion when there
is one (Hacker News, Lobsters, a site's comments): the runner writes the post itself,
so nothing of the source's text or pictures gets in, and links lose their `utm_*`
tracking. The link card then keeps only the page's title, site and icon - not its
description or picture. The `headlines` and `hackernews` sources run only in this mode.

```toml
[bots.lobsters]
source = "headlines"
mode = "headlines"
group = "alt.news.lobsters@<owner fingerprint>"
key_file = "~/.config/unseenet-bots/lobsters.key"
max_per_run = 5
options = { url = "https://lobste.rs/rss", site = "Lobsters" }
```

### From the archive

`mode = "archive"` posts one item from the source's archive every `every_hours`
(default 24), at random (`order = "random"`, the default) or the oldest first
(`order = "oldest"`), and starts over when it has posted them all. Each such post
says it is from the archive and when it was first published. Sources with an archive:
`xkcd` and `peppercarrot`. `picture_px` scales pictures down (default 1600 px), to
keep a channel's files within what nodes keep for it (8 MiB, UN-RFC 0017).

### Link previews

A post from a feed (NASA, EFF, Global Voices, The Conversation, UN News, Amnesty, HRW, Mongabay) gets a link
card for the article it comes from (UN-RFC 0059): the site's icon, domain,
title and description, made once over Tor when it is posted, so readers fetch
nothing. The page's own picture goes on the card only where the bot posts
what its source vouches for (`pictures = "yes"`) and the item brings no
picture of its own; elsewhere the card goes without it, since the picture has
a licence of its own. `cards = "no"` on a bot leaves the cards out. A page
that does not answer over Tor gives no card; the post goes all the same.

## Develop

### Writing a source

A source is a class with a `name` and `fetch(today) -> list[Item]` in
`src/unseenet_bots/sources/`. An `Item` has a stable `id` (so nothing is
posted twice), a `subject` and a markdown `body` that ends with the
credit line its licence asks for. See `wikipedia.py`, and *Writing a bot*
in the Unseenet docs for the core API underneath.

## Versions and releases

Versions follow [semantic versioning](https://semver.org/) on the same
principles as [unseenet](https://github.com/unseenet/unseenet/blob/main/docs/development.md#versioning):
tags `vX.Y.Z` on `main`, the changes in [CHANGELOG.md](CHANGELOG.md), and
releases on [PyPI](https://pypi.org/p/unseenet-bots). Each release names the
minor version of unseenet it works with (`unseenet>=0.5,<0.6`).

To release: move the entries under `## [Unreleased]` in `CHANGELOG.md` to a
new `## [X.Y.Z] - YYYY-MM-DD` section, set `__version__` in
`src/unseenet_bots/__init__.py`, commit, then
`git tag -a vX.Y.Z -m "unseenet-bots X.Y.Z" && git push origin vX.Y.Z`.

## Part of Unseenet

| Repository | What it is |
|---|---|
| [unseenet](https://github.com/unseenet/unseenet) | The protocol (UN-RFCs), the core library, the node and the command-line client |
| [unseenet-tui](https://github.com/unseenet/unseenet-tui) | The terminal client |
| [unseenet-gui](https://github.com/unseenet/unseenet-gui) | The graphical client - in a window, booted, or in a browser |
| [unseenet-portable](https://github.com/unseenet/unseenet-portable) | Builds the portable clients, Terminal and Graphical, with Tor inside |
| [unseenet-bootable](https://github.com/unseenet/unseenet-bootable) | Builds the bootable images, Terminal and Graphical |
| [unseenet-docs](https://github.com/unseenet/unseenet-docs) | The site [unseenet.org](https://unseenet.org) |
| [unseenet-entrance](https://github.com/unseenet/unseenet-entrance) | Web entrances: the graphical client in an ordinary browser |
| [unseenet-gateway](https://github.com/unseenet/unseenet-gateway) | Gateways to other networks: Usenet, Nostr, Matrix |
| [unseenet-bots](https://github.com/unseenet/unseenet-bots) | Bots that keep channels filled with current content |
| [unseenet-helpbot](https://github.com/unseenet/unseenet-helpbot) | The bot that answers questions in `unseenet.help` |
| [unseenet-watchman](https://github.com/unseenet/unseenet-watchman) | Automatic spam reports and content labels that readers may choose to follow |
| [unseenet-stats](https://github.com/unseenet/unseenet-stats) | Statistics for the network |
| [unseenet-mcp](https://github.com/unseenet/unseenet-mcp) | An MCP server, so a language model can read and post as you (planning) |
| [unseenet-demo](https://github.com/unseenet/unseenet-demo) | Demo people, feeds and sites, made with the command-line client |

## License

[Apache License 2.0](LICENSE). The Unseenet logo: CC BY 4.0.
