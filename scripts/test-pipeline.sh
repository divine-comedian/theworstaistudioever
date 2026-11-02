#!/usr/bin/env bash
# Dry-run the daily pipeline against test seeds into a sandbox subtree.
# Does NOT commit. Does NOT touch real state. Safe to run repeatedly.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
PIPELINE_ENGINE="${PIPELINE_ENGINE:-$(cat pipelines/engine)}"
SANDBOX="_test/daily"
rm -rf "$SANDBOX"
mkdir -p "$SANDBOX/seeds" "$SANDBOX/state/runs" "$SANDBOX/site/entries"
cp seeds/companies_test.json "$SANDBOX/seeds/companies.json"
cp seeds/subjects_test.json "$SANDBOX/seeds/subjects.json"
echo '[]' > "$SANDBOX/state/history.json"
cp site/styles.css "$SANDBOX/site/styles.css"
cp site/404.html "$SANDBOX/site/404.html"
cp site/CNAME "$SANDBOX/site/CNAME"
cp site/favicon.png "$SANDBOX/site/favicon.png"
cp site/logo.png "$SANDBOX/site/logo.png"
# Pipeline Step 8.1 invokes `scripts/validate-entry.sh` and Step 4 invokes
# `scripts/gen-image.sh`; the agent runs with cwd=$SANDBOX, so the scripts must
# be reachable at that relative path. gen-image.sh resolves its repo root from
# its own location, so its daily-cap counter lands in $SANDBOX/state/runs.
cp -r scripts "$SANDBOX/scripts"
cp -r pipelines "$SANDBOX/pipelines"
cp CLAUDE.md "$SANDBOX/CLAUDE.md"

LOG="$SANDBOX/run.log"

# Build a test prompt by replacing relative paths inside pipeline.md
# (The pipeline already uses repo-root-relative paths; we just `cd` into the sandbox)
cp pipeline.md "$SANDBOX/pipeline.md"

echo "=== dry run start ==="
if ! python3 scripts/run-pipeline-agent.py --engine "$PIPELINE_ENGINE" --workspace "$SANDBOX" \
      2>&1 | tee "$LOG" >&2; then
  echo "DRY RUN FAILED — see $LOG"
  exit 1
fi

# Validate whatever entry got produced
ENTRIES=$(ls "$SANDBOX/site/entries" 2>/dev/null)
NEW_SLUG="${ENTRIES%%$'\n'*}"
if [[ -z "$NEW_SLUG" ]]; then
  echo "DRY RUN FAILED — no entry created"
  exit 1
fi

if ! python3 scripts/build-entry-metadata.py "$SANDBOX/site" "$NEW_SLUG"; then
  echo "DRY RUN FAILED — sharing metadata generation rejected $NEW_SLUG"
  exit 1
fi

if ! ./scripts/validate-entry.sh "$SANDBOX/site" "$NEW_SLUG"; then
  echo "DRY RUN FAILED — validation rejected $NEW_SLUG"
  exit 1
fi

echo ""
echo "=== dry run complete ==="
echo "Output: $SANDBOX/site/entries/$NEW_SLUG/"
echo "Preview:"
echo "  python3 -m http.server 4173 --bind 127.0.0.1 --directory $SANDBOX/site"
echo "  Forward port 4173 from your workstation, then visit http://127.0.0.1:4173/entries/$NEW_SLUG/"
