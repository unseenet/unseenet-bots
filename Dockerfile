# unseenet-bots in a container: the bot runner on the node image (core, chiavdf,
# Tor, tini). bots.toml, keys and state in /data; the schedule runs inside.
#
#   docker run --rm -v bots:/data ghcr.io/unseenet/bots                 # writes an example bots.toml
#   docker run --rm -v bots:/data ghcr.io/unseenet/bots new-key /data/.config/unseenet-bots/news.key
#   docker run -d --name bots -v bots:/data ghcr.io/unseenet/bots       # every hour
#
# See the docs ("In Docker") and compose.yaml.
ARG NODE_IMAGE=ghcr.io/unseenet/node:latest

FROM ${NODE_IMAGE} AS build
USER root
RUN apk add --no-cache gcc musl-dev python3-dev libffi-dev
COPY pyproject.toml README.md LICENSE bots.example.toml /src/
COPY src /src/src
RUN /opt/unseenet/bin/pip install --no-cache-dir /src \
 && find /opt/unseenet -name __pycache__ -type d -prune -exec rm -rf {} +

FROM ${NODE_IMAGE}
USER root
COPY --from=build /opt/unseenet /opt/unseenet
COPY bots.example.toml /opt/unseenet-bots/bots.example.toml
COPY docker/entrypoint.sh /usr/local/bin/unseenet-bots-entrypoint
RUN chmod 755 /usr/local/bin/unseenet-bots-entrypoint
ENV UNSEENET_DATA=/data
VOLUME /data
HEALTHCHECK NONE
LABEL org.opencontainers.image.title="Unseenet bots" \
      org.opencontainers.image.description="Bots that post news, history and more to Unseenet channels" \
      org.opencontainers.image.source="https://github.com/unseenet/unseenet-bots" \
      org.opencontainers.image.url="https://unseenet.org/bots/" \
      org.opencontainers.image.licenses="Apache-2.0"
ENTRYPOINT ["/sbin/tini", "--", "unseenet-bots-entrypoint"]
CMD []
