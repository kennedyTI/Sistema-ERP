#!/usr/bin/env sh
set -e

HOST="$1"
PORT="$2"
shift 2

until nc -z "$HOST" "$PORT"; do
  echo "Aguardando ${HOST}:${PORT}..."
  sleep 1
done

exec "$@"
