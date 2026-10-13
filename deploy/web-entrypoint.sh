#!/bin/sh
set -eu

: "${API_UPSTREAM:?Set API_UPSTREAM to the approved internal API service origin}"
PORT="${PORT:-8080}"

case "$API_UPSTREAM" in
  http://*) authority="${API_UPSTREAM#http://}" ;;
  https://*) authority="${API_UPSTREAM#https://}" ;;
  *) echo "API_UPSTREAM must begin with http:// or https://" >&2; exit 1 ;;
esac
case "$authority" in
  ''|*/*|*\?*|*\#*|*@*) echo "API_UPSTREAM must be an origin without credentials, path or query" >&2; exit 1 ;;
esac
case "$authority" in
  *[!A-Za-z0-9:._-]*) echo "API_UPSTREAM contains an invalid character" >&2; exit 1 ;;
esac
case "$PORT" in
  ''|*[!0-9]*) echo "PORT must be numeric" >&2; exit 1 ;;
esac

export PORT API_UPSTREAM
envsubst '${PORT} ${API_UPSTREAM}' \
  < /etc/nginx/default.conf.template \
  > /tmp/nginx-conf/default.conf

exec "$@"
