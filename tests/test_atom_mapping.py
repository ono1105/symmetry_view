import unittest

from crystal_viewer.atom_mapping import atom_mappings_from_analysis
from crystal_viewer.structure_analysis import analyze_cif


class AtomMappingTest(unittest.TestCase):
    def test_crystal_mapping_groups_candidates_without_changing_results(self):
        result = analyze_cif("examples/cif/Halite.cif")

        mappings = atom_mappings_from_analysis(result)
        identity = mappings.mappings[0]
        face_translation = mappings.mappings[48]

        self.assertTrue(mappings.is_complete)
        self.assertEqual(identity.atom_to_atom, tuple(range(8)))
        self.assertEqual(face_translation.atom_to_atom, (3, 2, 1, 0, 7, 6, 5, 4))
        self.assertAlmostEqual(face_translation.max_distance, 0.0, places=8)


if __name__ == "__main__":
    unittest.main()
