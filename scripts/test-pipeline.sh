#!/usr/bin/env bash
# Dry-run the daily pipeline against test seeds into a sandbox subtree.
# Does NOT commit. Does NOT touch real state. Safe to run repeatedly.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

SANDBOX="_test"
rm -rf "$SANDBOX"
mkdir -p "$SANDBOX/seeds" "$SANDBOX/state/runs" "$SANDBOX/site/entries"
cp seeds/companies_test.json "$SANDBOX/seeds/companies.json"
cp seeds/subjects_test.json "$SANDBOX/seeds/subjects.json"
echo '[]' > "$SANDBOX/state/history.json"
cp site/styles.css "$SANDBOX/site/styles.css"
cp site/404.html "$SANDBOX/site/404.html"
cp site/CNAME "$SANDBOX/site/CNAME"

LOG="$SANDBOX/run.log"

# Build a test prompt by replacing relative paths inside pipeline.md
# (The pipeline already uses repo-root-relative paths; we just `cd` into the sandbox)
cd "$SANDBOX"
cp ../pipeline.md ./pipeline.md

echo "=== dry run start ==="
if ! claude -p "$(cat pipeline.md)" \
      --allowed-tools "Read,Write,Edit,Glob,Grep,Bash(jq:*),Bash(node:*),Bash(ls:*),Bash(cat:*),Bash(mkdir:*),Skill" \
      --max-turns 80 \
      2>&1 | tee "../$LOG" >&2; then
  echo "DRY RUN FAILED — see $LOG"
  exit 1
fi

cd ..

# Validate whatever entry got produced
NEW_SLUG=$(ls "$SANDBOX/site/entries" 2>/dev/null | head -1)
if [[ -z "$NEW_SLUG" ]]; then
  echo "DRY RUN FAILED — no entry created"
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
echo "  cd $SANDBOX/site && python3 -m http.server 4173"
echo "  open http://localhost:4173/entries/$NEW_SLUG/"
