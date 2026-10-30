# Changelog

All notable changes to unseenet-bots are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/) on the same principles as
[unseenet](https://github.com/unseenet/unseenet/blob/main/docs/development.md#versioning).

## [Unreleased]

### Added

- **Headlines only** (#35): `mode = "headlines"` posts the headline as a link, where it is
  from and the discussion (HN, Lobsters, comments) - written by the runner, so no text or
  picture from the source gets in; the link card keeps only title, site and icon. Sources
  `headlines` (any RSS/Atom feed, `options = { url, site }`) and `hackernews` (the front page
  above `min_score`), which run only in this mode. Links lose their `utm_*` parameters.
- Feeds with a bare `&` in an attribute (Rest of World) are read.

## [0.5.0] - 2026-10-30

Needs unseenet 0.6.5 (`unseenet>=0.6.5,<0.7`), as 0.4.0; nodes need no update.

### Added

- **UN News** (#30): source `un-news`, the summary of each UN News story with a link to the
  whole story and a credit line. Never pictures (UN Photo needs written permission for the
  web), so run it with `pictures = "no"`; the UN asks to be told that you carry it.
- **Amnesty International, Human Rights Watch and Mongabay** (#32): sources `amnesty` and `hrw`
  (whole news items, CC BY-NC-ND 4.0, without pictures, captions or WordPress footers) and
  `mongabay` (the feed's opening of each article and a link to the rest).

## [0.4.0] - 2026-10-30

Needs unseenet 0.6.5 (`unseenet>=0.6.5,<0.7`), which makes the link cards; nodes need no update for it.

### Added

- **Link previews** (#27, UN-RFC 0059; needs unseenet 0.6.5):
  a post from a feed gets a link card for the article it comes from, made over Tor. The
  page's picture goes on the card only with `pictures = "yes"` and no picture of the item's
  own; else the card goes without it. `cards = "no"` leaves them out; a page that does not
  answer gives no card, and the post goes anyway. `run --dry-run` shows the card to be made.

## [0.3.0] - 2026-10-29

Needs unseenet 0.6 (`unseenet>=0.6,<0.7`): update the nodes first.

- **Ripening to the level you choose** (#24, unseenet#740): `unseenet-bots ripen` ripens
  every bot's key, one after the other, to `ripen_to` in `[defaults]`, else
  `UNSEENET_RIPEN_TO`, else level 3, and goes on where it was after a restart. The
  container runs it in the background beside the hourly runs (`BOTS_RIPEN=no` to turn it
  off). Level 4 takes two to three weeks of one core, then every post costs about a
  quarter of the postage. The project's own bots run at 4.
- **A container image** (#18, unseenet/unseenet#571): `ghcr.io/unseenet/bots` - the
  runner on the node image, `bots.toml`, keys and state in `/data`, and the schedule
  inside the container (every hour plus up to 15 minutes at random), so the host needs
  no cron - and a `compose.yaml`. Published for amd64 and arm64 only for release tags,
  through the project's shared workflow. See *In Docker* in the docs.

- **Posts say their language** (UN-RFC 0052 5a): `Content-Language` from the bot's source
  (`options.lang`), else a one-language profile; none otherwise.

## [0.2.1] - 2026-10-25

### Changed

- The bots' profiles link their channel as `unseenet:<group-id>`, the form clients from unseenet 0.5 open (unseenet#386), instead of `unseenet:join?g=`. Profiles are published again on the next run.

## [0.2.0] - 2026-10-25

For unseenet 0.5 (`unseenet>=0.5,<0.6`); update the nodes first. Bots get profiles, and post pictures where the source's licence allows it.

### Added

- **Pictures on posts, only where the licence allows it** (#7): `pictures =
  "yes" | "check" | "no"` per bot (default `no`). NASA's Image of the Day
  (not copyrighted, `yes`) and the picture of a Wikipedia "In the news" story
  (`check`: posted only when Wikimedia Commons says public domain, CC0, CC BY
  or CC BY-SA). Each gets a credit line with its author, licence and page;
  big pictures are scaled down to 1600 px and cleaned of metadata by the core.
  Without a core that posts files (unseenet 0.5), or where the group or node
  takes none, the post links to the picture with the same credit.
- **Profiles for the bots** (#8): each run first publishes the bot's public
  profile with the bot mark (UN-RFC 0022), Markdown About text, links,
  languages and optionally a ready 128 px WebP picture - only when new or
  changed. Every About ends with the same line: run by the Unseenet project,
  comment below each post, not affiliated with the source, and the channel.
  `unseenet-bots profile [BOT ...]` publishes them without posting;
  `--dry-run` shows them. Draft texts for the six bots in `bots.example.toml`.

## [0.1.0] - 2026-10-22

The first release. Works with unseenet 0.4 (`unseenet>=0.4.1,<0.5`); nodes
from 0.4.0 need each bot key ripened once before it can post (see the
README's setup step).

### Added

- `unseenet-bots`: a runner that posts new items from each source to its
  own channel, one bot key per channel, posting through the core's
  `Session`, so ripening and postage are the same as in the clients.
- Sources: Wikipedia *In the news* and *On this day*, Global Voices,
  The Conversation, EFF Deeplinks and NASA Image of the Day, each posting
  Markdown with a link to the original and only items from the last two
  days (`max_age_hours`).
- Each bot key's ripening chain is kept beside its key file
  (`<key file>.state.json`, public), so a key ripens once (#3).
- `contrib/`: systemd units for a user service and for a dedicated `bots`
  user with an hourly timer.

[Unreleased]: https://github.com/unseenet/unseenet-bots/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/unseenet/unseenet-bots/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/unseenet/unseenet-bots/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/unseenet/unseenet-bots/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/unseenet/unseenet-bots/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/unseenet/unseenet-bots/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/unseenet/unseenet-bots/releases/tag/v0.1.0
