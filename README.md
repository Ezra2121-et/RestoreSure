# RestoreSure

RestoreSure is a Linux backup assurance and recovery CLI built around
[Restic](https://restic.net/). It runs configured backup jobs, checks
repository integrity, and performs recovery drills to compare restored files
against their current source.

The goal is to make backups more trustworthy by testing whether data can
actually be recovered, not just whether a backup command completed.

## Features

- Run named backup jobs using Restic.
- Verify repository integrity, including reading stored data.
- Restore the latest applicable snapshot to temporary storage and compare
  directory structure and file contents.
- Validate TOML configuration files.
- Check basic runtime dependencies.
- Run automated tests for configuration, backup, verification, and recovery
  behavior.

## Requirements

- Linux
- Python 3.11 or later
- [Restic](https://restic.net/)
- `uv` for the development workflow used below

## Setup

Clone the repository, then install it in the project environment:

```bash
uv sync
```

Copy the example configuration:

```bash
cp config/restoresure.toml.example config/restoresure.toml
```

Edit `config/restoresure.toml` to configure your backup job. The local
configuration is ignored by Git because it can contain machine-specific paths.

Example:

```toml
[[jobs]]
name = "documents"
source = "/home/your-user/Documents"
repository = "/path/to/restic-repository"
password_file = "/path/to/restic-password"
schedule = "daily"
```

Before running a job:

- The source must be an existing directory.
- The Restic repository directory must already exist and be initialized.
- The password file must exist and have permissions restricted from group
  and other users. Use `chmod 600 /path/to/restic-password`.
- Keep the repository outside the source directory.

Initialize a new repository separately with Restic before configuring it in
RestoreSure. Protect your repository password and keep a separate copy of
important credentials.

## CLI commands

Run commands from the project root.

Check the installation and dependencies:

```bash
uv run restoresure doctor
```

Validate a configuration file without running a backup:

```bash
uv run restoresure config-check \
  --config config/restoresure.toml
```

Run a named backup job:

```bash
uv run restoresure run documents \
  --config config/restoresure.toml
```

Verify repository integrity:

```bash
uv run restoresure verify documents \
  --config config/restoresure.toml
```

Perform a recovery drill:

```bash
uv run restoresure drill documents \
  --config config/restoresure.toml
```

The recovery drill restores the latest applicable snapshot into a temporary
directory, compares the restored directory structure and file contents with
the configured source, and removes the temporary restore directory when it
finishes.

A recovery drill compares against the source as it exists now. If the source
has changed since the last backup, a mismatch can indicate that the backup is
out of date rather than that the repository is corrupt.

## Development and tests

Run the automated test suite:

```bash
uv run python -m unittest discover -s tests -v
```

The tests cover configuration validation, backup behavior, repository
verification, and recovery-drill outcomes.

## Current scope

Implemented: CLI commands for backup execution, repository verification,
recovery drills, configuration validation, and basic dependency checks.

Not yet implemented: automatic scheduling through systemd, persistent
backup and recovery evidence reports, and a long-running background service.
The `schedule` field is configuration metadata at this stage; it does not
schedule jobs by itself.
