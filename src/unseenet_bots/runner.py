"""Run bots from a config file. Each run fetches each bot's source once and
posts what is new; schedule it with a systemd timer or cron.

    unseenet-bots -c bots.toml new-key news.key   # make a key; make it a poster
    unseenet-bots -c bots.toml run --dry-run      # show what would be posted
    unseenet-bots -c bots.toml run                # post
    unseenet-bots -c bots.toml run news           # only the bot named news
    unseenet-bots -c bots.toml profile --dry-run  # show the bots' public profiles
    unseenet-bots -c bots.toml profile            # publish them now, without posting

Each run publishes a bot's public profile first - with the bot mark, so clients
show that it is a bot - but only when its text or picture is new or has changed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import io
import json
import os
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from unseenet.core import crypto
from unseenet.core.markup import MARKDOWN_TYPE
from unseenet.core.poster import Poster, PosterError, load_key

from .sources import Item, Picture, free_licence, get_bytes, get_source

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
    max_per_day: int | None = None     # e.g. for sources that may not be republished whole
    max_age_hours: float = 48          # never post what the source published longer ago
    nodes: list[str] | None = None
    profile: dict = field(default_factory=dict)    # [bots.X.profile]: about, links, lang, picture
    pictures: str = "no"            # "yes", "check" or "no": pictures on posts (#7)
    cards: bool = True              # a link card for the item's page (#27, UN-RFC 0059)


PROFILE_FOOTER = ("An automatic channel run by the [Unseenet](https://unseenet.org) project - "
                  "comment below each post.{affiliation} Posts go to [{channel}]({address}).")
MAX_ABOUT = 2048                  # UN-RFC 0022 section 4.1


def channel_address(group: str) -> str:
    """The channel's ``unseenet:<group-id>`` address (UN-RFC 0031 section 3.4), which
    clients from 0.5 open."""
    return f"unseenet:{group}"


def bot_profile(bot: Bot) -> dict | None:
    """The bot's public profile (UN-RFC 0022): its About in Markdown with the footer
    every bot gets, its links and languages, and the bot mark. None when the config
    gives no profile."""
    cfg = bot.profile
    if not cfg:
        return None
    from unseenet.core.profiles import make_profile
    source = cfg.get("not_affiliated_with")
    about = cfg.get("about", "").strip()
    footer = PROFILE_FOOTER.format(
        affiliation=f" Not affiliated with {source}." if source else "",
        channel=bot.group.split("@")[0], address=channel_address(bot.group))
    text = (about + "\n\n" + footer) if about else footer
    if len(text) > MAX_ABOUT:
        raise ValueError(f"bot {bot.name}: the profile's about is over {MAX_ABOUT} characters")
    links = [{"kind": k, "value": v} for k, v in cfg.get("links", {}).items()]
    lang = cfg.get("lang")
    return make_profile(about=text, links=links, lang=[lang] if isinstance(lang, str) else lang,
                        bot=True, markdown=True)


def bot_picture(bot: Bot) -> dict | None:
    """The bot's profile picture: a file that is already the middle square, 128 px
    WebP without metadata (UN-RFC 0022 section 8.1), so any core can publish it."""
    path = bot.profile.get("picture")
    if not path:
        return None
    from unseenet.core.profiles import make_picture
    data = Path(_path(path)).read_bytes()
    return make_picture(data, "image/webp", int(bot.profile.get("picture_px", 128)),
                        alt=bot.profile.get("picture_alt", ""))


def _mark(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def _session_of(poster):
    """The Session a Poster posts through (core 0.4 and later)."""
    s = getattr(poster, "session", None) or getattr(poster, "_session", None)
    if s is None:
        raise ValueError("this unseenet core cannot publish profiles through its Poster")
    return s


async def publish_profile(bot: Bot, state: "State", poster, out=print, force: bool = False) -> bool:
    """Publish the bot's profile and picture when new or changed (or ``force``).
    Returns True when something was published. A failure is said and posting goes on."""
    marks = state.data.setdefault("_profiles", {}).setdefault(bot.name, {})
    done = False
    for what, make, publish in (("profile", bot_profile, "publish_profile"),
                                ("picture", bot_picture, "publish_picture")):
        try:
            obj = make(bot)
        except (OSError, ValueError) as exc:
            out(f"{bot.name}: no {what}: {exc}")
            continue
        if obj is None or (marks.get(what) == _mark(obj) and not force):
            continue
        try:
            await getattr(_session_of(poster), publish)(obj)
        except Exception as exc:  # noqa: BLE001 - posting goes on without it
            out(f"{bot.name}: could not publish the {what} yet: {exc}")
            continue
        marks[what] = _mark(obj)
        state.save()
        done = True
        out(f"{bot.name}: published the {what}" + (" with the bot mark" if what == "profile" else ""))
    return done


def load_config(path: Path) -> tuple[dict, list[Bot]]:
    data = tomllib.loads(path.read_text())
    defaults = data.get("defaults", {})
    bots = []
    for name, b in data.get("bots", {}).items():
        if name.startswith("_"):
            raise SystemExit(f"bot {name}: names starting with _ are reserved")
        try:
            bots.append(Bot(
                name=name, source=b["source"], group=b["group"],
                from_name=b.get("from_name", f"{name} (bot)"), options=b.get("options", {}),
                key_file=_path(b.get("key_file")), vault=_path(b.get("vault")),
                identity=b.get("identity"), seed_env=b.get("seed_env", "UNSEENET_SEED"),
                max_per_run=int(b.get("max_per_run", 5)),
                max_per_day=int(b["max_per_day"]) if "max_per_day" in b else None,
                max_age_hours=float(b.get("max_age_hours", 48)),
                nodes=b.get("nodes", defaults.get("nodes")),
                profile=b.get("profile", {}),
                pictures=_pictures_rule(name, b.get("pictures", "no")),
                cards=_cards_rule(name, b.get("cards", "yes"))))
        except KeyError as exc:
            raise SystemExit(f"bot {name}: missing {exc}") from exc
    return defaults, bots


def _pictures_rule(name: str, value) -> str:
    if value not in ("yes", "check", "no"):
        raise SystemExit(f"bot {name}: pictures is yes, check or no")
    return value


def _cards_rule(name: str, value) -> bool:
    if value in (True, "yes"):
        return True
    if value in (False, "no"):
        return False
    raise SystemExit(f"bot {name}: cards is yes or no")


# --- pictures on posts (#7): only where the licence clearly allows it ----------------

MAX_PICTURE_PX = 1600               # scaled down: a picture for reading, not for printing


def core_posts_files(poster_factory=Poster) -> bool:
    """Whether this core's Poster posts files (unseenet 0.5)."""
    cls = poster_factory if isinstance(poster_factory, type) else Poster
    return "files" in inspect.signature(cls.post).parameters


