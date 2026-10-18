# unseenet-bots

Bots that keep [Unseenet](https://unseenet.org) channels filled with
current content, and an example of how to build a bot on the Unseenet
core library.

**Status:** planning. Nothing runs yet; see the issues.

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
