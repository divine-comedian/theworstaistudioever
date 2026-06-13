#!/usr/bin/env bash
# sync-catalogue.sh — inject the repo's catalogued style/composition rows into the
# live ui-ux-pro-max plugin CSVs, so the daily pipeline's step-3 search can surface them.
#
# The repo (seeds/catalogue/*.additions.csv) is the source of truth; the plugin CSV is a
# derived cache. This script is IDEMPOTENT: rows already present (matched by their unique
# name column) are skipped, so it is safe to re-run after a plugin update to re-inject
# everything that a version bump would otherwise have wiped.
#
# Usage: scripts/sync-catalogue.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$REPO_ROOT/scripts/sync_catalogue.py" "$REPO_ROOT"
