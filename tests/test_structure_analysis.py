import unittest
from unittest.mock import patch

from crystal_viewer.structure_analysis import analyze_cif
from tests.support import FIXTURE_CIF_DIR


class StructureAnalysisTest(unittest.TestCase):
    def test_asymmetric_indices_are_derived_from_spglib_equivalent_atoms(self):
        result = analyze_cif("examples/cif/Halite.cif")

        self.assertEqual([atom.asymmetric_index for atom in result.structure.atoms], [0, 0, 0, 0, 1, 1, 1, 1])
        self.assertEqual([atom.generation_operation_index for atom in result.structure.atoms], [0, 144, 96, 48, 0, 144, 96, 48])
        self.assertEqual([(atom.index, atom.element) for atom in result.structure.asymmetric_atoms], [(0, "Na"), (1, "Cl")])

    def test_asymmetric_unit_comes_from_spglib_not_from_the_cif_site_loop(self):
        # Cd sits on a special position (3m., site symmetry of order 6), so six
        # space-group operations map the representative atom onto the same
        # target and "which one generated it" has no unique answer. The values
        # below are the lowest matching index, which is stable across spglib
        # releases; picking the nearest match made a 1e-16 rounding difference
        # decide the winner.
        #
        # This also stands in for the older guard that a normal CIF is not
        # re-parsed for its asymmetric unit: the read_asymmetric_unit_sites()
        # path it patched was deleted once spglib's equivalent_atoms became the
        # only source, and structure_analysis no longer imports CifParser at all.
        result = analyze_cif(FIXTURE_CIF_DIR / "Cadmoselite.cif")

        self.assertEqual([atom.asymmetric_index for atom in result.structure.atoms], [0, 0, 1, 1])
        self.assertEqual([atom.generation_operation_index for atom in result.structure.atoms], [0, 1, 0, 1])


if __name__ == "__main__":
    unittest.main()
