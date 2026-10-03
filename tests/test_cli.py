import os
import subprocess
import sys
import tempfile
import unittest

_SRC_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


class CliTests(unittest.TestCase):
    def _run(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, "-m", "carmvp", *args],
            capture_output=True,
            text=True,
            cwd=_SRC_ROOT,
            input=input_text,
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

    def test_evaluate_missing_file_reports_friendly_error(self):
        result = self._run("evaluate", "--format", "json", "does-not-exist.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Could not read input", result.stderr)

    def test_evaluate_malformed_json_reports_friendly_error(self):
        result = self._run("evaluate", "--format", "json", "-", input_text="{not valid json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Could not parse json input", result.stderr)

    def test_evaluate_empty_html_reports_no_listings(self):
        result = self._run(
            "evaluate", "--format", "html", "-", input_text="<html><body>nothing</body></html>"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("No listings found", result.stderr)

    def test_evaluate_reads_json_file(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            fh.write('[{"title": "File car", "price": 5000}]')
            path = fh.name
        try:
            result = self._run("evaluate", "--format", "json", path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("File car", result.stdout)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
