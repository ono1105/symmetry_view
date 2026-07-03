from __future__ import annotations

from pathlib import Path

from ..source_kinds import source_kind_ui_config_json


_HTML_TEMPLATE = Path(__file__).with_name("browser_ui.html").read_text(encoding="utf-8")
HTML = _HTML_TEMPLATE.replace("__STRUCTURE_KIND_CONFIG__", source_kind_ui_config_json())
