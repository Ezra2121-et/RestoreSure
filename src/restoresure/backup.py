"""Safe orchestration of configured Restic backup jobs."""

import os
import stat
import subprocess
import tomllib
from pathlib import Path


class BackupError(Exception):
    """Raised when a backup job cannot safely run."""


def load_job(config_path: Path, job_name: str) -> dict:
    try:
        with config_path.open("rb") as file:
            config = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise BackupError(f"Cannot load configuration: {exc}") from exc

    jobs = config.get("jobs")
    if not isinstance(jobs, list):
        raise BackupError("Configuration must contain a jobs array.")

    matches = [
        job for job in jobs
        if isinstance(job, dict) and job.get("name") == job_name
    ]

    if len(matches) != 1:
        raise BackupError(
            f"Expected exactly one job named '{job_name}', found {len(matches)}."
        )

    return matches[0]


def validate_job(job: dict) -> tuple[Path, Path, Path]:
    source_value = job.get("source")
    repository_value = job.get("repository")
    password_value = job.get("password_file")

    for key, value in (
        ("source", source_value),
        ("repository", repository_value),
        ("password_file", password_value),
    ):
        if not isinstance(value, str) or not value.strip():
            raise BackupError(f"Job requires a non-empty '{key}' path.")

    source = Path(source_value).expanduser().resolve()
    repository = Path(repository_value).expanduser().resolve()
    password_file = Path(password_value).expanduser().resolve()

    if not source.is_dir():
        raise BackupError(f"Source must be an existing directory: {source}")

    if not repository.is_dir():
        raise BackupError(
            f"Repository directory does not exist: {repository}. "
            "Initialize it separately before running a backup."
        )

    if source == repository or source in repository.parents:
        raise BackupError(
            "Repository must not be inside the source directory."
        )

    if repository in source.parents:
        raise BackupError(
            "Source must not be inside the repository directory."
        )

    if not password_file.is_file():
        raise BackupError("Password file does not exist or is not a regular file.")

    try:
        mode = stat.S_IMODE(password_file.stat().st_mode)
    except OSError as exc:
        raise BackupError(f"Cannot inspect password file: {exc}") from exc

    if mode & 0o077:
        raise BackupError(
            "Password file is accessible by group or others. "
            "Restrict it with: chmod 600 /path/to/password-file"
        )

    return source, repository, password_file


def run_backup(config_path: Path, job_name: str) -> int:
    job = load_job(config_path, job_name)
    source, repository, password_file = validate_job(job)

    env = os.environ.copy()
    env.pop("RESTIC_PASSWORD", None)
    env["RESTIC_PASSWORD_FILE"] = str(password_file)

    command = [
        "restic",
        "-r", str(repository),
        "backup",
        "--",
        str(source),
    ]

    print(f"Starting backup job: {job_name}")
    print(f"Source: {source}")
    print(f"Repository: {repository}")

    try:
        result = subprocess.run(
            command,
            env=env,
            text=True,
            check=False,
            timeout=3600,
        )
    except FileNotFoundError as exc:
        raise BackupError("Restic executable was not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise BackupError("Backup exceeded the one-hour time limit.") from exc
    except OSError as exc:
        raise BackupError(f"Could not start Restic: {exc}") from exc

    if result.returncode != 0:
        print(f"Backup failed with exit code {result.returncode}.")
        return result.returncode if result.returncode > 0 else 1

    print("Restic reported backup completion.")
    return 0


def run_verify(config_path: Path, job_name: str) -> int:
    """Verify all repository data for a configured backup job."""
    job = load_job(config_path, job_name)
    _, repository, password_file = validate_job(job)

    env = os.environ.copy()
    env.pop("RESTIC_PASSWORD", None)
    env["RESTIC_PASSWORD_FILE"] = str(password_file)

    command = [
        "restic",
        "-r", str(repository),
        "check",
        "--read-data",
    ]

    print(f"Verifying backup repository for job: {job_name}")
    print(f"Repository: {repository}")
    print("Checking repository data integrity; this may take time.")

    try:
        result = subprocess.run(
            command,
            env=env,
            text=True,
            check=False,
            timeout=3600,
        )
    except FileNotFoundError as exc:
        raise BackupError("Restic executable was not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise BackupError(
            "Repository verification exceeded the one-hour time limit."
        ) from exc
    except OSError as exc:
        raise BackupError(f"Could not start Restic: {exc}") from exc

    if result.returncode != 0:
        print(
            f"Repository verification failed with exit code "
            f"{result.returncode}."
        )
        return result.returncode if result.returncode > 0 else 1

    print("Repository verification completed successfully.")
    return 0


def _tree_manifest(root: Path) -> dict[str, tuple]:
    """Describe directory entries and hash regular-file contents."""
    import hashlib

    manifest = {}

    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()

        if path.is_symlink():
            manifest[relative] = ("symlink", os.readlink(path))
        elif path.is_dir():
            manifest[relative] = ("directory",)
        elif path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as file:
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(chunk)
            manifest[relative] = ("file", digest.hexdigest())
        else:
            manifest[relative] = ("unsupported",)

    return manifest


def run_restore_drill(config_path: Path, job_name: str) -> int:
    """Restore the latest snapshot to a temporary directory and compare it."""
    import tempfile

    job = load_job(config_path, job_name)
    source, repository, password_file = validate_job(job)

    env = os.environ.copy()
    env.pop("RESTIC_PASSWORD", None)
    env["RESTIC_PASSWORD_FILE"] = str(password_file)

    print(f"Starting recovery drill for job: {job_name}")
    print(f"Source: {source}")
    print(f"Repository: {repository}")

    try:
        with tempfile.TemporaryDirectory(prefix="restoresure-drill-") as temp:
            target = Path(temp)
            restored_source = target / source.relative_to(source.anchor)

            command = [
                "restic",
                "-r", str(repository),
                "restore", "latest",
                "--path", str(source),
                "--target", str(target),
            ]

            result = subprocess.run(
                command,
                env=env,
                text=True,
                check=False,
                timeout=3600,
            )

            if result.returncode != 0:
                print(
                    f"Recovery drill failed: Restic exited "
                    f"with code {result.returncode}."
                )
                return result.returncode if result.returncode > 0 else 1

            if not restored_source.is_dir():
                raise BackupError(
                    "Restic completed, but the expected source directory "
                    "was not found in the restored snapshot."
                )

            original_manifest = _tree_manifest(source)
            restored_manifest = _tree_manifest(restored_source)

            if original_manifest != restored_manifest:
                original_paths = set(original_manifest)
                restored_paths = set(restored_manifest)
                differences = []

                for path in sorted(original_paths | restored_paths):
                    if original_manifest.get(path) != restored_manifest.get(path):
                        differences.append(path)

                print("Recovery drill failed: restored content differs.")
                for path in differences[:10]:
                    print(f"  Mismatch: {path}")
                if len(differences) > 10:
                    print(f"  ... and {len(differences) - 10} more mismatches")
                return 1

            print("Recovery drill passed: directory structure and file contents match.")
            return 0

    except FileNotFoundError as exc:
        raise BackupError("Restic executable was not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise BackupError(
            "Recovery drill exceeded the one-hour time limit."
        ) from exc
    except OSError as exc:
        raise BackupError(f"Recovery drill could not complete: {exc}") from exc
