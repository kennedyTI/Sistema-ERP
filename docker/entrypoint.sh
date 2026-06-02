#!/usr/bin/env sh
set -e

# Entrypoint simples e seguro para todos os containers Python.
# As migrations ficam no servico dedicado "migrations" do docker-compose.

exec "$@"
