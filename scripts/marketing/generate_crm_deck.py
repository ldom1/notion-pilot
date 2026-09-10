#!/usr/bin/env python3
"""Generate the Notion Pilot CRM executive marketing deck (13 slides + appendix).

Design layer: everything is drawn from native PowerPoint shapes (including the logo),
so the deck stays fully editable and resolution-independent. No table styles are used —
rows are shape-based cards, which gives full control over fills, spacing and borders.

All copy lives in docs/marketing/crm-deck-content.json — this module holds layout only,
so the marketing team can edit text without touching Python. Slide numbers are computed
from position, so slides can be added, removed or reordered freely.
"""

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "notion-pilot-crm-executive-deck.pptx"
PALETTE_PATH = ROOT / "docs" / "marketing" / "brand-palette.json"
CONTENT_PATH = ROOT / "docs" / "marketing" / "crm-deck-content.json"

CONTENT = json.loads(CONTENT_PATH.read_text())
META = CONTENT["meta"]
FONT = META["font"]

# ── Slide geometry (13.333 × 7.5 in). Fixed zones prevent overlap. ────────────
ML = Inches(0.65)
CW = Inches(13.333) - ML - Inches(0.65)
TOPBAR_H = Inches(0.10)
CHROME_TOP = Inches(0.30)
LOGO_SIZE = Inches(0.34)
ACCENT_TOP = Inches(0.80)
HERO_TOP = Inches(0.95)
HERO_H = Inches(1.15)
SUPPORT_TOP = Inches(2.18)
BODY_TOP = Inches(2.72)
BODY_H = Inches(4.06)  # ends 6.78
FOOTER_RULE = Inches(6.98)
FOOTER_TEXT = Inches(7.04)


def hex_rgb(value: str) -> RGBColor:
    value = value.lstrip("#")
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


C = {k: hex_rgb(v) for k, v in json.loads(PALETTE_PATH.read_text())["palette"].items()}
INK, MUTED = C["ink"], C["muted"]
PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT = C["primary"], C["primaryDark"], C["primaryLight"]
SURFACE, BORDER = C["surface"], C["border"]
PHASE1, PHASE2 = C["phaseFoundation"], C["phaseAcceleration"]
POSITIVE, NEGATIVE = C["positive"], C["negative"]
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


# ── primitives ───────────────────────────────────────────────────────────────
def shape(
    slide,
    kind,
    left,
    top,
    width,
    height,
    *,
    fill=None,
    line=None,
    line_w=1.0,
    radius=None,
    dashed=False,
    name=None,
):
    s = slide.shapes.add_shape(kind, left, top, width, height)
    if name:
        s.name = name
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(line_w)
        if dashed:
            s.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    if radius is not None and kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.shadow.inherit = False
    return s


def write(
    target,
    lines,
    *,
    size=14,
    bold=False,
    color=INK,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    spacing=0,
    margin=6,
):
    """Render lines into a shape or textbox. `lines` is a str or list of (text, opts)."""
    tf = target.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Pt(margin)
    tf.margin_top = tf.margin_bottom = Pt(2)
    items = [lines] if isinstance(lines, str) else lines
    for i, item in enumerate(items):
        text, opts = (item, {}) if isinstance(item, str) else item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = text
        p.font.size = Pt(opts.get("size", size))
        p.font.bold = opts.get("bold", bold)
        p.font.color.rgb = opts.get("color", color)
        p.font.name = FONT
        p.alignment = opts.get("align", align)
        p.space_after = Pt(opts.get("spacing", spacing))
    return target


def textbox(slide, left, top, width, height, lines, *, name=None, **kw):
    box = slide.shapes.add_textbox(left, top, width, height)
    if name:
        box.name = name
    return write(box, lines, **kw)


def card(slide, left, top, width, height, *, fill=WHITE, line=BORDER, radius=0.12):
    return shape(
        slide,
        MSO_SHAPE.ROUNDED_RECTANGLE,
        left,
        top,
        width,
        height,
        fill=fill,
        line=line,
        line_w=1.0,
        radius=radius,
    )


