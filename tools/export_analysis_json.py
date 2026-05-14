from __future__ import annotations

import argparse
import json
from pathlib import Path

import _bootstrap  # noqa: F401

from crystal_viewer.atom_mapping import atom_mappings_from_analysis
from crystal_viewer.json_export import export_payload, write_export_json
from crystal_viewer.molecule_analysis import analyze_molecule_file
from crystal_viewer.render_data import render_data_from_analysis
from crystal_viewer.structure_analysis import analyze_cif


def main() -> int:
    parser = argparse.ArgumentParser(description="Export RenderData and AtomMapping as JSON.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--mode", choices=["crystal", "molecule"], required=True)
    parser.add_argument("--output", "-o", type=Path, default=None)
    parser.add_argument("--tolerance-cart", type=float, default=1e-2)
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args()

    if args.mode == "crystal":
        analysis = analyze_cif(args.path)
    else:
        analysis = analyze_molecule_file(args.path)

    render_data = render_data_from_analysis(analysis)
    atom_mappings = atom_mappings_from_analysis(analysis, tolerance_cart=args.tolerance_cart)

    if args.output is None:
        payload = export_payload(render_data, atom_mappings, source_kind=args.mode)
        print(json.dumps(payload, ensure_ascii=False, indent=args.indent))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_export_json(
            args.output,
            render_data,
            atom_mappings,
            source_kind=args.mode,
            indent=args.indent,
        )
        print(f"Wrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