def core_makes_cards(poster_factory=Poster) -> bool:
    """Whether this core's Poster makes link cards (unseenet 0.6, UN-RFC 0059)."""
    cls = poster_factory if isinstance(poster_factory, type) else Poster
    return hasattr(cls, "make_card")


async def item_card(p, bot: Bot, item: Item, out=print):
    """The link card for the item's page (#27, UN-RFC 0059), made over Tor, or None.
    Its picture belongs to the page and has a licence of its own: it stays only where
    the bot posts what its source vouches for (``pictures = "yes"``) and the item brings
    no picture of its own; else the card goes without one."""
    if not bot.cards or not item.link:
        return None
    try:
        card = await p.make_card(item.link, language=_lang(bot) or "en")
    except (PosterError, OSError, ValueError) as exc:
        out(f"{bot.name}: no link card: {exc}")
        return None
    if not card.title.strip():
        out(f"{bot.name}: no link card for {item.link}: {card.note or 'no title'}")
        return None
    if bot.pictures != "yes" or item.pictures:
        card.picture = None
    return card


def _lang(bot: Bot) -> str:
    """The bot's language, as ``language_header`` gives it, or ''."""
    head = language_header(bot)
    return head[0][1] if head else ""


def allowed_pictures(bot: Bot, item: Item, out=print) -> list[tuple[Picture, str, str]]:
    """The item's pictures the bot may post, with their licence and author: "yes"
    takes what the source vouches for, "check" only a picture whose licence is known
    and free (public domain, CC0, CC BY, CC BY-SA), "no" none."""
    if bot.pictures == "no":
        return []
    chosen = []
    for pic in item.pictures:
        lic, author = pic.licence, pic.author
        if lic is None and pic.lookup is not None:
            try:
                found = pic.lookup()
            except Exception as exc:  # noqa: BLE001 - then only the link
                out(f"{bot.name}: licence of {pic.url} not known: {exc}")
                found = None
            if found:
                lic, author = found
        if (bot.pictures == "yes" and lic is not None) or free_licence(lic):
            chosen.append((pic, lic or "", author))
        else:
            out(f"{bot.name}: picture left out ({lic or 'licence unknown'}): {pic.url}")
    return chosen


