import tempfile
import unittest
from pathlib import Path

from restoresure.cli import check_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)

    def write_config(self, content):
        path = self.directory / "test.toml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_empty_jobs_list_is_valid(self):
        path = self.write_config("jobs = []\n")
        self.assertEqual(check_config(path), [])

    def test_valid_job_is_accepted(self):
        path = self.write_config(
            '[[jobs]]\n'
            'name = "documents"\n'
            'source = "/tmp/source"\n'
            'repository = "/tmp/repository"\n'
            'schedule = "daily"\n'
        )
        self.assertEqual(check_config(path), [])

    def test_missing_jobs_is_rejected(self):
        path = self.write_config('name = "example"\n')
        self.assertTrue(check_config(path))

    def test_invalid_schedule_is_rejected(self):
        path = self.write_config(
            '[[jobs]]\n'
            'name = "documents"\n'
            'source = "/tmp/source"\n'
            'repository = "/tmp/repository"\n'
            'schedule = "hourly"\n'
        )
        errors = check_config(path)
        self.assertTrue(any("schedule" in error for error in errors))

    def test_duplicate_job_names_are_rejected(self):
        path = self.write_config(
            '[[jobs]]\n'
            'name = "documents"\n'
            'source = "/tmp/a"\n'
            'repository = "/tmp/repo"\n'
            'schedule = "daily"\n'
            '\n'
            '[[jobs]]\n'
            'name = "documents"\n'
            'source = "/tmp/b"\n'
            'repository = "/tmp/repo"\n'
            'schedule = "weekly"\n'
        )
        errors = check_config(path)
        self.assertTrue(any("duplicate job name" in error for error in errors))

    def test_invalid_toml_is_rejected(self):
        path = self.write_config("[[jobs]\n")
        errors = check_config(path)
        self.assertTrue(any("Invalid TOML" in error for error in errors))

    def test_missing_file_is_reported(self):
        errors = check_config(self.directory / "missing.toml")
        self.assertTrue(any("not found" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
