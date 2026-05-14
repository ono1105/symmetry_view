from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from crystal_viewer.atom_mapping import atom_mappings_from_analysis
from crystal_viewer.molecule_analysis import analyze_molecule_file
from crystal_viewer.structure_analysis import analyze_cif


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect atom mappings for crystal or molecule symmetry operations.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--mode", choices=["crystal", "molecule"], required=True)
    parser.add_argument("--operation", type=int, default=None)
    parser.add_argument("--tolerance-cart", type=float, default=1e-2)
    args = parser.parse_args()

    if args.mode == "crystal":
        result = analyze_cif(args.path)
    else:
        result = analyze_molecule_file(args.path)

    mapping_set = atom_mappings_from_analysis(result, tolerance_cart=args.tolerance_cart)

    print("=== AtomMapping ===")
    print(f"mode: {mapping_set.mode}")
    print(f"operations: {len(mapping_set.mappings)}")
    print(f"complete: {mapping_set.is_complete}")
    print(f"incomplete operations: {mapping_set.incomplete_operation_indices}")

    mappings = mapping_set.mappings
    if args.operation is not None:
        mappings = tuple(mapping for mapping in mappings if mapping.operation_index == args.operation)

    print("\n=== Operations ===")
    for mapping in mappings[:12]:
        print(
            f"Operation {mapping.operation_index}: {mapping.operation_kind}, "
            f"complete={mapping.is_complete}, max_distance={mapping.max_distance:.3e}"
        )
        pairs = ", ".join(
            f"{entry.source_atom}->{entry.target_atom}" for entry in mapping.entries[:16]
        )
        suffix = " ..." if len(mapping.entries) > 16 else ""
        print(f"  {pairs}{suffix}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
