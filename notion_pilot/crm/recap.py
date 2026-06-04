"""Format Notion query results into Telegram-safe messages."""

from __future__ import annotations

CAP_LEADS = 10
CAP_INBOX = 10
CAP_RECAP_SECTION = 5


def _overflow(items: list, cap: int, fmt: callable) -> str:
    visible = items[:cap]
    overflow = len(items) - cap
    lines = [fmt(i) for i in visible]
    if overflow > 0:
        lines.append(f"…and {overflow} more")
    return "\n".join(lines)


def format_leads(leads: list[dict]) -> str:
    if not leads:
        return "No open leads."
    body = _overflow(leads, CAP_LEADS, lambda d: f"• {d['title']} — {d['stage']}")
    return f"*Active Leads*\n{body}"


def format_inbox(items: list[dict]) -> str:
    if not items:
        return "Nothing to review."
    body = _overflow(items, CAP_INBOX, lambda i: f"• {i['title']}")
    return f"*À relire*\n{body}"


def format_recap(leads: list[dict], people: list[dict], inbox: list[dict]) -> str:
    sections = []

    # Leads
    if leads:
        body = _overflow(leads, CAP_RECAP_SECTION, lambda d: f"• {d['title']} — {d['stage']}")
        sections.append(f"*Active Leads*\n{body}")
    else:
        sections.append("*Active Leads*\nNone.")

    # Next actions (from leads that have one)
    actions = [d for d in leads if d.get("next_action")]
    if actions:
        body = _overflow(actions, CAP_RECAP_SECTION, lambda d: f"• {d['title']}: {d['next_action']}")
        sections.append(f"*Next Actions*\n{body}")

    # Recent people
    if people:
        body = _overflow(people, CAP_RECAP_SECTION, lambda p: f"• {p['name']} @ {p['company']}" if p.get("company") else f"• {p['name']}")
        sections.append(f"*People Added*\n{body}")

    # À relire
    if inbox:
        body = _overflow(inbox, CAP_RECAP_SECTION, lambda i: f"• {i['title']}")
        sections.append(f"*À relire*\n{body}")
    else:
        sections.append("*À relire*\nNothing to review.")

    return "\n\n".join(sections)
