"""URL domain → platform label for prompts and heuristic enrichment."""

_SOURCE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("instagram.com", "Instagram"),
    ("linkedin.com", "LinkedIn"),
    ("twitter.com", "Twitter / X"),
    ("x.com", "Twitter / X"),
    ("youtube.com", "YouTube"),
    ("youtu.be", "YouTube"),
    ("github.com", "GitHub"),
    ("reddit.com", "Reddit"),
    ("medium.com", "Medium"),
    ("substack.com", "Substack"),
    ("tiktok.com", "TikTok"),
    ("open.spotify.com", "Spotify"),
    ("arxiv.org", "arXiv"),
    ("notion.so", "Notion"),
    ("figma.com", "Figma"),
)


def infer_source_label(body: str) -> str | None:
    """Return a platform label if ``body`` contains a known URL host, else ``None``."""
    lowered = body.lower()
    for domain, label in _SOURCE_PATTERNS:
        if domain in lowered:
            return label
    return None


def format_source_hint_for_prompt(body: str) -> str:
    """One-line hint for the LLM when a known domain appears in the message."""
    label = infer_source_label(body)
    if label:
        return f'The message contains a {label} URL — set "source" to "{label}".'
    return ""
