from __future__ import annotations

import numpy as np
from pymatgen.core import Element


ELEMENT_COLORS = {
    "H": "#e8edf2",
    "He": "#9ed9d8",
    "Li": "#8ea7d8",
    "Be": "#8fbf87",
    "B": "#d59a7b",
    "C": "#7f8790",
    "N": "#6f95d8",
    "O": "#d66a61",
    "F": "#7fbf9b",
    "Ne": "#8fc7d7",
    "Na": "#b89ad8",
    "Mg": "#9dbf75",
    "Al": "#b6a6a0",
    "Si": "#d0aa7a",
    "P": "#d29b55",
    "S": "#d8c36a",
    "Cl": "#83b77a",
    "Ar": "#8ebfd0",
    "K": "#a98bd0",
    "Ca": "#92bb78",
    "Sc": "#e6e6e6",
    "Ti": "#9aa7b3",
    "V": "#8fa2b8",
    "Cr": "#8e9fc5",
    "Mn": "#a88bc2",
    "Fe": "#c77b58",
    "Co": "#c78392",
    "Ni": "#78b985",
    "Cu": "#b98555",
    "Zn": "#9198bf",
    "Ga": "#b9918b",
    "Ge": "#7fa0a0",
    "As": "#aa86c7",
    "Se": "#d19a52",
    "Br": "#a96258",
    "Kr": "#74b3c4",
    "Rb": "#9978be",
    "Sr": "#81b879",
    "Y": "#8fc7c7",
    "Zr": "#86b9bd",
    "Nb": "#77aeb8",
    "Mo": "#6fa6a6",
    "Tc": "#3b9e9e",
    "Ru": "#5b9696",
    "Rh": "#5a8d98",
    "Pd": "#91a8bd",
    "Ag": "#b8bdc5",
    "Cd": "#cdb584",
    "In": "#ad8580",
    "Sn": "#7d9999",
    "Sb": "#9d7ab5",
    "Te": "#c78b55",
    "I": "#8f6cae",
    "Xe": "#6fa7b7",
    "Cs": "#8569aa",
    "Ba": "#79ae73",
    "La": "#86bfd4",
    "Ce": "#c9c48b",
    "Pr": "#b5c18a",
    "Nd": "#9fc18a",
    "Sm": "#87bd93",
    "Eu": "#73b89d",
    "Gd": "#68b5a6",
    "Tb": "#5db0aa",
    "Dy": "#58aaa6",
    "Ho": "#52a796",
    "Er": "#52a681",
    "Tm": "#5ca36e",
    "Yb": "#6aa062",
    "Lu": "#789c5d",
    "Hf": "#79acc9",
    "Ta": "#6fa0c8",
    "W": "#5f94bd",
    "Re": "#6388aa",
    "Os": "#657c9c",
    "Ir": "#61718f",
    "Pt": "#b8b8c8",
    "Au": "#d0b45f",
    "Hg": "#aeb0c0",
    "Tl": "#a97770",
    "Pb": "#7c8088",
    "Bi": "#9b73ae",
    "Po": "#aa7a52",
    "At": "#8e7068",
    "Rn": "#6f9bad",
    "Fr": "#420066",
    "Ra": "#007d00",
    "Ac": "#70abfa",
    "Th": "#00baff",
    "Pa": "#00a1ff",
    "U": "#008fff",
    "Np": "#0080ff",
    "Pu": "#006bff",
    "Am": "#545cf2",
    "Cm": "#785ce3",
    "Bk": "#8a4fe3",
    "Cf": "#a136d4",
    "Es": "#b31fd4",
    "Fm": "#b31fba",
    "Md": "#b30da6",
    "No": "#bd0d87",
    "Lr": "#c70066",
}

DEFAULT_ATOM_COLOR = "#9aa5b1"
_ELEMENT_RADIUS_CACHE: dict[int, float] = {}


def element_radius_angstrom(atomic_number: int) -> float:
    atomic_number = int(atomic_number)
    cached = _ELEMENT_RADIUS_CACHE.get(atomic_number)
    if cached is not None:
        return cached
    try:
        element = Element.from_Z(atomic_number)
        radius = element.atomic_radius or element.atomic_radius_calculated
        value = float(radius) if radius is not None else 1.0
    except Exception:
        value = 1.0
    value = max(value, 0.15)
    _ELEMENT_RADIUS_CACHE[atomic_number] = value
    return value


def atom_radius(atomic_number: int, scene_span_value: float) -> float:
    del scene_span_value
    return element_radius_angstrom(atomic_number)


def display_atom_radius(atom: dict, render_data: dict) -> float:
    radius = element_radius_angstrom(int(atom["atomic_number"]))
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        return radius
    scale, minimum_radius = display_radius_scale(render_data)
    return max(radius * scale, minimum_radius)


def display_radius_scale(render_data: dict) -> tuple[float, float]:
    cached = render_data.get("_display_radius_scale")
    if cached is not None:
        return cached

    atoms = render_data.get("atoms", [])
    if not atoms:
        result = (1.0, 0.0)
        render_data["_display_radius_scale"] = result
        return result
    max_radius = max(
        element_radius_angstrom(int(item["atomic_number"]))
        for item in atoms
    )
    unit_cell = render_data.get("unit_cell")
    if unit_cell is None:
        result = (1.0, 0.0)
        render_data["_display_radius_scale"] = result
        return result
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    lengths = np.linalg.norm(lattice, axis=1)
    shortest = float(np.min(lengths)) if len(lengths) else 0.0
    if shortest <= 1e-9 or max_radius <= 1e-9:
        result = (1.0, 0.0)
        render_data["_display_radius_scale"] = result
        return result

    max_display_radius = shortest * 0.12
    scale = min(1.0, max_display_radius / max_radius)
    minimum_radius = shortest * 0.012
    result = (scale, minimum_radius)
    render_data["_display_radius_scale"] = result
    return result


def atom_color(
    atom: dict,
    *,
    element_colors: dict | None = None,
    atom_colors: dict | None = None,
) -> str:
    atom_index = str(atom.get("index", ""))
    if atom_colors and atom_index in atom_colors:
        color = normalize_hex_color(atom_colors[atom_index])
        if color is not None:
            return color
    element = str(atom.get("element", ""))
    if element_colors and element in element_colors:
        color = normalize_hex_color(element_colors[element])
        if color is not None:
            return color
    return ELEMENT_COLORS.get(element, DEFAULT_ATOM_COLOR)


def normalize_hex_color(value) -> str | None:
    text = str(value).strip()
    if len(text) == 7 and text.startswith("#"):
        digits = text[1:]
    elif len(text) == 6:
        digits = text
    else:
        return None
    if all(char in "0123456789abcdefABCDEF" for char in digits):
        return "#" + digits.lower()
    return None


def color_to_rgb(color: str) -> tuple[float, float, float]:
    normalized = normalize_hex_color(color) or DEFAULT_ATOM_COLOR
    return (
        int(normalized[1:3], 16) / 255.0,
        int(normalized[3:5], 16) / 255.0,
        int(normalized[5:7], 16) / 255.0,
    )
