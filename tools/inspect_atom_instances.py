from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:
    from tools import _bootstrap  # noqa: F401

from crystal_viewer.viewer.atom_instances import element_instance_batches, element_instance_index


DEFAULT_DISPLAY_MODES = ("source", "expanded_quarter", "expanded_half", "expanded_1_0")


def inspect_display_mode(render_data: dict, display_mode: str) -> None:
    batches = element_instance_batches(render_data, display_mode=display_mode)
    instance_index = element_instance_index(batches)
    total = sum(len(batch.items) for batch in batches)
    primary = sum(int(batch.primary_mask.sum()) for batch in batches)

    print(f"=== {display_mode} ===")
    print(f"instances: {total}")
    print(f"unique keys: {len(instance_index)}")
    print(f"primary images: {primary}")
    print(f"element batches: {len(batches)}")
    for batch in batches:
        print(
            f"  {batch.element}: instances={len(batch.items)}, "
            f"primary={int(batch.primary_mask.sum())}, atomic_number={batch.atomic_number}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect display atom instance counts and element batches for exported viewer JSON."
    )
    parser.add_argument("json_path", type=Path)
    parser.add_argument(
        "--display-mode",
        action="append",
        help="Display mode to inspect. May be passed multiple times.",
    )
    args = parser.parse_args()

    payload = json.loads(args.json_path.read_text(encoding="utf-8"))
    render_data = payload["render_data"]
    modes = tuple(args.display_mode or DEFAULT_DISPLAY_MODES)

    metadata = render_data.get("metadata", {})
    print(f"source: {metadata.get('source_file', args.json_path)}")
    print(f"formula: {metadata.get('formula', '')}")
    print(f"symmetry: {metadata.get('symmetry_label', '')}")
    print(f"atoms: {len(render_data.get('atoms', []))}")
    print()

    for index, mode in enumerate(modes):
        if index:
            print()
        inspect_display_mode(render_data, mode)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
