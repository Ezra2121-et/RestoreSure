import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from restoresure.backup import BackupError, run_verify


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.source = self.root / "source"
        self.repository = self.root / "repository"
        self.password_file = self.root / "password"
        self.config = self.root / "restoresure.toml"

        self.source.mkdir()
        self.repository.mkdir()
        self.password_file.write_text("test-password\n")
        self.password_file.chmod(0o600)

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

    @patch("restoresure.backup.subprocess.run")
    def test_successful_verification_returns_zero(self, mock_run):
        mock_run.return_value = Mock(returncode=0)

        result = run_verify(self.config, "documents")

        self.assertEqual(result, 0)
        args, kwargs = mock_run.call_args
        self.assertEqual(
            args[0],
            [
                "restic",
                "-r", str(self.repository.resolve()),
                "check",
                "--read-data",
            ],
        )
        self.assertEqual(
            kwargs["env"]["RESTIC_PASSWORD_FILE"],
            str(self.password_file.resolve()),
        )
        self.assertNotIn("RESTIC_PASSWORD", kwargs["env"])

    @patch("restoresure.backup.subprocess.run")
    def test_failed_verification_returns_nonzero(self, mock_run):
        mock_run.return_value = Mock(returncode=1)

        result = run_verify(self.config, "documents")

        self.assertEqual(result, 1)

    @patch("restoresure.backup.subprocess.run")
    def test_missing_restic_is_reported(self, mock_run):
        mock_run.side_effect = FileNotFoundError

        with self.assertRaises(BackupError):
            run_verify(self.config, "documents")


if __name__ == "__main__":
    unittest.main()