def credit_line(pic: Picture, licence: str, author: str, attached: bool) -> str:
    """The credit under a picture: what it shows, who made it, its licence, its page."""
    who = f" by {author}" if author and author.lower() not in licence.lower() else ""
    where = pic.page or pic.url
    what = "Picture" if attached else f"[Picture]({pic.url})"
    return f"*{what}{': ' + pic.alt if pic.alt else ''}{who}, {licence} - [{where}]({where})*"


def scale_down(octets: bytes, max_px: int = MAX_PICTURE_PX) -> bytes:
    """A big picture made smaller (the core takes its metadata out when it posts)."""
    try:
        from PIL import Image
    except ImportError:
        return octets
    try:
        im = Image.open(io.BytesIO(octets))
        if max(im.size) <= max_px:
            return octets
        fmt = im.format or "JPEG"
        im.thumbnail((max_px, max_px))
        if fmt == "JPEG" and im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, fmt, **({"quality": 85} if fmt in ("JPEG", "WEBP") else {}))
        return buf.getvalue()
    except Exception:  # noqa: BLE001 - not a picture we can read: as it is
        return octets


def language_header(bot: Bot) -> list[tuple[str, str]]:
    """``Content-Language`` for what a bot posts (UN-RFC 0052 5a): its source's language
    (``options.lang``), else its profile's when it names one; none when neither says."""
    lang = (bot.options or {}).get("lang") or bot.profile.get("lang")
    if isinstance(lang, list):
        lang = lang[0] if len(lang) == 1 else None
    lang = (lang or "").strip().lower().split("-")[0]
    return [("Content-Language", lang)] if 2 <= len(lang) <= 3 and lang.isalpha() else []


async def post_item(p, bot: Bot, item: Item, files_ok: bool, out=print, fetch=get_bytes,
                    cards_ok: bool = False):
    """Post an item, with the pictures its licence allows when the core can, else a
    link to each with its credit; without them if the group or the node takes none.
    With ``cards_ok``, a link card for the item's page goes with it (#27)."""
    card = await item_card(p, bot, item, out) if cards_ok else None
    pics = allowed_pictures(bot, item, out)
    files = []
    if pics and files_ok:
        for pic, _, _ in pics:
            try:
                octets = scale_down(fetch(pic.url, "image/*"))
                files.append((pic.url.rsplit("/", 1)[-1][:100] or "picture", octets, pic.alt))
            except (OSError, ValueError) as exc:
                out(f"{bot.name}: picture not fetched: {exc}")

    def body(attached: bool) -> str:
        if not pics:
            return item.body
        lines = [credit_line(pic, lic, author, attached) for pic, lic, author in pics]
        return item.body.rstrip("\n") + "\n\n" + "\n\n".join(lines) + "\n"

    if files or (card is not None and card.picture is not None):
        try:
            result = await p.post(bot.group, item.subject, body(bool(files)), files=files or None,
                                  content_type=MARKDOWN_TYPE, extra=language_header(bot),
                                  **({"card": card} if card is not None else {}))
            if result.ok:
                return result
            out(f"{bot.name}: not posted with its picture "
                f"({result.refused or result.unreachable}); posting a link instead")
        except PosterError as exc:
            out(f"{bot.name}: picture not posted ({exc}); posting a link instead")
        if card is not None:
            card.picture = None                    # where files go nowhere, the card goes bare
    if card is not None:
        try:
            return await p.post(bot.group, item.subject, body(False), content_type=MARKDOWN_TYPE,
                                extra=language_header(bot), card=card)
        except PosterError as exc:
            out(f"{bot.name}: link card not posted ({exc}); posting without it")
    return await p.post(bot.group, item.subject, body(False), content_type=MARKDOWN_TYPE,
                        extra=language_header(bot))


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

    def mark(self, bot: str, item_id: str, message_id: str, now: datetime | None = None) -> None:
        posted = self.posted(bot)
        posted[item_id] = message_id
        for old in list(posted)[:-KEEP]:
            del posted[old]
        times = self.data.setdefault("_times", {}).setdefault(bot, [])
        times.append((now or datetime.now(timezone.utc)).isoformat())
        del times[:-KEEP]

    def posted_since(self, bot: str, since: datetime) -> int:
        return sum(1 for t in self.data.get("_times", {}).get(bot, [])
                   if datetime.fromisoformat(t) >= since)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        tmp.replace(self.path)