# ── brand mark, drawn from shapes (mirrors assets/logo.svg) ───────────────────
def add_logo(slide, left, top, size, *, wordmark=False):
    shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, left, top, size, size, fill=PRIMARY, radius=0.23)
    glyph_pt = size.inches * 72 * 0.43
    write(
        slide.shapes.add_textbox(left + int(size * 0.14), top, int(size * 0.60), size),
        "P",
        size=glyph_pt,
        bold=True,
        color=WHITE,
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
        margin=0,
    )
    dot = int(size * 0.133)
    shape(
        slide,
        MSO_SHAPE.OVAL,
        left + int(size * 0.617),
        top + int(size * 0.383),
        dot,
        dot,
        fill=PHASE2,
    )
    if wordmark:
        write(
            slide.shapes.add_textbox(left + size + int(size * 0.30), top, Inches(4.2), size),
            "Notion Pilot",
            size=size.inches * 72 * 0.46,
            bold=True,
            color=INK,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )


# ── slide chrome ─────────────────────────────────────────────────────────────
def add_chrome(slide, phase, phase_color, slide_no):
    shape(
        slide,
        MSO_SHAPE.RECTANGLE,
        0,
        0,
        Inches(13.333),
        TOPBAR_H,
        fill=phase_color,
        name="Phase rule",
    )
    add_logo(slide, ML, CHROME_TOP, LOGO_SIZE)
    if phase:
        textbox(
            slide,
            ML + LOGO_SIZE + Inches(0.14),
            CHROME_TOP + Inches(0.03),
            Inches(6.0),
            Inches(0.28),
            phase,
            size=10,
            bold=True,
            color=phase_color,
            margin=0,
        )
    shape(slide, MSO_SHAPE.RECTANGLE, ML, FOOTER_RULE, CW, Inches(0.01), fill=BORDER)
    textbox(
        slide,
        ML,
        FOOTER_TEXT,
        Inches(7.0),
        Inches(0.28),
        f"{META['footer']} · v{META['version']}",
        size=9,
        color=MUTED,
        margin=0,
        name="Footer",
    )
    if slide_no is not None:
        textbox(
            slide,
            ML + CW - Inches(1.2),
            FOOTER_TEXT,
            Inches(1.2),
            Inches(0.28),
            str(slide_no),
            size=9,
            color=MUTED,
            align=PP_ALIGN.RIGHT,
            margin=0,
        )


def add_hero(slide, message, support, *, size=32):
    shape(slide, MSO_SHAPE.RECTANGLE, ML, ACCENT_TOP, Inches(0.9), Inches(0.05), fill=PRIMARY)
    textbox(
        slide,
        ML,
        HERO_TOP,
        CW,
        HERO_H,
        message,
        size=size,
        bold=True,
        color=INK,
        margin=0,
        name="Hero",
    )
    if support:
        textbox(slide, ML, SUPPORT_TOP, CW, Inches(0.42), support, size=14, color=MUTED, margin=0)


# ── reusable body components ─────────────────────────────────────────────────
def add_rows(slide, rows, *, top=BODY_TOP, height=BODY_H, left=ML, width=CW, split=0.38, gap=0.07):
    """Header + data rows as shape cards — replaces PowerPoint table styles."""
    n = len(rows)
    row_h = (height.inches - gap * (n - 1)) / n
    lw, rw = int(width * split), width - int(width * split)
    y = top
    for i, (a, b) in enumerate(rows):
        h = Inches(row_h)
        if i == 0:
            shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, left, y, width, h, fill=PRIMARY, radius=0.1)
            write(
                slide.shapes.add_textbox(left, y, lw, h),
                a,
                size=11,
                bold=True,
                color=WHITE,
                anchor=MSO_ANCHOR.MIDDLE,
                margin=12,
            )
            write(
                slide.shapes.add_textbox(left + lw, y, rw, h),
                b,
                size=11,
                bold=True,
                color=WHITE,
                anchor=MSO_ANCHOR.MIDDLE,
                margin=12,
            )
        else:
            card(slide, left, y, width, h, fill=WHITE if i % 2 else SURFACE, radius=0.1)
            write(
                slide.shapes.add_textbox(left, y, lw, h),
                a,
                size=12.5,
                bold=True,
                color=PRIMARY_DARK,
                anchor=MSO_ANCHOR.MIDDLE,
                margin=12,
            )
            write(
                slide.shapes.add_textbox(left + lw, y, rw, h),
                b,
                size=12.5,
                color=INK,
                anchor=MSO_ANCHOR.MIDDLE,
                margin=12,
            )
        y += Inches(row_h + gap)


