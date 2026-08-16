"""The shipped examples must still be what the generator table says they are.

tools/generate_example_structures.py writes examples/cif and examples/molecules
from published space groups, lattice constants and Wyckoff positions.  Running
its verification against the files in the tree catches a hand-edit, a lost file,
and — the reason the check exists — a pymatgen or spglib update that changes how
a setting is interpreted, which would silently turn a teaching example into a
different structure.
"""

from __future__ import annotations

import unittest

from tools.generate_example_structures import (
    CRYSTALS,
    DEFAULT_CIF_DIR,
    DEFAULT_MOLECULE_DIR,
    MOLECULES,
    PROTECTED,
    verify_crystal,
    verify_molecule,
)


class GeneratedExamplesTest(unittest.TestCase):
    def test_generated_crystals_reanalyse_as_specified(self):
        for spec in CRYSTALS:
            with self.subTest(spec.stem):
                verify_crystal(spec, DEFAULT_CIF_DIR / f"{spec.stem}.cif")

    def test_generated_molecules_reanalyse_as_specified(self):
        for spec in MOLECULES:
            with self.subTest(spec.stem):
                verify_molecule(spec, DEFAULT_MOLECULE_DIR / f"{spec.stem}.xyz")

    def test_hand_authored_examples_are_not_generated(self):
        # Halite and BaTiO3 carry test snapshots and the empty-symmetry-loop
        # fallback sample; regenerating them would quietly drop that coverage.
        generated = {spec.stem for spec in CRYSTALS}
        self.assertEqual(generated & PROTECTED, set())
        for stem in PROTECTED:
            self.assertTrue((DEFAULT_CIF_DIR / f"{stem}.cif").exists())


if __name__ == "__main__":
    unittest.main()