def new_items(items: list[Item], seen: dict, recent_subjects: set[str], limit: int,
              now: datetime | None = None, max_age_hours: float | None = None) -> list[Item]:
    """What to post now: not posted before, not too old, at most ``limit``."""
    oldest = (now or datetime.now(timezone.utc)) - timedelta(hours=max_age_hours) \
        if max_age_hours else None
    out = [i for i in items if i.id not in seen and i.subject not in recent_subjects
           and (oldest is None or i.published is None or i.published >= oldest)]
    return out[:max(0, limit)]


def key_state(bot: Bot) -> Path | None:
    """Where the bot key's ripening chain is kept (UN-RFC 0025): next to its key file,
    where ``unseenet ripen --key-file`` puts it at setup, so a key ripened there is the
    one that posts. Holds nothing secret. Without a key file, the core's default."""
    return Path(_path(bot.key_file) + ".state.json") if bot.key_file else None


def _limit(bot: Bot, state: State, now: datetime) -> int:
    if bot.max_per_day is None:
        return bot.max_per_run
    left = bot.max_per_day - state.posted_since(bot.name, now - timedelta(days=1))
    return min(bot.max_per_run, left)


async def ripen_bots(bots: list[Bot], to: int | None = None, out=print,
                     poster_factory=Poster) -> None:
    """Ripen each bot's key, one after the other, to ``to`` - the level from
    ``service_ripen_to()``: ``ripen_to`` in [defaults], else ``UNSEENET_RIPEN_TO``, else 3
    (#24, unseenet#740) - publishing ripe@ at each level. Runs for weeks to reach 4, and
    goes on where it was after a restart: ripen in the background beside the hourly runs
    (the container does; see "Ripening" in the docs). Keys shared by bots ripen once."""
    from unseenet.client.runtime import ClientRuntime, service_ripen_to
    level = service_ripen_to(to)
    done: set[str] = set()
    for bot in bots:
        key = load_key(key_file=bot.key_file, vault=bot.vault, identity=bot.identity,
                       seed_env=bot.seed_env)
        if key.key_text in done:
            continue
        done.add(key.key_text)
        out(f"{bot.name}: ripening {key.key_text[:20]}... to level {level}")
        async with poster_factory(key, bot.nodes, from_name=bot.from_name, state=key_state(bot),
                                  log=lambda m, n=bot.name: out(f"  {n}: {m}")) as p:
            s = _session_of(p)
            await ClientRuntime(s, ripen_to=level).ripen()
            out(f"{bot.name}: level {s.ripening().level}")


