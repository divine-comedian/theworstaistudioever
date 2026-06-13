#!/usr/bin/env bash
# shoot-site.sh — render a URL with a real browser and capture it for design cataloguing.
#
# Usage:
#   scripts/shoot-site.sh <url> <slug> [--fold]
#
#   <url>     the page to capture (include https://)
#   <slug>    kebab-case id; output goes to docs/design-catalogue/<slug>.png
#   --fold    ALSO capture an above-the-fold-only shot at docs/design-catalogue/<slug>-fold.png
#             (use when the full page is too tall to read clearly in one image)
#
# Renders with Chromium via Playwright's built-in screenshot command. Full-page by default.
set -euo pipefail

URL="${1:-}"
SLUG="${2:-}"
FOLD="${3:-}"

if [[ -z "$URL" || -z "$SLUG" ]]; then
  echo "usage: scripts/shoot-site.sh <url> <slug> [--fold]" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/docs/design-catalogue"
mkdir -p "$OUT_DIR"

VIEWPORT="1440,900"
WAIT_MS="2500"
PW="npx --yes playwright@1.60.0"

echo "shooting (full-page): $URL -> $OUT_DIR/$SLUG.png"
$PW screenshot --full-page \
  --viewport-size="$VIEWPORT" \
  --wait-for-timeout="$WAIT_MS" \
  "$URL" "$OUT_DIR/$SLUG.png"

if [[ "$FOLD" == "--fold" ]]; then
  echo "shooting (above-the-fold): $URL -> $OUT_DIR/$SLUG-fold.png"
  $PW screenshot \
    --viewport-size="$VIEWPORT" \
    --wait-for-timeout="$WAIT_MS" \
    "$URL" "$OUT_DIR/$SLUG-fold.png"
fi

echo "done."