def add_callout(
    slide,
    text,
    left,
    top,
    width,
    height,
    *,
    fill=PRIMARY_LIGHT,
    border=PRIMARY,
    color=PRIMARY_DARK,
    size=13,
):
    s = shape(
        slide,
        MSO_SHAPE.ROUNDED_RECTANGLE,
        left,
        top,
        width,
        height,
        fill=fill,
        line=border,
        line_w=1.25,
        radius=0.14,
    )
    return write(
        s,
        text,
        size=size,
        bold=True,
        color=color,
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
        margin=12,
    )


def add_placeholder(slide, left, top, width, height, label):
    s = shape(
        slide,
        MSO_SHAPE.ROUNDED_RECTANGLE,
        left,
        top,
        width,
        height,
        fill=SURFACE,
        line=BORDER,
        line_w=1.5,
        radius=0.06,
        dashed=True,
    )
    write(
        s,
        [
            ("Screenshot to insert", {"size": 12, "bold": True, "color": MUTED}),
            (label, {"size": 11, "color": MUTED}),
        ],
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def add_chips(slide, items, *, left=ML, top=BODY_TOP, width=CW, height=BODY_H):
    gap = 0.1
    row_h = (height.inches - gap * (len(items) - 1)) / len(items)
    y = top
    for text in items:
        h = Inches(row_h)
        card(slide, left, y, width, h, fill=WHITE, radius=0.1)
        shape(
            slide,
            MSO_SHAPE.RECTANGLE,
            left + Inches(0.16),
            y + Inches(row_h / 2 - 0.06),
            Inches(0.11),
            Inches(0.11),
            fill=PRIMARY,
        )
        write(
            slide.shapes.add_textbox(left + Inches(0.42), y, width - Inches(0.6), h),
            text,
            size=13.5,
            color=INK,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )
        y += Inches(row_h + gap)


def add_three_cards(slide, cards, callout):
    gap = Inches(0.35)
    card_w = int((CW - gap * 2) / 3)
    card_h = Inches(3.15)
    left = ML
    for badge, title, desc in cards:
        card(slide, left, BODY_TOP, card_w, card_h, fill=SURFACE, radius=0.08)
        b = shape(
            slide,
            MSO_SHAPE.OVAL,
            left + Inches(0.34),
            BODY_TOP + Inches(0.34),
            Inches(0.62),
            Inches(0.62),
            fill=PRIMARY_LIGHT,
            line=PRIMARY,
        )
        write(
            b,
            badge,
            size=20,
            bold=True,
            color=PRIMARY_DARK,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )
        textbox(
            slide,
            left + Inches(0.34),
            BODY_TOP + Inches(1.16),
            card_w - Inches(0.68),
            Inches(0.5),
            title,
            size=21,
            bold=True,
            color=INK,
            margin=0,
        )
        textbox(
            slide,
            left + Inches(0.34),
            BODY_TOP + Inches(1.78),
            card_w - Inches(0.68),
            Inches(1.1),
            desc,
            size=14,
            color=MUTED,
            margin=0,
        )
        left += card_w + gap
    add_callout(
        slide,
        callout,
        ML,
        BODY_TOP + card_h + Inches(0.22),
        CW,
        Inches(0.6),
    )


def add_flow(slide, stages, *, top, height, highlight=1):
    """Horizontal stage flow with arrow connectors."""
    arrow_w = Inches(0.34)
    gap = Inches(0.12)
    box_w = int((CW - (arrow_w + gap * 2) * (len(stages) - 1)) / len(stages))
    x = ML
    for i, (title, desc) in enumerate(stages):
        on = i == highlight
        card(
            slide,
            x,
            top,
            box_w,
            height,
            fill=PRIMARY if on else SURFACE,
            line=PRIMARY if on else BORDER,
            radius=0.1,
        )
        write(
            slide.shapes.add_textbox(
                x + Inches(0.16), top + Inches(0.22), box_w - Inches(0.32), Inches(0.42)
            ),
            title,
            size=15,
            bold=True,
            color=WHITE if on else INK,
            align=PP_ALIGN.CENTER,
            margin=0,
        )
        write(
            slide.shapes.add_textbox(
                x + Inches(0.16), top + Inches(0.72), box_w - Inches(0.32), height - Inches(0.9)
            ),
            desc,
            size=12,
            color=PRIMARY_LIGHT if on else MUTED,
            align=PP_ALIGN.CENTER,
            margin=0,
        )
        if i < len(stages) - 1:
            shape(
                slide,
                MSO_SHAPE.RIGHT_ARROW,
                x + box_w + gap,
                top + int(height / 2) - Inches(0.11),
                arrow_w,
                Inches(0.22),
                fill=PRIMARY,
            )
        x += box_w + arrow_w + gap * 2


def add_chevrons(slide, labels, *, top, height, left=ML, width=CW, last_color=PHASE2):
    overlap = Inches(0.14)
    w = int((width + overlap * (len(labels) - 1)) / len(labels))
    x = left
    for i, label in enumerate(labels):
        last = i == len(labels) - 1
        s = shape(
            slide,
            MSO_SHAPE.CHEVRON,
            x,
            top,
            w,
            height,
            fill=last_color if last else PRIMARY_LIGHT,
            line=last_color if last else PRIMARY,
        )
        write(
            s,
            label,
            size=13,
            bold=True,
            color=WHITE if last else PRIMARY_DARK,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )
        x += w - overlap


def add_chat_mock(slide, left, top, width, height, turns, title, caption):
    """Stylised capture conversation — an illustration, not a screenshot."""
    card(slide, left, top, width, height, fill=SURFACE, radius=0.06)
    head = shape(
        slide,
        MSO_SHAPE.ROUNDED_RECTANGLE,
        left,
        top,
        width,
        Inches(0.42),
        fill=PRIMARY,
        radius=0.12,
    )
    write(
        head,
        title,
        size=11,
        bold=True,
        color=WHITE,
        anchor=MSO_ANCHOR.MIDDLE,
        margin=14,
    )
    y = top + Inches(0.58)
    bubble_w = int(width * 0.74)
    for who, text in turns:
        mine = who == "me"
        h = Inches(0.46 if len(text) < 44 else 0.66)
        bx = left + width - bubble_w - Inches(0.16) if mine else left + Inches(0.16)
        b = card(
            slide,
            bx,
            y,
            bubble_w,
            h,
            fill=PRIMARY_LIGHT if mine else WHITE,
            line=PRIMARY if mine else BORDER,
            radius=0.22,
        )
        write(b, text, size=11, color=INK if mine else MUTED, anchor=MSO_ANCHOR.MIDDLE, margin=10)
        y += h + Inches(0.12)
    textbox(
        slide,
        left,
        top + height + Inches(0.06),
        width,
        Inches(0.26),
        caption,
        size=9,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        margin=0,
    )


def add_compare(
    slide, left_title, left_items, right_title, right_items, *, top=BODY_TOP, height=BODY_H
):
    gap = Inches(0.4)
    col_w = int((CW - gap) / 2)
    for i, (title, items, accent, glyph) in enumerate(
        [(left_title, left_items, POSITIVE, "✓"), (right_title, right_items, NEGATIVE, "✕")]
    ):
        x = ML + (col_w + gap) * i
        card(slide, x, top, col_w, height, fill=WHITE, line=accent, radius=0.07)
        head = shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            top,
            col_w,
            Inches(0.56),
            fill=accent,
            radius=0.12,
        )
        write(
            head,
            f"{glyph}  {title}",
            size=14,
            bold=True,
            color=WHITE,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=16,
        )
        row_h = (height.inches - 0.72) / len(items)
        y = top + Inches(0.66)
        for text in items:
            write(
                slide.shapes.add_textbox(x + Inches(0.2), y, col_w - Inches(0.4), Inches(row_h)),
                f"{glyph}   {text}",
                size=13.5,
                color=INK,
                anchor=MSO_ANCHOR.MIDDLE,
                margin=0,
            )
            y += Inches(row_h)


