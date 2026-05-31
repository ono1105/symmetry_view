import unittest
from unittest.mock import patch

from crystal_viewer.structure_analysis import analyze_cif


class StructureAnalysisTest(unittest.TestCase):
    def test_asymmetric_indices_are_derived_from_spglib_equivalent_atoms(self):
        result = analyze_cif("examples/cif/Halite.cif")

        self.assertEqual([atom.asymmetric_index for atom in result.structure.atoms], [0, 0, 0, 0, 1, 1, 1, 1])
        self.assertEqual([atom.generation_operation_index for atom in result.structure.atoms], [0, 144, 96, 48, 0, 144, 96, 48])
        self.assertEqual([(atom.index, atom.element) for atom in result.structure.asymmetric_atoms], [(0, "Na"), (1, "Cl")])

    def test_normal_cif_analysis_does_not_reparse_asymmetric_unit_loop(self):
        with patch(
            "crystal_viewer.structure_analysis.read_asymmetric_unit_sites",
            side_effect=AssertionError("read_asymmetric_unit_sites should not be called"),
        ):
            result = analyze_cif("examples/cif/Cadmoselite.cif")

        self.assertEqual([atom.asymmetric_index for atom in result.structure.atoms], [0, 0, 1, 1])
        self.assertEqual([atom.generation_operation_index for atom in result.structure.atoms], [0, 1, 0, 1])


if __name__ == "__main__":
    unittest.main()
