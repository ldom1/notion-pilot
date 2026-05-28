"""Notion URL and ID utilities."""


def page_id_from_url(value: str) -> str:
    """Accept a raw UUID or a Notion URL and return a hyphenated UUID."""
    # Strip query params and fragments
    value = value.split("?")[0].split("#")[0]
    # Extract the last path segment
    segment = value.rstrip("/").rsplit("/", 1)[-1]
    # If segment contains dashes, it's either a slug-uuid or already formatted.
    # Try to extract the UUID part (last 32 char hex or hyphenated UUID).
    if "-" in segment:
        # Check if it's already a hyphenated UUID (8-4-4-4-12 format)
        parts = segment.split("-")
        if len(parts) == 5 and all(len(p) in (8, 4, 12) for p in parts):  # noqa: PLR2004
            return segment  # Already hyphenated
        # Otherwise, extract the raw UUID from the end (e.g., "My-Page-550e8400e29b41d4...")
        raw = parts[-1]
    else:
        raw = segment

    # If it's 32 chars (raw UUID), hyphenate it
    if len(raw) == 32:  # noqa: PLR2004
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return raw
