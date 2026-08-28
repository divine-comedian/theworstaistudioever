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

# Browser preflight. Playwright's own "Executable doesn't exist" error helpfully
# prints `npx playwright install` — which the 2026-08-28 daily run followed,
# downloading a browser mid-run and opening an unbounded screenshot-critique
# loop that ate the turn budget. Fail fast and unambiguously instead: this
# script captures with what is already installed, and never installs anything.
# Exit 3 = "no browser, skip the capture", distinct from exit 1 = real failure.
if ! ls -d "$HOME/.cache/ms-playwright"/chromium-* >/dev/null 2>&1; then
  echo "shoot-site: SHOOT_NO_BROWSER — no chromium in ~/.cache/ms-playwright" >&2
  echo "shoot-site: this script never installs browsers; skip the capture step." >&2
  exit 3
fi

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
