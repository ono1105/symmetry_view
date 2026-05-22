from __future__ import annotations

from pathlib import Path

from crystal_viewer.source_kinds import SOURCE_KIND_CRYSTAL, normalize_source_kind
from crystal_viewer.viewer.operation_labels import operation_summaries


class ViewerSession:
    def __init__(self, json_path: Path, payload: dict) -> None:
        self.load(json_path, payload)

    def load(self, json_path: Path, payload: dict) -> None:
        self.json_path = json_path
        self.payload = payload
        self.render_data = payload["render_data"]
        self.atoms = self.render_data["atoms"]
        self.operations = self.render_data["operations"]
        self.operation_summary_items = operation_summaries(
            self.render_data,
            payload.get("atom_mappings"),
        )

    def replace_from(self, other: "ViewerSession") -> None:
        self.json_path = other.json_path
        self.payload = other.payload
        self.render_data = other.render_data
        self.atoms = other.atoms
        self.operations = other.operations
        self.operation_summary_items = other.operation_summary_items

    @property
    def source_kind(self) -> str:
        return normalize_source_kind(
            self.payload.get(
                "source_kind",
                self.render_data.get("metadata", {}).get("mode", SOURCE_KIND_CRYSTAL),
            )
        )
