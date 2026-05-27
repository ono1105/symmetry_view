from __future__ import annotations

import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401

from crystal_viewer.export_pipeline import default_json_output_path, export_analysis_to_json
from crystal_viewer.source_kinds import SOURCE_KIND_CRYSTAL, SOURCE_KIND_MOLECULE


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CIF_DIR = PROJECT_ROOT / "examples/cif"
DEFAULT_MOLECULE_DIR = PROJECT_ROOT / "examples/molecules"
DEFAULT_JSON_DIR = PROJECT_ROOT / "exports/json"
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "examples/example_catalog.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate example JSON exports and the browser example catalog."
    )
    parser.add_argument("--cif-dir", type=Path, default=DEFAULT_CIF_DIR)
    parser.add_argument("--molecule-dir", type=Path, default=DEFAULT_MOLECULE_DIR)
    parser.add_argument("--json-dir", type=Path, default=DEFAULT_JSON_DIR)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--tolerance-cart", type=float, default=1e-2)
    parser.add_argument("--indent", type=int, default=2)
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete top-level JSON files in --json-dir before regeneration.",
    )
    args = parser.parse_args()

    json_dir = args.json_dir
    json_dir.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for path in json_dir.glob("*.json"):
            path.unlink()

    catalog = {
        SOURCE_KIND_CRYSTAL: regenerate_kind(
            sorted(args.cif_dir.glob("*.cif")),
            SOURCE_KIND_CRYSTAL,
            json_dir,
            tolerance_cart=args.tolerance_cart,
            indent=args.indent,
        ),
        SOURCE_KIND_MOLECULE: regenerate_kind(
            sorted(args.molecule_dir.glob("*.xyz")),
            SOURCE_KIND_MOLECULE,
            json_dir,
            tolerance_cart=args.tolerance_cart,
            indent=args.indent,
        ),
    }
    args.catalog.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=args.indent) + "\n",
        encoding="utf-8",
    )
    print(
        f"Regenerated {len(catalog[SOURCE_KIND_CRYSTAL])} crystal and "
        f"{len(catalog[SOURCE_KIND_MOLECULE])} molecule examples."
    )
    return 0


def regenerate_kind(
    paths: list[Path],
    kind: str,
    json_dir: Path,
    *,
    tolerance_cart: float,
    indent: int,
) -> list[dict]:
    items = []
    for source_path in paths:
        source_relative = source_path.resolve().relative_to(PROJECT_ROOT)
        output_path = default_json_output_path(source_relative, json_dir)
        export_analysis_to_json(
            source_relative,
            mode=kind,
            output_path=output_path,
            tolerance_cart=tolerance_cart,
            indent=indent,
        )
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        metadata = payload["render_data"]["metadata"]
        item = {
            "kind": kind,
            "name": source_path.stem,
            "path": str(source_relative),
            "formula": str(metadata.get("formula") or ""),
            "symmetry": catalog_symmetry_label(kind, str(metadata.get("symmetry_label") or "")),
            "point_group": str(metadata.get("point_group_label") or ""),
        }
        items.append(item)
        print(f"{kind}\t{source_relative}\t{output_path.relative_to(PROJECT_ROOT)}")
    return items


def catalog_symmetry_label(kind: str, label: str) -> str:
    if kind != SOURCE_KIND_CRYSTAL:
        return label
    number, _, symbol = label.partition(" ")
    if number.isdigit() and symbol:
        return f"No. {number} {symbol}"
    return label


if __name__ == "__main__":
    raise SystemExit(main())
