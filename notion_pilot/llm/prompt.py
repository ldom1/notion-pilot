"""System prompts for OpenRouter → Notion enrichment."""

from notion_pilot.llm.source_hints import format_source_hint_for_prompt
from notion_pilot.models import IncomingMessage, NotionDatabaseProperties

_EXCLUDED_FIELDS = {"status"}


def _fields_spec() -> str:
    """Build the JSON key spec from NotionDatabaseProperties — single source of truth."""
    lines = []
    for py_name, field in NotionDatabaseProperties.model_fields.items():
        if py_name in _EXCLUDED_FIELDS:
            continue
        key = field.alias or py_name
        lines.append(f'  "{key}" — {field.description or ""}')
    return "\n".join(lines)


def build_openrouter_system_prompt(incoming: IncomingMessage) -> str:
    """Return a system prompt that instructs the LLM to produce a Notion row as JSON."""
    body = (incoming.body or "").strip()
    source_hint = format_source_hint_for_prompt(body)
    source_hint_block = f"\n\nSOURCE HINT: {source_hint}" if source_hint else ""

    return f"""\
You are a structured data extractor. Your sole job is to read a Telegram message and \
return a single JSON object — no prose, no markdown fences, no explanation — \
containing EXACTLY these keys (case-sensitive, matching Notion column names):

{_fields_spec()}

RULES:
- Output valid JSON only. No trailing commas. No comments.
- Use the exact key names above (e.g. "Name" not "name", "Type" not "type").
- "Label" MUST be a JSON array of 1–5 short tags (strings), never a single string.
- Use null only for "Link" and "Source" when unknown.
- Match the sender's language for "Name" and "Description" unless the linked content \
is clearly in another language.
- If the message body is empty (voice note pending, media-only), infer as much as \
possible from the media type and caption.
- Never hallucinate URLs. Only populate "Link" if a URL is explicitly present in the input.\
{source_hint_block}

INPUT CONTEXT:
  Sender      : {incoming.sender}
  Media type  : {incoming.media_type.value}
  Message body:
<message>
{body[:12000]}
</message>"""
