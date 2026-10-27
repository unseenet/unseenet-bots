# Changelog

All notable changes to unseenet-bots are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/) on the same principles as
[unseenet](https://github.com/unseenet/unseenet/blob/main/docs/development.md#versioning).

## [Unreleased]

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

[Unreleased]: https://github.com/unseenet/unseenet-bots/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/unseenet/unseenet-bots/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/unseenet/unseenet-bots/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/unseenet/unseenet-bots/releases/tag/v0.1.0
