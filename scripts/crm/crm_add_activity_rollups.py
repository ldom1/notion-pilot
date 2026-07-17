#!/usr/bin/env python
"""Add Last Activity rollups + derived formulas to Deals, People, Companies.

Prerequisites:
- Activities DB created (Task 1)
- Back-relations on Deals/People/Companies named "Activities" (verify with probe)

Rollup: Last Activity Date = max(Activities.Date) on each parent DB

Formulas on Deals (stage-aware — terminal deals return 0, not 999):
  Days Since Last Activity  = 0 if terminal stage, 999 if no activity, else dateBetween(...)
  Deal Age (days)           = dateBetween(now(), Created time, "days")
  Deal Temperature          = 🔥/🌡/❄️ based on days; "—" if terminal (incl. No Answer)
  Stale Deal                = open deal + no Next Step + no activity in 14+ days
  Next Step Scheduled       = not(empty(Next Step Date))

Formulas on People / Companies (no Stage, simpler):
  Days Since Last Activity  = 999 if no activity, else dateBetween(...)

Manual fallback (rollup 400 errors):
  If rollup creation fails, create "Last Activity Date" manually in Notion UI:
  Open DB → Add property → Rollup → Relation: Activities → Property: Date → Calculate: Latest date
  Formulas will show an error until the rollup property exists — safe to add later.
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

COMMERCIAL_ID = "4890e1d6-178d-4a42-af06-7bbe0cef09fe"
PEOPLE_ID = "11b5f43c-a19a-4bec-9489-7c6897ed30fb"
COMPANIES_ID = "cfc21198-9684-47ef-98ae-fc5657511998"

# The name of the Activities back-relation on each DB.
# Verified by probe: "Activities" on all three parent DBs.
ACTIVITIES_RELATION_PROP = "Activities"

ACTIVITIES_DATE_PROP = "Date"  # Name of the Date property in Activities DB


async def patch_db(
    client: httpx.AsyncClient,
    token: str,
    db_id: str,
    properties: dict,
    *,
    allow_400: bool = False,
) -> bool:
    """Patch a Notion database with the given properties.

    Returns True on success. If allow_400 is True, logs a warning on 400 and
    returns False instead of raising — used for rollup creation so we can
    continue to formula steps even when rollup API rejects the payload.
    """
    r = await client.patch(
        f"{NOTION_API}/databases/{db_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        json={"properties": properties},
    )
    if r.status_code == 400 and allow_400:
        logger.warning(
            "⚠ Rollup creation returned 400 for DB {} — manual action required.\n"
            "  Error: {}\n"
            "  → In Notion UI: open the DB → Add property → Rollup\n"
            "      Relation: Activities  |  Property: Date  |  Calculate: Latest date\n"
            "  Formulas that reference 'Last Activity Date' will show an error in Notion\n"
            "  until the rollup is created manually. This is safe to fix later.",
            db_id,
            r.text,
        )
        return False
    if r.status_code != 200:
        logger.error("Failed to patch DB {}: {} {}", db_id, r.status_code, r.text)
        r.raise_for_status()
    logger.info("✅ Patched {}", db_id)
    return True


async def main() -> None:
    token = os.environ["NOTION_TOKEN"]

    # Terminal-stage expression reused across several Deals formulas.
    # NOTE: Notion formula 1.0 (API) only accepts or() with exactly 2 arguments —
    # use nested or(or(a, b), c) to combine three conditions.
    _terminal = (
        'or(or(prop("Stage") == "Closed Won", prop("Stage") == "Closed Lost"), '
        'prop("Stage") == "No Answer")'
    )

    async with httpx.AsyncClient(timeout=30) as client:
        # ── Commercial / Deals ─────────────────────────────────────────────────

        logger.info("Deals: creating Last Activity Date rollup…")
        await patch_db(
            client,
            token,
            COMMERCIAL_ID,
            {
                "Last Activity Date": {
                    "rollup": {
                        "relation_property_name": ACTIVITIES_RELATION_PROP,
                        "rollup_property_name": ACTIVITIES_DATE_PROP,
                        "function": "latest_date",
                    }
                },
            },
            allow_400=True,
        )

        # Step 1: formulas that don't depend on other new formulas
        logger.info("Deals: adding base formulas (Days Since Last Activity, Deal Age)…")
        await patch_db(
            client,
            token,
            COMMERCIAL_ID,
            {
                "Days Since Last Activity": {
                    "formula": {
                        "expression": (
                            f"if({_terminal}, 0, "
                            'if(empty(prop("Last Activity Date")), 999, '
                            'dateBetween(now(), prop("Last Activity Date"), "days")))'
                        )
                    }
                },
                "Deal Age (days)": {
                    "formula": {"expression": 'dateBetween(now(), prop("Created time"), "days")'}
                },
                "Next Step Scheduled": {
                    "formula": {"expression": 'not(empty(prop("Next Step Date")))'}
                },
            },
        )

        # Step 2: Deal Temperature and Stale Deal
        # NOTE: Notion formula 1.0 (API) has two constraints:
        #   1. Cannot reference formula properties — must inline the raw expression.
        #   2. and() / or() only support 2 args reliably when mixed with complex
        #      expressions; nest 2-arg calls for 3+ conditions.
        # - empty Last Activity Date → treated as "no activity" (Cold / stale)
        # - terminal stage → "—" (Deal Temperature) or excluded from stale check
        _days = 'dateBetween(now(), prop("Last Activity Date"), "days")'

        logger.info("Deals: adding Deal Temperature and Stale Deal formulas…")
        await patch_db(
            client,
            token,
            COMMERCIAL_ID,
            {
                "Deal Temperature": {
                    "formula": {
                        "expression": (
                            f'if({_terminal}, "—", '
                            f'if(empty(prop("Last Activity Date")), "❄️ Cold", '
                            f'if({_days} <= 7, "🔥 Hot", '
                            f'if({_days} <= 21, "🌡 Warm", '
                            '"❄️ Cold"))))'
                        )
                    }
                },
                # Stale = open deal AND no Next Step AND no activity in 14+ days.
                # Use nested 2-arg and() to avoid Notion 1.0 type inference bug
                # with 3-arg and() when args contain complex sub-expressions.
                "Stale Deal": {
                    "formula": {
                        "expression": (
                            f"and(not({_terminal}), "
                            f'and(empty(prop("Next Step")), '
                            f'if(empty(prop("Last Activity Date")), true, {_days} > 14)))'
                        )
                    }
                },
            },
        )

        # ── People ─────────────────────────────────────────────────────────────

        logger.info("People: creating Last Activity Date rollup…")
        await patch_db(
            client,
            token,
            PEOPLE_ID,
            {
                "Last Activity Date": {
                    "rollup": {
                        "relation_property_name": ACTIVITIES_RELATION_PROP,
                        "rollup_property_name": ACTIVITIES_DATE_PROP,
                        "function": "latest_date",
                    }
                },
            },
            allow_400=True,
        )

        logger.info("People: adding formula…")
        await patch_db(
            client,
            token,
            PEOPLE_ID,
            {
                "Days Since Last Activity": {
                    "formula": {
                        "expression": (
                            'if(empty(prop("Last Activity Date")), '
                            "999, "
                            'dateBetween(now(), prop("Last Activity Date"), "days"))'
                        )
                    }
                },
            },
        )

        # ── Companies ──────────────────────────────────────────────────────────

        logger.info("Companies: creating Last Activity Date rollup…")
        await patch_db(
            client,
            token,
            COMPANIES_ID,
            {
                "Last Activity Date": {
                    "rollup": {
                        "relation_property_name": ACTIVITIES_RELATION_PROP,
                        "rollup_property_name": ACTIVITIES_DATE_PROP,
                        "function": "latest_date",
                    }
                },
            },
            allow_400=True,
        )

        logger.info("Companies: adding formula…")
        await patch_db(
            client,
            token,
            COMPANIES_ID,
            {
                "Days Since Last Activity": {
                    "formula": {
                        "expression": (
                            'if(empty(prop("Last Activity Date")), '
                            "999, "
                            'dateBetween(now(), prop("Last Activity Date"), "days"))'
                        )
                    }
                },
            },
        )

    logger.info("✅ All rollups and formulas applied.")


if __name__ == "__main__":
    asyncio.run(main())
