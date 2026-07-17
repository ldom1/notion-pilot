"""Build Notion page-body blocks and a set-level Description for multi-link
Telegram messages, from already-fetched, factual link metadata only."""

from typing import Any

import httpx
from loguru import logger

from notion_pilot.shared.config import Settings
from notion_pilot.shared.llm.link_metadata import LinkMetadata
from notion_pilot.shared.models import IncomingMessage


def _bullet(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [{"text": {"content": text}}]},
    }


def _heading(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": [{"text": {"content": text}}]},
    }


_MAX_LINKS_IN_BODY = 15  # each link contributes up to 6 blocks; keeps the total safely
# under Notion's 100-children-per-pages.create limit


def build_link_body_blocks(items: list[LinkMetadata]) -> list[dict[str, Any]]:
    """One heading + up to 4 factual bullets per link. Never fabricates data —
    a failed fetch just gets the bare URL, no invented stats or summary.

    Truncates to _MAX_LINKS_IN_BODY links, appending a note naming the omitted
    count, instead of letting a large link list exceed Notion's 100-children
    limit and silently fail the entire page write."""
    truncated = items[:_MAX_LINKS_IN_BODY]
    blocks: list[dict[str, Any]] = []
    for item in truncated:
        blocks.append(_heading(item.title or item.url))
        if item.error:
            blocks.append(_bullet(f"{item.url} (could not fetch details: {item.error})"))
            continue
        if item.description:
            blocks.append(_bullet(item.description))
        if item.extra.get("language"):
            blocks.append(_bullet(f"Language: {item.extra['language']}"))
        if item.extra.get("stars"):
            blocks.append(_bullet(f"Stars: {item.extra['stars']}"))
        if item.extra.get("topics"):
            blocks.append(_bullet(f"Topics: {item.extra['topics']}"))
        blocks.append(_bullet(item.url))

    omitted = len(items) - len(truncated)
    if omitted:
        logger.warning(
            "synthesis: truncated {} of {} links from page body (Notion's block limit)",
            omitted,
            len(items),
        )
        blocks.append(
            _bullet(
                f"...and {omitted} more link(s) not shown (message exceeded Notion's block limit)"
            )
        )
    return blocks


async def synthesize_multi_link_description(
    settings: Settings, incoming: IncomingMessage, items: list[LinkMetadata]
) -> str:
    """One short OpenRouter call describing the *set* of links, grounded only
    in fetched metadata. Falls back to a deterministic joined-titles string on
    any LLM failure — never blocks the Notion write."""
    fallback = "A collection of links: " + ", ".join(i.title or i.url for i in items)
    key = settings.openrouter_api_key
    if key is None or not key.get_secret_value().strip():
        return fallback

    context = "\n".join(
        f"- {i.title or i.url}: {i.description or '(no description fetched)'}" for i in items
    )
    prompt = (
        "Write a 1-3 sentence summary describing this SET of links as a whole "
        "(not just the first one), based only on the fetched descriptions below. "
        "Never invent facts not present in the descriptions.\n\n"
        f"Original message: {incoming.body[:2000]}\n\n"
        f"Fetched link metadata:\n{context}\n\n"
        "Reply with ONLY the summary sentence(s), no markdown, no preamble."
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.openrouter_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openrouter_model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
        content: str = resp.json()["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("synthesis: multi-link description generation failed: {}", exc)
        return fallback