def add_step_cards(slide, steps, *, top=BODY_TOP, height=Inches(2.78)):
    gap = Inches(0.35)
    card_w = int((CW - gap * 2) / 3)
    x = ML
    for num, title, desc, timing in steps:
        card(slide, x, top, card_w, height, fill=WHITE, radius=0.08)
        b = shape(
            slide,
            MSO_SHAPE.OVAL,
            x + Inches(0.3),
            top + Inches(0.3),
            Inches(0.66),
            Inches(0.66),
            fill=PRIMARY_LIGHT,
            line=PRIMARY,
        )
        write(
            b,
            num,
            size=24,
            bold=True,
            color=PRIMARY_DARK,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )
        textbox(
            slide,
            x + Inches(1.1),
            top + Inches(0.4),
            card_w - Inches(1.4),
            Inches(0.5),
            title,
            size=19,
            bold=True,
            color=INK,
            margin=0,
        )
        textbox(
            slide,
            x + Inches(0.3),
            top + Inches(1.16),
            card_w - Inches(0.6),
            Inches(1.0),
            desc,
            size=13.5,
            color=MUTED,
            margin=0,
        )
        badge = shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x + Inches(0.3),
            top + height - Inches(0.62),
            Inches(1.5),
            Inches(0.34),
            fill=PRIMARY,
            radius=0.2,
        )
        write(
            badge,
            timing,
            size=11,
            bold=True,
            color=WHITE,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )
        x += card_w + gap


