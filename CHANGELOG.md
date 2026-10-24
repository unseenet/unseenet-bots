# Changelog

All notable changes to unseenet-bots are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[semantic versioning](https://semver.org/) on the same principles as
[unseenet](https://github.com/unseenet/unseenet/blob/main/docs/development.md#versioning).

## [Unreleased]

### Added

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

[Unreleased]: https://github.com/unseenet/unseenet-bots/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/unseenet/unseenet-bots/releases/tag/v0.1.0
