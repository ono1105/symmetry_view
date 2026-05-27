import unittest

from crystal_viewer.viewer.operation_lookup import operation_by_index, selected_mapping


class OperationLookupTest(unittest.TestCase):
    def test_selected_mapping_does_not_reuse_stale_equal_length_data(self):
        first = {
            "mappings": [
                {"operation_index": 1, "entries": [{"source_atom": 0, "target_atom": 0}]}
            ]
        }
        second = {
            "mappings": [
                {"operation_index": 1, "entries": [{"source_atom": 0, "target_atom": 2}]}
            ]
        }

        self.assertEqual(selected_mapping(first, 1)["entries"][0]["target_atom"], 0)
        self.assertEqual(selected_mapping(second, 1)["entries"][0]["target_atom"], 2)

    def test_operation_by_index_does_not_reuse_stale_equal_length_data(self):
        first = [{"index": 1, "label": "first"}]
        second = [{"index": 1, "label": "second"}]

        self.assertEqual(operation_by_index(first, 1)["label"], "first")
        self.assertEqual(operation_by_index(second, 1)["label"], "second")


if __name__ == "__main__":
    unittest.main()
