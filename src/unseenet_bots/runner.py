"""Run bots from a config file. Each run fetches each bot's source once and
posts what is new; schedule it with a systemd timer or cron.

    unseenet-bots -c bots.toml new-key news.key   # make a key; make it a poster
    unseenet-bots -c bots.toml run --dry-run      # show what would be posted
    unseenet-bots -c bots.toml run                # post
    unseenet-bots -c bots.toml run news           # only the bot named news
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from unseenet.core import crypto
from unseenet.core.poster import Poster, PosterError, load_key

from .sources import Item, get_source

KEEP = 1000          # remembered item IDs per bot


@dataclass
class Bot:
    name: str
    source: str
    group: str
    from_name: str
    options: dict = field(default_factory=dict)
    key_file: str | None = None
    vault: str | None = None
    identity: str | None = None
    seed_env: str = "UNSEENET_SEED"
    max_per_run: int = 5
    nodes: list[str] | None = None


def load_config(path: Path) -> tuple[dict, list[Bot]]:
    data = tomllib.loads(path.read_text())
    defaults = data.get("defaults", {})
    bots = []
    for name, b in data.get("bots", {}).items():
        try:
            bots.append(Bot(
                name=name, source=b["source"], group=b["group"],
                from_name=b.get("from_name", f"{name} (bot)"), options=b.get("options", {}),
                key_file=_path(b.get("key_file")), vault=_path(b.get("vault")),
                identity=b.get("identity"), seed_env=b.get("seed_env", "UNSEENET_SEED"),
                max_per_run=int(b.get("max_per_run", 5)),
                nodes=b.get("nodes", defaults.get("nodes"))))
        except KeyError as exc:
            raise SystemExit(f"bot {name}: missing {exc}") from exc
    return defaults, bots


def _path(value: str | None) -> str | None:
    return os.path.expanduser(value) if value else None


class State:
    """Which items each bot has posted: {bot: {item id: Message-ID}}."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.data = json.loads(path.read_text())
        except (OSError, ValueError):
            self.data = {}

    def posted(self, bot: str) -> dict:
        return self.data.setdefault(bot, {})

    def mark(self, bot: str, item_id: str, message_id: str) -> None:
        posted = self.posted(bot)
        posted[item_id] = message_id
        for old in list(posted)[:-KEEP]:
            del posted[old]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        tmp.replace(self.path)


def new_items(items: list[Item], seen: dict, recent_subjects: set[str], limit: int) -> list[Item]:
    out = [i for i in items if i.id not in seen and i.subject not in recent_subjects]
    return out[:limit]


async def run_bot(bot: Bot, state: State, dry_run: bool = False, today=None,
                  poster_factory=Poster, out=print) -> int:
    """Post what is new for one bot. Returns the number of posts made."""
    today = today or datetime.now(timezone.utc).date()
    source = get_source(bot.source, **bot.options)
    items = source.fetch(today)
    if dry_run:
        for item in new_items(items, state.posted(bot.name), set(), bot.max_per_run):
            out(f"--- {bot.name} -> {bot.group}\nSubject: {item.subject}\n\n{item.body}")
        return 0
    key = load_key(key_file=bot.key_file, vault=bot.vault, identity=bot.identity,
                   seed_env=bot.seed_env)
    posted = 0
    async with poster_factory(key, bot.nodes, from_name=bot.from_name,
                              log=lambda m: out(f"  {bot.name}: {m}")) as p:
        recent = {subject for _, subject in await p.recent_threads(bot.group)}
        for item in new_items(items, state.posted(bot.name), recent, bot.max_per_run):
            result = await p.post(bot.group, item.subject, item.body)
            if result.ok:
                state.mark(bot.name, item.id, result.message_id)
                state.save()                  # after every post: a crash posts nothing twice
                posted += 1
                out(f"{bot.name}: posted {item.subject!r} to {len(result.accepted)} node(s)")
            else:
                out(f"{bot.name}: NOT posted {item.subject!r}: {result.refused or result.unreachable}")
    return posted


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-c", "--config", type=Path, default=Path("bots.toml"))
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="fetch and post what is new")
    r.add_argument("bots", nargs="*", help="only these bots (default: all)")
    r.add_argument("--dry-run", action="store_true", help="show the posts, post nothing")
    sub.add_parser("list", help="list the configured bots")
    k = sub.add_parser("new-key", help="make a key for a bot and show its public key")
    k.add_argument("file", type=Path)
    args = p.parse_args(argv)

    if args.cmd == "new-key":
        if args.file.exists():
            sys.exit(f"{args.file} exists; not overwriting a key")
        ident = crypto.Identity.generate()
        args.file.touch(mode=0o600)
        args.file.write_text(ident.seed.hex() + "\n")
        print(f"Wrote {args.file}. Make this key a poster in the bot's channel:\n{ident.key_text}")
        return

    defaults, bots = load_config(args.config)
    if args.cmd == "list":
        for b in bots:
            print(f"{b.name:16} {b.source:22} {b.group}")
        return
    chosen = [b for b in bots if not args.bots or b.name in args.bots]
    if not chosen:
        sys.exit("no such bot")
    state = State(Path(_path(defaults.get("state_file", "~/.local/state/unseenet-bots/state.json"))))
    failed = False
    for bot in chosen:
        try:
            asyncio.run(run_bot(bot, state, dry_run=args.dry_run))
        except (PosterError, OSError, ValueError) as exc:
            print(f"{bot.name}: failed: {exc}", file=sys.stderr)
            failed = True
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
