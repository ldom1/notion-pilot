#!/usr/bin/env bash
# Launch the Notion Pilot web setup UI.
#
# Secrets are loaded from Infisical. Two modes:
#   - Local dev (CLI auth): run via `infisical run -- ./launch_webserver.sh`
#     or just `make dev` / `make dev-backend` (already wrapped).
#   - Docker / SDK path: set INFISICAL_CLIENT_ID + INFISICAL_CLIENT_SECRET +
#     INFISICAL_PROJECT_ID in .env.bootstrap; the Python SDK fetches the rest.
#
# Override any env var by exporting it before running this script.
#
# Usage:
#   make dev-backend               # preferred (wraps with infisical run --)
#   infisical run -- ./launch_webserver.sh
#   PORT=9000 infisical run -- ./launch_webserver.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Defaults
WEB_ADMIN_USERNAME="${WEB_ADMIN_USERNAME:-admin}"
WEB_ADMIN_PASSWORD="${WEB_ADMIN_PASSWORD:-}"
WEB_SECRET_KEY="${WEB_SECRET_KEY:-}"
PORT="${PORT:-8080}"

if [[ -z "$WEB_ADMIN_PASSWORD" ]]; then
  echo "ERROR: WEB_ADMIN_PASSWORD is not set."
  echo "  Run via: infisical run -- ./launch_webserver.sh"
  echo "  Or:      make dev-backend"
  exit 1
fi

if [[ -z "$WEB_SECRET_KEY" ]]; then
  echo "ERROR: WEB_SECRET_KEY is not set."
  echo "  Run via: infisical run -- ./launch_webserver.sh"
  echo "  Or:      make dev-backend"
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
  --reload \
  --host 0.0.0.0 \
  --port "$PORT"
