import shutil
import subprocess
import unittest
from pathlib import Path


class JavaScriptAnimationPathTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_matches_python_golden_samples(self):
        project_root = Path(__file__).resolve().parents[1]
        subprocess.run(
            ["node", "--test", "tests/js/animation_path.test.mjs"],
            cwd=project_root,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
