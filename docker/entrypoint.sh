#!/bin/sh
# unseenet-bots in a container (docs: "In Docker").
#
#   (no arguments)        run the bots now, then every BOTS_INTERVAL seconds (default an
#                         hour, plus up to BOTS_JITTER seconds at random) - no host cron
#   run, list, profile, new-key ...   that unseenet-bots command once, then exit
#   --help                as unseenet-bots
#   sh, python3, unseenet ...   run that program instead
#
# Everything is in /data: bots.toml, the bots' keys, their state and the core's state.
# Each run starts its own Tor (the core's Poster), so nothing else is needed.
set -eu
DATA=${UNSEENET_DATA:-/data}
CONFIG=${UNSEENET_BOTS_CONFIG:-$DATA/bots.toml}

# Started as root (the default): make /data ours, then drop root for good.
if [ "$(id -u)" = 0 ]; then
    if [ "$(stat -c %u "$DATA")" != 10001 ]; then
        chown -R unseenet:unseenet "$DATA"
    fi
    chmod 700 "$DATA"
    exec su-exec unseenet "$0" "$@"
fi
export HOME="$DATA" UNSEENET_STATE_DIR="${UNSEENET_STATE_DIR:-$DATA/keys-state}"

case "${1:-}" in
    sh|ash|python3|unseenet|unseenet-*) exec "$@" ;;
    -h|--help) exec unseenet-bots "$@" ;;
    new-key) mkdir -p "$(dirname "${2:-.}")"; exec unseenet-bots -c "$CONFIG" "$@" ;;
esac

if [ ! -f "$CONFIG" ]; then
    cp /opt/unseenet-bots/bots.example.toml "$CONFIG"
    echo "unseenet-bots: wrote an example $CONFIG - edit it and make the bots' keys" >&2
    echo "  (new-key /data/.config/unseenet-bots/news.key), then start again." >&2
    exit 64
fi
cd "$DATA"
if [ $# -gt 0 ]; then
    exec unseenet-bots -c "$CONFIG" "$@"
fi

INTERVAL=${BOTS_INTERVAL:-3600}
JITTER=${BOTS_JITTER:-900}
while true; do
    unseenet-bots -c "$CONFIG" run || echo "unseenet-bots: this run failed; again next time" >&2
    sleep $((INTERVAL + $(od -An -N2 -tu2 /dev/urandom) % (JITTER + 1)))
done
