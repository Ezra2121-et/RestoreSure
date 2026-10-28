import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from restoresure.backup import (
    BackupError,
    load_job,
    validate_job,
    run_backup,
)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.source = self.root / "source"
        self.repository = self.root / "repository"
        self.password_file = self.root / "password"

        self.source.mkdir()
        self.repository.mkdir()
        self.password_file.write_text("test-password\n")
        self.password_file.chmod(0o600)

        self.config = self.root / "restoresure.toml"
        self.config.write_text(
            f'[[jobs]]\n'
            f'name = "documents"\n'
            f'source = "{self.source}"\n'
            f'repository = "{self.repository}"\n'
            f'password_file = "{self.password_file}"\n'
            f'schedule = "daily"\n'
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_load_job_finds_configured_job(self):
        job = load_job(self.config, "documents")
        self.assertEqual(job["name"], "documents")

    def test_validate_job_accepts_safe_paths(self):
        source, repository, password = validate_job(
            load_job(self.config, "documents")
        )
        self.assertEqual(source, self.source.resolve())
        self.assertEqual(repository, self.repository.resolve())
        self.assertEqual(password, self.password_file.resolve())

    def test_rejects_repository_inside_source(self):
        nested_repository = self.source / "repository"
        nested_repository.mkdir()

        job = load_job(self.config, "documents")
        job["repository"] = str(nested_repository)

        with self.assertRaises(BackupError):
            validate_job(job)

    def test_rejects_insecure_password_file_permissions(self):
        self.password_file.chmod(0o644)

        with self.assertRaises(BackupError):
            validate_job(load_job(self.config, "documents"))

    @patch("restoresure.backup.subprocess.run")
    def test_successful_backup_returns_zero(self, mock_run):
        mock_run.return_value = Mock(returncode=0)

        result = run_backup(self.config, "documents")

        self.assertEqual(result, 0)
        mock_run.assert_called_once()

        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][0], "restic")
        self.assertIn("backup", args[0])
        self.assertEqual(
            kwargs["env"]["RESTIC_PASSWORD_FILE"],
            str(self.password_file.resolve()),
        )
        self.assertNotIn("RESTIC_PASSWORD", kwargs["env"])

    @patch("restoresure.backup.subprocess.run")
    def test_failed_backup_returns_nonzero(self, mock_run):
        mock_run.return_value = Mock(returncode=1)

        result = run_backup(self.config, "documents")

        self.assertEqual(result, 1)

    @patch("restoresure.backup.subprocess.run")
    def test_missing_restic_is_reported(self, mock_run):
        mock_run.side_effect = FileNotFoundError

        with self.assertRaises(BackupError):
            run_backup(self.config, "documents")


if __name__ == "__main__":
    unittest.main()
