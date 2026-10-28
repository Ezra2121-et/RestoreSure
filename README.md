# RestoreSure

RestoreSure is a Linux backup assurance and recovery automation agent.

It is designed to combine a persistent systemd service with a terminal CLI,
using an established backup engine and recording evidence of backup
verification and restore tests.

The project is in early development. Backup execution, scheduling, verification,
and service integration are not implemented yet.

## Development checks

From the project root:

```bash
PYTHONPATH=src python -m restoresure --version
PYTHONPATH=src python -m restoresure doctor
PYTHONPATH=src python -m restoresure config-check \
  --config config/restoresure.toml.example
python -m unittest discover -s tests -v
```

No backup jobs are run by these commands.