# ── schema (entity-relationship) ─────────────────────────────────────────────
def connect(slide, x1, y1, x2, y2, *, color=PRIMARY, width=1.25, label=None):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = color
    c.line.width = Pt(width)
    if label:
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        textbox(
            slide,
            mx - Inches(0.85),
            my - Inches(0.28),
            Inches(1.7),
            Inches(0.24),
            label,
            size=9,
            color=MUTED,
            align=PP_ALIGN.CENTER,
            margin=0,
        )


def entity(slide, left, top, width, height, name, props, *, hub=False, badge=None):
    card(
        slide,
        left,
        top,
        width,
        height,
        fill=PRIMARY if hub else WHITE,
        line=PRIMARY if hub else BORDER,
        radius=0.09,
    )
    textbox(
        slide,
        left + Inches(0.22),
        top + Inches(0.18),
        width - Inches(0.44),
        Inches(0.42),
        name,
        size=17 if hub else 15,
        bold=True,
        color=WHITE if hub else PRIMARY_DARK,
        margin=0,
        name=f"Entity: {name}",
    )
    textbox(
        slide,
        left + Inches(0.22),
        top + Inches(0.66),
        width - Inches(0.44),
        height - Inches(0.8),
        props,
        size=11,
        color=PRIMARY_LIGHT if hub else MUTED,
        margin=0,
    )
    if badge:
        auto = badge == "auto"
        chip = shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            left + width - Inches(1.28),
            top + Inches(0.16),
            Inches(1.1),
            Inches(0.26),
            fill=PHASE2 if auto else RGBColor(0xEE, 0xF0, 0xF4),
            radius=0.3,
        )
        write(
            chip,
            "AUTOMATED" if auto else "MANUAL",
            size=7.5,
            bold=True,
            color=WHITE if auto else MUTED,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )


