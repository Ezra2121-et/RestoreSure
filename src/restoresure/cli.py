"""Command-line interface for RestoreSure."""

import argparse
import shutil
import sys
import tomllib
from pathlib import Path

from restoresure import __version__
from restoresure.backup import BackupError, run_backup, run_verify, run_restore_drill


def check_config(path: Path) -> list[str]:
    """Return configuration errors. An empty jobs list is valid."""
    try:
        with path.open("rb") as file:
            config = tomllib.load(file)
    except FileNotFoundError:
        return [f"Configuration file not found: {path}"]
    except PermissionError:
        return [f"Permission denied reading configuration: {path}"]
    except tomllib.TOMLDecodeError as exc:
        return [f"Invalid TOML configuration: {exc}"]
    except OSError as exc:
        return [f"Cannot read configuration: {exc}"]

    errors = []

    if not isinstance(config.get("jobs"), list):
        return ["Configuration must contain a 'jobs' array."]

    seen_names = set()

    for index, job in enumerate(config["jobs"], start=1):
        prefix = f"Job {index}"

        if not isinstance(job, dict):
            errors.append(f"{prefix} must be a TOML table.")
            continue

        name = job.get("name")
        source = job.get("source")
        repository = job.get("repository")
        schedule = job.get("schedule")

        if not isinstance(name, str) or not name.strip():
            errors.append(f"{prefix}: 'name' must be a non-empty string.")
        elif name in seen_names:
            errors.append(f"{prefix}: duplicate job name '{name}'.")
        else:
            seen_names.add(name)

        if not isinstance(source, str) or not source.strip():
            errors.append(f"{prefix}: 'source' must be a non-empty string.")

        if not isinstance(repository, str) or not repository.strip():
            errors.append(f"{prefix}: 'repository' must be a non-empty string.")

        if schedule not in ("daily", "weekly"):
            errors.append(
                f"{prefix}: 'schedule' must be 'daily' or 'weekly'."
            )

    return errors


def run_doctor() -> int:
    """Report basic runtime dependencies without changing the system."""
    print("RestoreSure system check")
    print(f"Version: {__version__}")
    print(f"Python: {sys.version.split()[0]}")

    checks = {
        "Restic": shutil.which("restic"),
        "systemctl": shutil.which("systemctl"),
    }

    failed = False
    for name, executable in checks.items():
        if executable:
            print(f"[OK]   {name}: {executable}")
        else:
            print(f"[WARN] {name}: not found")
            failed = True

    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="restoresure",
        description="Linux backup assurance and recovery automation.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="check basic runtime dependencies")

    run_parser = subparsers.add_parser(
        "run", help="run a configured backup job"
    )
    run_parser.add_argument("job", help="configured job name")
    run_parser.add_argument(
        "--config", type=Path, default=Path("config/restoresure.toml"),
        help="configuration file path",
    )

    verify_parser = subparsers.add_parser(
        "verify", help="verify a configured backup repository"
    )
    verify_parser.add_argument("job", help="configured job name")
    verify_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/restoresure.toml"),
        help="configuration file path",
    )

    drill_parser = subparsers.add_parser(
        "drill", help="restore and compare a backup in temporary storage"
    )
    drill_parser.add_argument("job", help="configured job name")
    drill_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/restoresure.toml"),
        help="configuration file path",
    )

    config_parser = subparsers.add_parser(
        "config-check",
        help="validate a TOML configuration file",
    )
    config_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/restoresure.toml"),
        help="configuration file path",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "doctor":
        return run_doctor()

    if args.command == "run":
        try:
            return run_backup(args.config, args.job)
        except BackupError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.command == "verify":
        try:
            return run_verify(args.config, args.job)
        except BackupError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.command == "drill":
        try:
            return run_restore_drill(args.config, args.job)
        except BackupError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.command == "config-check":
        errors = check_config(args.config)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1

        print(f"Configuration is valid: {args.config}")
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
