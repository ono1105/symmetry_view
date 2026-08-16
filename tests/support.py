"""Shared loading helpers for tests that read exported analysis JSON.

Exports live in two places.  ``exports/json/`` holds the bundled teaching
examples and is user-facing (the README calls it the shared JSON).
``tests/fixtures/json/`` holds exports of the retired crystal-class CIFs under
``tests/fixtures/cif/``, which are kept for coverage but are deliberately not
offered to users.  Tests should not care which side a structure is on, so look
in the fixture directory first and fall back to the examples.
"""

from __future__ import annotations

import json
from pathlib import Path


EXPORT_DIR = Path("exports/json")
FIXTURE_JSON_DIR = Path("tests/fixtures/json")
FIXTURE_CIF_DIR = Path("tests/fixtures/cif")


def export_path(slug: str) -> Path:
    """Path of the export named ``slug`` (without the .json suffix)."""
    for directory in (FIXTURE_JSON_DIR, EXPORT_DIR):
        candidate = directory / f"{slug}.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"no export named {slug}.json in {FIXTURE_JSON_DIR} or {EXPORT_DIR}. "
        "Run tools/regenerate_example_assets.py to rebuild them."
    )


def load_export(slug: str) -> dict:
    """The whole exported payload (render_data, atom_mapping, metadata)."""
    return json.loads(export_path(slug).read_text(encoding="utf-8"))


def load_render_data(slug: str) -> dict:
    """Just the render_data block, which is what the game modules consume."""
    payload = load_export(slug)
    return payload.get("render_data", payload)
