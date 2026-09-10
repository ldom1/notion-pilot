# Notion Pilot — CRM marketing deck

Source of truth for the executive deck. **Copy lives in JSON; layout lives in Python.**

| File | What it is | Who edits it |
|---|---|---|
| `crm-deck-content.json` | Every word in the deck — headlines, support lines, table rows, speaker notes | Marketing |
| `brand-palette.json` | Colours, fonts, tagline, CTA | Marketing / brand |
| `../../scripts/marketing/generate_crm_deck.py` | Layout, geometry, shapes | Engineering |
| `../notion-pilot-crm-executive-deck.pptx` | **Generated output — never edit by hand** | nobody |
| `../notion-pilot-crm-deck-talk-track.md` | Speaker sheet: talk track, timings, objections | Marketing / sales |

## Rebuild after any copy change

```bash
uv run python scripts/marketing/generate_crm_deck.py
```

Edits made directly in PowerPoint are lost on the next rebuild. Change the JSON instead.

## Editing rules

- **Slide numbers are computed**, so you can add, remove or reorder slides in the JSON array without renumbering anything. Appendix slides (`"appendix": true`) stay unnumbered.
- Keep `kind` unchanged unless you also want a different layout — it selects which visual the slide is drawn with (`rows`, `cards3`, `schema`, `kpi`, `flow`, `capture`, `journey`, `compare`, `steps`, `cta`, `chips`).
- Row and list lengths are flexible; heights are computed to fill the slide. Very long strings will still wrap, so keep table cells under ~60 characters and headlines under ~60.
- `"hero": "First line|Second line"` on the title slide — the `|` is a deliberate line break, and the second half is set in brand purple.
- Bump `meta.version` when you ship a change. It prints in the footer of every slide, so sales can tell a stale deck at a glance.

## Before this deck leaves the building

1. **Fill the CTA.** The last slide carries a dashed placeholder — `‹ booking link or contact — fill in before sending ›`. Replace `cta_fill` in the JSON.
2. **Insert the three appendix screenshots** (A1 MCP output, A3 CRM board, A4 ERD). They are dashed placeholders today. The main path (slides 1–15) needs no screenshots.
3. **Get naming approval** for the Artelys slide (A3) if the deck goes to anyone outside the company.
4. **Read the "Never say" list** at the end of the talk track. The deck deliberately avoids data-residency guarantees, invented ROI numbers, and a Meetings database — all three are wrong, not merely cautious.

## Known constraints

- **Font.** The deck is set in Segoe UI, which ships with Windows and Office but is not on macOS or Google Slides — those will substitute and reflow the layout. If the audience is mixed, change `meta.font` to a font everyone has (Calibri, Aptos, Arial) and rebuild.
- **The brand mark is drawn from shapes**, not the SVG, because PowerPoint files cannot embed SVG through the generator. It matches `notion-pilot-promo/assets/logo.svg`; if the logo changes, update `add_logo()`.
- **No PDF export here** — no headless LibreOffice on the build machine. Export from PowerPoint.
- **Alt text is not set** on the diagrams. Add it in PowerPoint if the deck must pass an accessibility check, or ask engineering to bake it in.
