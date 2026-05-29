#!/usr/bin/env bash
# Launch the Notion Pilot web setup UI.
#
# Reads WEB_ADMIN_USERNAME, WEB_ADMIN_PASSWORD, WEB_SECRET_KEY from .env if present.
# Override any value by exporting it before running this script.
#
# Usage:
#   ./launch_webserver.sh              # reads .env, default port 8080
#   PORT=9000 ./launch_webserver.sh    # custom port

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env if present (skip lines that are comments or empty)
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  while IFS='=' read -r key value; do
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    # Only export web-related vars that aren't already set
    if [[ "$key" =~ ^WEB_ ]] && [[ -z "${!key:-}" ]]; then
      export "$key=$value"
    fi
  done < "$SCRIPT_DIR/.env"
fi

# Defaults
WEB_ADMIN_USERNAME="${WEB_ADMIN_USERNAME:-admin}"
WEB_ADMIN_PASSWORD="${WEB_ADMIN_PASSWORD:-}"
WEB_SECRET_KEY="${WEB_SECRET_KEY:-}"
PORT="${PORT:-8080}"

# Validate required vars
if [[ -z "$WEB_ADMIN_PASSWORD" ]]; then
  echo "ERROR: WEB_ADMIN_PASSWORD is not set."
  echo "  Add it to .env or export it before running this script."
  exit 1
fi

if [[ -z "$WEB_SECRET_KEY" ]]; then
  echo "ERROR: WEB_SECRET_KEY is not set."
  echo "  Add it to .env or export it before running this script."
  exit 1
fi

export WEB_ADMIN_USERNAME
export WEB_ADMIN_PASSWORD
export WEB_SECRET_KEY

echo "Starting Notion Pilot web UI on http://0.0.0.0:${PORT}"
echo "  Admin user : $WEB_ADMIN_USERNAME"
echo "  Press Ctrl+C to stop."
echo ""

cd "$SCRIPT_DIR"
exec uv run uvicorn web.server:app_factory --factory \
  --host 0.0.0.0 \
  --port "$PORT"
