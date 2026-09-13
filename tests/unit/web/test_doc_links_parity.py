# tests/unit/web/test_doc_links_parity.py
import re
from pathlib import Path

from notion_pilot.shared.doc_links import DOC_GROUPS, SOURCES_LEDE

PANEL = Path(__file__).resolve().parents[3] / "web/frontend/src/features/docs/SourcesPanel.tsx"


def test_cockpit_sources_panel_mirrors_doc_links():
    source = PANEL.read_text()
    in_panel = set(re.findall(r'url: "(https://[^"]+)"', source))
    assert in_panel == {link.url for group in DOC_GROUPS for link in group.links}
    assert SOURCES_LEDE in source
