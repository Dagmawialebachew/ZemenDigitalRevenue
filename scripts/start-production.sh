#!/usr/bin/env sh
set -eu
# Render exposes the public service port as PORT. Keep APP_PORT portable for
# local Docker and other hosts while always honoring the platform-provided port.
APP_PORT="${PORT:-${APP_PORT:-8000}}"
export APP_PORT

# Running a file under scripts/ makes Python use that directory as sys.path[0].
# Add the repository root explicitly so backend/, database/, bot/, and workers/
# remain importable regardless of the platform's launch working directory.
PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONPATH

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python scripts/migrate.py
fi
if [ "${RUN_PREFLIGHT:-true}" = "true" ]; then
  python scripts/preflight.py
fi
exec python main.py
