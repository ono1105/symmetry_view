from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from crystal_viewer.structure_analysis import load_structure_from_cif


R_LATTICE = """
_cell_length_a   4.000000
_cell_length_b   4.000000
_cell_length_c   4.000000
_cell_angle_alpha   89.843000
_cell_angle_beta    89.843000
_cell_angle_gamma   89.843000
"""


class RhombohedralCifFallbackTest(unittest.TestCase):
    def test_rhombohedral_empty_symmetry_loop_uses_warning_fallback(self) -> None:
        cif_text = f"""
data_batio3
_symmetry_Int_Tables_number   160
{R_LATTICE}
loop_
_symmetry_equiv_pos_as_xyz
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Ba1 Ba 0.000000 0.000000 0.000000
Ti1 Ti 0.500000 0.500000 0.500000
O1 O 0.500000 0.500000 0.000000
"""

        loaded = load_structure_from_cif(self.write_temp_cif(cif_text))

        self.assertEqual(len(loaded.structure), 5)
        self.assertEqual(loaded.structure.composition.reduced_formula, "BaTiO3")
        self.assertEqual(len(loaded.asymmetric_atoms or ()), 3)
        self.assertTrue(loaded.warnings)
        self.assertIn("space-group number 160", loaded.warnings[0])

    def test_normal_cif_does_not_enter_warning_fallback(self) -> None:
        cif_text = """
data_p1
_symmetry_Int_Tables_number   1
_cell_length_a   3.000000
_cell_length_b   4.000000
_cell_length_c   5.000000
_cell_angle_alpha   90.000000
_cell_angle_beta    90.000000
_cell_angle_gamma   90.000000
loop_
_symmetry_equiv_pos_as_xyz
'x, y, z'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Si1 Si 0.000000 0.000000 0.000000
"""

        loaded = load_structure_from_cif(self.write_temp_cif(cif_text))

        self.assertEqual(len(loaded.structure), 1)
        self.assertEqual(loaded.warnings, ())
        self.assertIsNone(loaded.asymmetric_atoms)

    def test_non_rhombohedral_empty_symmetry_loop_is_not_silently_repaired(self) -> None:
        cif_text = """
data_cubic_empty_loop
_symmetry_Int_Tables_number   221
_cell_length_a   4.000000
_cell_length_b   4.000000
_cell_length_c   4.000000
_cell_angle_alpha   90.000000
_cell_angle_beta    90.000000
_cell_angle_gamma   90.000000
loop_
_symmetry_equiv_pos_as_xyz
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Na1 Na 0.000000 0.000000 0.000000
"""

        with self.assertRaises(Exception):
            load_structure_from_cif(self.write_temp_cif(cif_text))

    def write_temp_cif(self, text: str) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".cif", encoding="utf-8", delete=False)
        with handle:
            handle.write(text)
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path


if __name__ == "__main__":
    unittest.main()