def add_schema(slide, spec):
    cw_, ch = Inches(2.85), Inches(1.25)
    hub_w, hub_h = Inches(3.5), Inches(1.45)
    lx, rx = ML, ML + CW - cw_
    y_top, y_bot = Inches(2.80), Inches(4.30)
    hub_x, hub_y = Inches((13.333 - 3.5) / 2), Inches(3.45)

    for i, (nm, props, rel, badge) in enumerate(spec["left"]):
        y = y_top if i == 0 else y_bot
        connect(
            slide,
            lx + cw_,
            y + ch // 2,
            hub_x,
            hub_y + (hub_h // 3 if i == 0 else hub_h * 2 // 3),
            label=rel,
        )
        entity(slide, lx, y, cw_, ch, nm, props, badge=badge)

    for i, (nm, props, rel, badge) in enumerate(spec["right"]):
        y = y_top if i == 0 else y_bot
        if i == 0:
            connect(slide, hub_x + hub_w, hub_y + hub_h // 2, rx, y + ch // 2, label=rel)
        else:
            connect(slide, rx + cw_ // 2, y_top + ch, rx + cw_ // 2, y, color=BORDER, width=1.0)
            textbox(
                slide,
                rx,
                y_top + ch + Inches(0.01),
                cw_,
                Inches(0.24),
                rel,
                size=9,
                color=MUTED,
                align=PP_ALIGN.CENTER,
                margin=0,
            )
        entity(slide, rx, y, cw_, ch, nm, props, badge=badge)

    entity(slide, hub_x, hub_y, hub_w, hub_h, *spec["hub"], hub=True, badge="auto")
    add_callout(slide, spec["callout"], ML, Inches(5.86), CW, Inches(0.62))


# ── call to action ───────────────────────────────────────────────────────────
def add_cta(slide, spec):
    gap = Inches(0.4)
    col_w = int((CW - gap) / 2)
    top, h = BODY_TOP, Inches(2.73)
    panels = [
        (spec["need_title"], spec["need"], PRIMARY),
        (spec["get_title"], spec["get"], PHASE2),
    ]
    for i, (title, items, accent) in enumerate(panels):
        x = ML + (col_w + gap) * i
        card(slide, x, top, col_w, h, fill=WHITE, line=accent, radius=0.07)
        band = shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x,
            top,
            col_w,
            Inches(0.52),
            fill=accent,
            radius=0.12,
            name=f"CTA panel: {title}",
        )
        write(
            band,
            title,
            size=13.5,
            bold=True,
            color=WHITE,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=16,
        )
        row_h = (h.inches - 0.66) / len(items)
        y = top + Inches(0.62)
        for text in items:
            shape(
                slide,
                MSO_SHAPE.OVAL,
                x + Inches(0.26),
                y + Inches(row_h / 2 - 0.05),
                Inches(0.1),
                Inches(0.1),
                fill=accent,
            )
            write(
                slide.shapes.add_textbox(x + Inches(0.52), y, col_w - Inches(0.76), Inches(row_h)),
                text,
                size=13,
                color=INK,
                anchor=MSO_ANCHOR.MIDDLE,
                margin=0,
            )
            y += Inches(row_h)

    band = shape(
        slide,
        MSO_SHAPE.ROUNDED_RECTANGLE,
        ML,
        BODY_TOP + Inches(2.95),
        CW,
        Inches(0.7),
        fill=PRIMARY,
        radius=0.14,
        name="CTA band",
    )
    write(
        band,
        spec["cta"],
        size=17,
        bold=True,
        color=WHITE,
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
        margin=12,
    )
    chip = shape(
        slide,
        MSO_SHAPE.ROUNDED_RECTANGLE,
        ML + CW // 2 - Inches(2.4),
        BODY_TOP + Inches(3.74),
        Inches(4.8),
        Inches(0.3),
        fill=SURFACE,
        line=MUTED,
        dashed=True,
        radius=0.2,
        name="CTA link — fill before sending",
    )
    write(
        chip,
        spec["cta_fill"],
        size=9.5,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
        margin=0,
    )


# ── slide builders ───────────────────────────────────────────────────────────
def add_notes(slide, purpose, text):
    slide.notes_slide.notes_text_frame.text = f"Purpose — {purpose}\n\n{text}"


def new_slide(prs, appendix=False):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = SURFACE if appendix else WHITE
    return slide


def slide_title(prs, spec):
    slide = new_slide(prs)
    shape(
        slide,
        MSO_SHAPE.RECTANGLE,
        0,
        0,
        Inches(13.333),
        Inches(0.14),
        fill=PRIMARY,
        name="Phase rule",
    )
    shape(
        slide,
        MSO_SHAPE.OVAL,
        Inches(9.6),
        Inches(-2.2),
        Inches(6.2),
        Inches(6.2),
        fill=SURFACE,
        name="Corner tint",
    )
    add_logo(slide, ML, Inches(1.15), Inches(0.92), wordmark=True)
    shape(slide, MSO_SHAPE.RECTANGLE, ML, Inches(2.52), Inches(1.1), Inches(0.06), fill=PRIMARY)
    head, _, tail = spec["hero"].partition("|")
    textbox(
        slide,
        ML,
        Inches(2.78),
        Inches(11.2),
        Inches(1.55),
        [(head.strip(), {}), (tail.strip(), {"color": PRIMARY})],
        size=40,
        bold=True,
        color=INK,
        margin=0,
        name="Hero",
    )
    textbox(
        slide,
        ML,
        Inches(4.34),
        Inches(9.6),
        Inches(0.6),
        spec["tagline"],
        size=15,
        color=MUTED,
        margin=0,
        name="Tagline",
    )
    pill_w = int((CW - Inches(0.7)) / 3)
    x = ML
    for i, (num, label) in enumerate(spec["pills"]):
        on = i == len(spec["pills"]) - 1
        card(
            slide,
            x,
            Inches(5.15),
            pill_w,
            Inches(0.86),
            fill=PRIMARY_LIGHT if on else WHITE,
            line=PRIMARY if on else BORDER,
            radius=0.16,
        )
        b = shape(
            slide,
            MSO_SHAPE.OVAL,
            x + Inches(0.24),
            Inches(5.37),
            Inches(0.42),
            Inches(0.42),
            fill=PRIMARY,
        )
        write(
            b,
            num,
            size=13,
            bold=True,
            color=WHITE,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )
        write(
            slide.shapes.add_textbox(
                x + Inches(0.82), Inches(5.15), pill_w - Inches(1.0), Inches(0.86)
            ),
            label,
            size=14,
            bold=True,
            color=PRIMARY_DARK,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )
        x += pill_w + Inches(0.35)
    shape(slide, MSO_SHAPE.RECTANGLE, ML, FOOTER_RULE, CW, Inches(0.01), fill=BORDER)
    textbox(
        slide,
        ML,
        FOOTER_TEXT,
        Inches(8.0),
        Inches(0.28),
        spec["footer"],
        size=9,
        color=MUTED,
        margin=0,
        name="Footer",
    )
    add_notes(slide, spec["purpose"], spec["notes"])


def body_kpi(slide, spec):
    add_rows(slide, spec["rows"], height=Inches(3.2))
    add_callout(slide, spec["callout"], ML, BODY_TOP + Inches(3.38), CW, Inches(0.62))


def body_flow(slide, spec):
    add_callout(slide, spec["quote"], ML, BODY_TOP, CW, Inches(0.72), size=14)
    add_flow(
        slide,
        spec["stages"],
        top=BODY_TOP + Inches(1.02),
        height=Inches(1.85),
        highlight=spec["highlight"],
    )
    textbox(
        slide,
        ML,
        BODY_TOP + Inches(3.12),
        CW,
        Inches(0.4),
        spec["caption"],
        size=12,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        margin=0,
    )


def body_capture(slide, spec):
    col_w = Inches(6.5)
    add_rows(slide, spec["rows"], width=col_w, split=spec["split"], height=Inches(3.3))
    add_chat_mock(
        slide,
        ML + col_w + Inches(0.5),
        BODY_TOP,
        CW - col_w - Inches(0.5),
        Inches(3.5),
        spec["chat"],
        spec["chat_title"],
        spec["chat_caption"],
    )


def body_journey(slide, spec):
    add_chevrons(slide, spec["chevrons"], top=BODY_TOP, height=Inches(0.9))
    gap = Inches(0.4)
    col_w = int((CW - gap) / 2)
    col_top, col_h = BODY_TOP + Inches(1.12), Inches(2.05)

    card(slide, ML, col_top, col_w, col_h, fill=SURFACE, radius=0.08)
    textbox(
        slide,
        ML + Inches(0.24),
        col_top + Inches(0.16),
        col_w - Inches(0.48),
        Inches(0.3),
        spec["input_title"],
        size=10,
        bold=True,
        color=MUTED,
        margin=0,
    )
    b = card(
        slide,
        ML + Inches(0.24),
        col_top + Inches(0.58),
        col_w - Inches(0.48),
        Inches(0.72),
        fill=PRIMARY_LIGHT,
        line=PRIMARY,
        radius=0.2,
    )
    write(
        b,
        spec["input_quote"],
        size=13,
        bold=True,
        color=PRIMARY_DARK,
        anchor=MSO_ANCHOR.MIDDLE,
        margin=12,
    )
    textbox(
        slide,
        ML + Inches(0.24),
        col_top + Inches(1.44),
        col_w - Inches(0.48),
        Inches(0.4),
        spec["input_caption"],
        size=11.5,
        color=MUTED,
        margin=0,
    )

    x2 = ML + col_w + gap
    card(slide, x2, col_top, col_w, col_h, fill=WHITE, line=PHASE2, radius=0.08)
    textbox(
        slide,
        x2 + Inches(0.24),
        col_top + Inches(0.16),
        col_w - Inches(0.48),
        Inches(0.3),
        spec["output_title"],
        size=10,
        bold=True,
        color=PHASE2,
        margin=0,
    )
    y = col_top + Inches(0.56)
    for k, v in spec["output"]:
        write(
            slide.shapes.add_textbox(x2 + Inches(0.24), y, Inches(1.1), Inches(0.34)),
            k,
            size=11,
            bold=True,
            color=PRIMARY_DARK,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )
        write(
            slide.shapes.add_textbox(x2 + Inches(1.34), y, col_w - Inches(1.6), Inches(0.34)),
            v,
            size=11.5,
            color=INK,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )
        y += Inches(0.36)

    strip_top = col_top + col_h + Inches(0.22)
    for i, (label, color) in enumerate(zip(spec["outcomes"], (PHASE2, NEGATIVE))):
        s = shape(
            slide,
            MSO_SHAPE.ROUNDED_RECTANGLE,
            ML + (Inches(1.9) + Inches(0.2)) * i,
            strip_top,
            Inches(1.9),
            Inches(0.5),
            fill=color,
            radius=0.2,
        )
        write(
            s,
            label,
            size=12,
            bold=True,
            color=WHITE,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            margin=0,
        )
    textbox(
        slide,
        ML + Inches(4.3),
        strip_top,
        CW - Inches(4.3),
        Inches(0.5),
        spec["outcome_note"],
        size=12.5,
        color=INK,
        anchor=MSO_ANCHOR.MIDDLE,
        margin=0,
    )


def body_steps(slide, spec):
    add_step_cards(slide, spec["steps"])
    add_callout(
        slide,
        spec["callout"],
        ML,
        BODY_TOP + Inches(2.98),
        CW,
        Inches(0.7),
        fill=PRIMARY,
        border=PRIMARY,
        color=WHITE,
        size=15,
    )


def body_chips(slide, spec):
    label = spec.get("placeholder")
    if label:
        split = Inches(6.4)
        add_chips(slide, spec["chips"], width=split)
        add_placeholder(
            slide, ML + split + Inches(0.5), BODY_TOP, CW - split - Inches(0.5), BODY_H, label
        )
    else:
        add_chips(slide, spec["chips"])


BODIES = {
    "rows": lambda s, spec: add_rows(s, spec["rows"], split=spec["split"]),
    "cards3": lambda s, spec: add_three_cards(s, spec["cards"], spec["callout"]),
    "schema": add_schema,
    "kpi": body_kpi,
    "flow": body_flow,
    "capture": body_capture,
    "journey": body_journey,
    "compare": lambda s, spec: add_compare(
        s, spec["is_title"], spec["is"], spec["isnot_title"], spec["isnot"]
    ),
    "steps": body_steps,
    "cta": add_cta,
    "chips": body_chips,
}
ACCENTS = {"phase1": PHASE1, "phase2": PHASE2, "muted": MUTED}


def main():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    cp = prs.core_properties
    cp.title = META["docTitle"]
    cp.author = META["docAuthor"]
    cp.subject = META["docSubject"]
    cp.keywords = META["docKeywords"]
    cp.comments = f"Generated from {CONTENT_PATH.name} — edit copy there, not in the PPTX."
    cp.category = "Marketing"

    number = 0
    for spec in CONTENT["slides"]:
        if spec["kind"] == "title":
            slide_title(prs, spec)
            number += 1
            continue
        appendix = spec.get("appendix", False)
        if not appendix:
            number += 1
        slide = new_slide(prs, appendix=appendix)
        add_chrome(slide, spec["phase"], ACCENTS[spec["accent"]], None if appendix else number)
        add_hero(slide, spec["hero"], spec["support"], size=26 if appendix else 32)
        BODIES[spec["kind"]](slide, spec)
        add_notes(slide, spec["purpose"], spec["notes"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"Saved: {OUT} ({len(CONTENT['slides'])} slides)")


if __name__ == "__main__":
    main()
