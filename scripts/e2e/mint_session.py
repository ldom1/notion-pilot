"""Mint a Playwright storageState containing a signed Notion session cookie.

The deploy wizard sits behind Notion OAuth, which cannot be automated. To drive
the *real* wizard end to end we forge the same signed session cookie Starlette's
SessionMiddleware would have set after a successful callback, and hand it to
Playwright as a storageState file.

This is a test affordance, not a back door: it needs the app's own
WEB_SESSION_SECRET and a real Notion token, i.e. exactly the secrets an operator
already holds. No test-only bypass is added to the application.

LIMIT — read before using this for the deploy wizard. A session minted from the
internal-integration NOTION_TOKEN authenticates against /api/cockpit/* but
CANNOT run a deploy. create_workspace_root_page posts `parent: {workspace: true}`
and Notion answers 400: "Internal integrations aren't owned by a single user, so
creating workspace-level private pages is not supported." Only a
public-integration OAuth token carries the insert_content capability that needs.
For the full wizard, capture a real OAuth session instead:

    npx playwright open --save-storage=web/frontend/e2e/.auth/state.json \
      http://127.0.0.1:8099/auth/notion

Use this script for cockpit API tests against an already-configured workspace.

Usage:
    INFISICAL_ENV=prod \\
    NOTION_OAUTH_REDIRECT_URI="https://notion-pilot.dombot.tech/auth/notion/callback" \\
    uv run python scripts/e2e/mint_session.py --base-url http://127.0.0.1:8080

Writes web/frontend/e2e/.auth/state.json (gitignored).
"""

from __future__ import annotations

import argparse
import base64
import json
import pathlib
import sys
from urllib.parse import urlparse

import itsdangerous

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "web" / "frontend" / "e2e" / ".auth" / "state.json"


def _session_cookie(secret: str, payload: dict) -> str:
    """Reproduce starlette.middleware.sessions.SessionMiddleware's cookie value.

    Starlette signs standard, padded base64 (`base64.b64encode`) — not
    itsdangerous' URL-safe unpadded variant. Using the latter makes the server
    fail with "binascii.Error: Incorrect padding" on unsign.
    """
    signer = itsdangerous.TimestampSigner(str(secret))
    data = base64.b64encode(json.dumps(payload).encode("utf-8"))
    return signer.sign(data).decode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument(
        "--workspace-id",
        default="e2e-playwright",
        help="cockpit workspace id; keep it distinct from any real one",
    )
    args = ap.parse_args()

    sys.path.insert(0, str(REPO_ROOT))
    from notion_pilot.shared.config import load_settings  # noqa: PLC0415

    settings = load_settings()
    if not settings.notion_token:
        print("no notion_token in settings — cannot mint a session", file=sys.stderr)
        return 1
    secret = settings.web_session_secret
    if not secret:
        print(
            "WEB_SESSION_SECRET is unset. The app falls back to a random per-process "
            "secret, which a forged cookie can never match — set it for both the "
            "server and this script.",
            file=sys.stderr,
        )
        return 1

    payload = {
        "notion_token": settings.notion_token.get_secret_value(),
        "workspace_id": args.workspace_id,
        "workspace_name": "Playwright E2E",
        "user_name": "playwright",
    }
    cookie = _session_cookie(secret.get_secret_value(), payload)

    parsed = urlparse(args.base_url)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "session",
                        "value": cookie,
                        "domain": parsed.hostname or "127.0.0.1",
                        "path": "/",
                        "httpOnly": True,
                        "secure": False,
                        "sameSite": "Lax",
                        "expires": -1,
                    }
                ],
                "origins": [],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {OUT.relative_to(REPO_ROOT)} for {args.base_url}")
    print("this file contains a real Notion token — it is gitignored; delete it when done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
