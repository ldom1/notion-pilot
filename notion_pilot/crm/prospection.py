"""LLM-powered contact ranking for a B2B sales pitch."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

from notion_pilot.config import Settings
from notion_pilot.utils.dedup import CandidateRecord


@dataclass
class RankedContact:
    page_id: str
    name: str
    company: str
    position: str
    score: float
    reasoning: str
    linkedin_url: str = field(default="")


async def rank_contacts(
    pitch: str,
    candidates: list[CandidateRecord],
    settings: Settings,
    top_k: int = 10,
) -> list[RankedContact]:
    """Return top_k contacts ranked by relevance to pitch. Empty list if no key or candidates."""
    if not settings.openrouter_api_key or not candidates:
        return []

    contacts_text = "\n".join(
        f"{i + 1}. {c['name']} — {c.get('position', '')} at {c['company']}"
        f" (seniority: {c.get('seniority', 'unknown')}, "
        f"role: {', '.join(c.get('role_type', [])) or 'unknown'})"
        for i, c in enumerate(candidates)
    )

    prompt = (
        f"You are a B2B sales assistant. For this pitch:\n\n{pitch}\n\n"
        "Rank these contacts by their likelihood to be decision-makers or strong influencers. "
        'Return JSON: {"rankings": [{"index": 1, "score": 0.9, "reasoning": "..."}]}.\n\n'
        f"Contacts:\n{contacts_text}"
    )

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(
            f"{settings.openrouter_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
        )
    resp.raise_for_status()
    data = json.loads(resp.json()["choices"][0]["message"]["content"])

    ranked: list[RankedContact] = []
    for r in data.get("rankings", []):
        idx = int(r["index"]) - 1
        if 0 <= idx < len(candidates):
            c = candidates[idx]
            ranked.append(
                RankedContact(
                    page_id=c["page_id"],
                    name=c["name"],
                    company=c["company"],
                    position=c.get("position", ""),
                    score=float(r.get("score", 0.0)),
                    reasoning=str(r.get("reasoning", "")),
                    linkedin_url=c.get("linkedin_url", ""),
                )
            )

    return sorted(ranked, key=lambda x: x.score, reverse=True)[:top_k]
