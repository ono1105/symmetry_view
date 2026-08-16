"""Every crystal class must still analyse to the same space group and cell.

These CIFs were the original example set: one real structure per crystal class.
They were retired from examples/ because large cells and unfamiliar minerals
make poor teaching material, but as a set they cover all 32 classes, which no
curated teaching set does.  Analysing them here turns dormant files into an
actual regression net over the CIF reader, spglib settings and the symmetry
summary — the paths a library upgrade is most likely to shift.

Two of the 32 classes are covered by teaching examples instead: Halite (m-3m)
and BaTiO3 (3m), which is why they stayed in examples/cif.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from crystal_viewer.structure_analysis import analyze_cif
from tests.support import FIXTURE_CIF_DIR


# file, space group number, Hermann-Mauguin symbol, crystal class, atoms in cell
FIXTURE_STRUCTURES: tuple[tuple[str, int, str, str, int], ...] = (
    ("Adamantane.cif", 114, "P-42_1c", "-42m", 52),
    ("AgCl.cif", 11, "P2_1/m", "2/m", 4),
    ("Antimony.cif", 166, "R-3m", "-3m", 6),
    ("Babefphite.cif", 1, "P1", "1", 64),
    ("Bromine.cif", 64, "Cmce", "mmm", 8),
    ("C12H14N4.cif", 43, "Fdd2", "mm2", 128),
    ("Cadmoselite.cif", 186, "P6_3mc", "6mm", 4),
    ("Cl H4 N O2.cif", 99, "P4mm", "4mm", 4),
    ("Cl2 H6 N2.cif", 205, "Pa-3", "m-3", 16),
    ("Edgarite.cif", 182, "P6_322", "622", 20),
    ("Gd I S.cif", 174, "P-6", "-6", 9),
    ("Ge Hf O4.cif", 88, "I4_1/a", "4/m", 24),
    ("H11 I N2 O6.cif", 148, "R-3", "-3", 27),
    ("Helium.cif", 194, "P6_3/mmc", "6/mmm", 2),
    ("Ho2Rh12As7.cif", 176, "P6_3/m", "6/m", 24),
    ("La6MgSi2S14.cif", 173, "P6_3", "6", 24),
    ("Manganese-beta.cif", 213, "P4_132", "432", 20),
    ("MgHPO3(H2O)6.cif", 146, "R3", "3", 36),
    ("N2 O4.cif", 199, "I2_13", "23", 36),
    ("NbP.cif", 141, "I4_1/amd", "4/mmm", 8),
    ("O9 V5.cif", 2, "P-1", "-1", 56),
    ("Pb(Al,Si)4O8.cif", 79, "I4", "4", 34),
    ("Pharmacosiderite.cif", 215, "P-43m", "-43m", 33),
    ("Qusongite.cif", 187, "P-6m2", "-6m2", 2),
    ("Ravatite.cif", 4, "P2_1", "2", 28),
    ("Retgersite.cif", 96, "P4_32_12", "422", 48),
    ("SiO2.cif", 82, "I-4", "-4", 24),
    ("Tellurium.cif", 154, "P3_221", "32", 3),
    ("Tenorite.cif", 9, "Cc", "m", 8),
    ("Tridymite.cif", 20, "C222_1", "222", 24),
)

# The classes the two retained teaching examples contribute.
EXAMPLE_CLASSES = {"m-3m": "examples/cif/Halite.cif", "3m": "examples/cif/BaTiO3.cif"}

CRYSTAL_CLASSES = frozenset({
    "1", "-1",
    "2", "m", "2/m",
    "222", "mm2", "mmm",
    "4", "-4", "4/m", "422", "4mm", "-42m", "4/mmm",
    "3", "-3", "32", "3m", "-3m",
    "6", "-6", "6/m", "622", "6mm", "-6m2", "6/mmm",
    "23", "m-3", "432", "-43m", "m-3m",
})


class FixtureCifCoverageTest(unittest.TestCase):
    def test_each_fixture_analyses_as_recorded(self):
        for name, number, symbol, point_group, atoms in FIXTURE_STRUCTURES:
            with self.subTest(name):
                result = analyze_cif(FIXTURE_CIF_DIR / name)
                self.assertEqual(result.space_group.number, number)
                self.assertEqual(result.space_group.international, symbol)
                self.assertEqual(result.space_group.point_group, point_group)
                self.assertEqual(len(result.structure.atoms), atoms)

    def test_the_table_lists_every_fixture_file(self):
        listed = {name for name, *_ in FIXTURE_STRUCTURES}
        on_disk = {path.name for path in FIXTURE_CIF_DIR.glob("*.cif")}
        self.assertEqual(listed, on_disk)

    def test_all_32_crystal_classes_stay_covered(self):
        covered = {point_group for _, _, _, point_group, _ in FIXTURE_STRUCTURES}
        covered |= set(EXAMPLE_CLASSES)
        self.assertEqual(covered, CRYSTAL_CLASSES)

    def test_the_classes_claimed_for_examples_come_from_examples(self):
        for point_group, path in EXAMPLE_CLASSES.items():
            with self.subTest(point_group):
                self.assertEqual(analyze_cif(Path(path)).space_group.point_group, point_group)


if __name__ == "__main__":
    unittest.main()