async def run_bot(bot: Bot, state: State, dry_run: bool = False, today=None,
                  poster_factory=Poster, out=print, now: datetime | None = None) -> int:
    """Post what is new for one bot. Returns the number of posts made."""
    now = now or datetime.now(timezone.utc)
    today = today or now.date()
    limit = _limit(bot, state, now)
    if limit <= 0:
        out(f"{bot.name}: {bot.max_per_day} posts in the last day already; waiting")
        return 0
    source = get_source(bot.source, **bot.options)
    items = source.fetch(today)
    if dry_run:
        for item in new_items(items, state.posted(bot.name), set(), limit, now, bot.max_age_hours):
            for pic, lic, _ in allowed_pictures(bot, item, out):
                out(f"--- {bot.name}: picture for {item.subject!r}: {pic.url} ({lic})")
        prof = bot_profile(bot)
        marks = state.data.get("_profiles", {}).get(bot.name, {})
        if prof and marks.get("profile") != _mark(prof):
            out(f"--- {bot.name}: would publish its profile first\n{prof.get('about', '')}")
        for item in new_items(items, state.posted(bot.name), set(), limit, now, bot.max_age_hours):
            out(f"--- {bot.name} -> {bot.group}\nSubject: {item.subject}\n\n{item.body}")
            if bot.cards and item.link:
                out(f"--- {bot.name}: link card for {item.link}"
                    + (" (with the page's picture)" if bot.pictures == "yes" and not item.pictures
                       else " (without a picture)"))
        return 0
    key = load_key(key_file=bot.key_file, vault=bot.vault, identity=bot.identity,
                   seed_env=bot.seed_env)
    posted = 0
    async with poster_factory(key, bot.nodes, from_name=bot.from_name, state=key_state(bot),
                              log=lambda m: out(f"  {bot.name}: {m}")) as p:
        await publish_profile(bot, state, p, out)
        recent = {subject for _, subject in await p.recent_threads(bot.group)}
        files_ok = bot.pictures != "no" and core_posts_files(poster_factory)
        cards_ok = bot.cards and core_makes_cards(poster_factory)
        for item in new_items(items, state.posted(bot.name), recent, limit, now, bot.max_age_hours):
            # Markdown (Item.body), with the pictures its licence allows (#7)
            result = await post_item(p, bot, item, files_ok, out, cards_ok=cards_ok)
            if result.ok:
                state.mark(bot.name, item.id, result.message_id, now)
                state.save()                  # after every post: a crash posts nothing twice
                posted += 1
                out(f"{bot.name}: posted {item.subject!r} to {len(result.accepted)} node(s)")
            else:
                out(f"{bot.name}: NOT posted {item.subject!r}: {result.refused or result.unreachable}")
    return posted


async def profile_bot(bot: Bot, state: State, dry_run: bool = False, poster_factory=Poster,
                      out=print) -> bool:
    """``unseenet-bots profile``: publish one bot's profile now (``--dry-run``: show it)."""
    if dry_run:
        prof, pic = bot_profile(bot), bot_picture(bot)
        out(f"--- {bot.name}: profile\n" + (json.dumps(prof, indent=1, ensure_ascii=False)
                                           if prof else "(none in the config)"))
        if pic:
            out(f"--- {bot.name}: picture, {pic['px']} px, alt {pic.get('alt', '')!r}")
        return False
    key = load_key(key_file=bot.key_file, vault=bot.vault, identity=bot.identity,
                   seed_env=bot.seed_env)
    async with poster_factory(key, bot.nodes, from_name=bot.from_name, state=key_state(bot),
                              log=lambda m: out(f"  {bot.name}: {m}")) as p:
        return await publish_profile(bot, state, p, out, force=True)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-c", "--config", type=Path, default=Path("bots.toml"))
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="fetch and post what is new")
    r.add_argument("bots", nargs="*", help="only these bots (default: all)")
    r.add_argument("--dry-run", action="store_true", help="show the posts, post nothing")
    sub.add_parser("list", help="list the configured bots")
    pr = sub.add_parser("profile", help="publish the bots' public profiles now, without posting")
    pr.add_argument("bots", nargs="*", help="only these bots (default: all)")
    pr.add_argument("--dry-run", action="store_true", help="show the profiles, publish nothing")
    rp_ = sub.add_parser("ripen", help="ripen the bots' keys to the configured level, in the "
                                       "background beside the hourly runs (weeks for level 4)")
    rp_.add_argument("bots", nargs="*", help="only these bots (default: all)")
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
    if args.cmd == "ripen":
        to = defaults.get("ripen_to")
        try:
            asyncio.run(ripen_bots(chosen, int(to) if to is not None else None))
        except (PosterError, OSError, ValueError) as exc:
            sys.exit(f"ripening stopped: {exc}")
        return
    state = State(Path(_path(defaults.get("state_file", "~/.local/state/unseenet-bots/state.json"))))
    failed = False
    for bot in chosen:
        try:
            if args.cmd == "profile":
                asyncio.run(profile_bot(bot, state, dry_run=args.dry_run))
                continue
            asyncio.run(run_bot(bot, state, dry_run=args.dry_run))
        except (PosterError, OSError, ValueError) as exc:
            print(f"{bot.name}: failed: {exc}", file=sys.stderr)
            failed = True
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
