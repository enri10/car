import os
import subprocess
import sys
import unittest

_SRC_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


class CliTests(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "carmvp", *args],
            capture_output=True,
            text=True,
            cwd=_SRC_ROOT,
        )

    def test_demo_runs_and_ranks_listings(self):
        result = self._run("demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("#1", result.stdout)
        self.assertIn("#6", result.stdout)  # 3 JSON + 3 HTML demo listings

    def test_evaluate_requires_format(self):
        result = self._run("evaluate")
        self.assertNotEqual(result.returncode, 0)

    def test_help(self):
        result = self._run("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("demo", result.stdout)
        self.assertIn("evaluate", result.stdout)


if __name__ == "__main__":
    unittest.main()
