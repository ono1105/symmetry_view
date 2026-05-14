from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from crystal_viewer.molecule_analysis import analyze_molecule_file
from crystal_viewer.render_data import render_data_from_crystal, render_data_from_molecule
from crystal_viewer.structure_analysis import analyze_cif


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect common RenderData from crystal or molecule analysis.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--mode", choices=["crystal", "molecule"], required=True)
    args = parser.parse_args()

    if args.mode == "crystal":
        data = render_data_from_crystal(analyze_cif(args.path))
    else:
        data = render_data_from_molecule(analyze_molecule_file(args.path))

    print("=== RenderData ===")
    print(f"mode: {data.metadata.mode}")
    print(f"source: {data.metadata.source_file}")
    print(f"formula: {data.metadata.formula}")
    print(f"symmetry: {data.metadata.symmetry_label}")
    print(f"atoms: {len(data.atoms)}")
    print(f"operations: {len(data.operations)}")
    print(f"axes: {len(data.axes)}")
    print(f"planes: {len(data.planes)}")
    print(f"centers: {len(data.centers)}")
    print(f"unit cell: {data.unit_cell is not None}")
    print(f"bounds: {data.bounds_min} -> {data.bounds_max}")

    if data.axes:
        axis = data.axes[0]
        print(f"first axis: {axis.label}, point={axis.point_cart}, direction={axis.direction_cart}")
    if data.planes:
        plane = data.planes[0]
        print(f"first plane: {plane.label}, point={plane.point_cart}, normal={plane.normal_cart}")
    if data.centers:
        center = data.centers[0]
        print(f"first center: {center.label}, point={center.point_cart}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
