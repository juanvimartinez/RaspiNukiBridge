#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${CONFIG_FILE:-/config/nuki.yaml}"
DEBUG_FLAG=""

# Check if DEBUG environment variable is set
if [ "${DEBUG:-false}" = "true" ]; then
  DEBUG_FLAG="--debug"
fi

case "${1:-serve}" in
  generate-config)
    python . --generate-config > "${CONFIG_FILE}"
    echo "Generated ${CONFIG_FILE}"
    ;;
  pair)
    if [ -z "${2:-}" ]; then
      echo "Usage: docker compose run --rm raspinukibridge pair XX:XX:XX:XX:XX:XX"
      exit 1
    fi
    python . --config "${CONFIG_FILE}" --pair "$2"
    ;;
  lock)
    python . --config "${CONFIG_FILE}" --lock
    ;;
  unlock)
    python . --config "${CONFIG_FILE}" --unlock
    ;;
  serve)
    exec python . --config "${CONFIG_FILE}" ${DEBUG_FLAG}
    ;;
  *)
    exec "$@"
    ;;
esac
