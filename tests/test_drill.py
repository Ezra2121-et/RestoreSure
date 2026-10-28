import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from restoresure.backup import run_restore_drill


class RestoreDrillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

        self.source = self.root / "source"
        self.repository = self.root / "repository"
        self.password_file = self.root / "password"
        self.config = self.root / "restoresure.toml"

        self.source.mkdir()
        self.repository.mkdir()
        (self.source / "example.txt").write_text("original content\n")
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

    def simulate_restore(self, command, **kwargs):
        target = Path(command[command.index("--target") + 1])
        restored_source = target / str(self.source).lstrip("/")
        restored_source.mkdir(parents=True)
        (restored_source / "example.txt").write_text("original content\n")
        return Mock(returncode=0)

    @patch("restoresure.backup.subprocess.run")
    def test_matching_restore_passes(self, mock_run):
        mock_run.side_effect = self.simulate_restore

        result = run_restore_drill(self.config, "documents")

        self.assertEqual(result, 0)

    @patch("restoresure.backup.subprocess.run")
    def test_mismatched_restore_fails(self, mock_run):
        def simulate_mismatch(command, **kwargs):
            target = Path(command[command.index("--target") + 1])
            restored_source = target / str(self.source).lstrip("/")
            restored_source.mkdir(parents=True)
            (restored_source / "example.txt").write_text("wrong content\n")
            return Mock(returncode=0)

        mock_run.side_effect = simulate_mismatch

        result = run_restore_drill(self.config, "documents")

        self.assertEqual(result, 1)

    @patch("restoresure.backup.subprocess.run")
    def test_restore_is_limited_to_configured_source_path(self, mock_run):
        mock_run.side_effect = self.simulate_restore

        result = run_restore_drill(self.config, "documents")

        self.assertEqual(result, 0)
        command = mock_run.call_args.args[0]
        self.assertIn("--path", command)
        self.assertIn(str(self.source), command)
        self.assertEqual(command[command.index("--path") + 1], str(self.source))


    @patch("restoresure.backup.subprocess.run")
    def test_restic_failure_fails_drill(self, mock_run):
        mock_run.return_value = Mock(returncode=1)

        result = run_restore_drill(self.config, "documents")

        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
