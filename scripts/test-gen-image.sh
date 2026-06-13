#!/usr/bin/env bash
# Tests for gen-image.sh — all offline (dry-run, missing key, cap file, args).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GEN="$SCRIPT_DIR/gen-image.sh"
TMP="$(mktemp -d)"
trap "rm -rf $TMP" EXIT

PASS=0
FAIL=0

ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

# Isolate every test from the real repo .env and state/runs counter.
touch "$TMP/empty.env"
mkdir -p "$TMP/state"
run_gen() {
  env -u GEMINI_API_KEY -u GEMINI_IMAGE_MODEL \
    GEN_IMAGE_ENV_FILE="$TMP/empty.env" GEN_IMAGE_STATE_DIR="$TMP/state" \
    "$@" "$GEN" "${ARGS[@]}"
}

TODAY="$(date -u +%F)"
CAP_FILE="$TMP/state/${TODAY}.imagegen"

# Test 1: --dry-run prints payload with prompt, aspect ratio, and default model
ARGS=("a deadpan corporate headshot of an otter" "16:9" "$TMP/out.png" --dry-run)
if OUT="$(run_gen env 2>/dev/null)" \
   && jq -e '.model == "gemini-3.1-flash-image"' <<<"$OUT" >/dev/null \
   && jq -e '.body.generationConfig.imageConfig.aspectRatio == "16:9"' <<<"$OUT" >/dev/null \
   && jq -e '.body.contents[0].parts[0].text == "a deadpan corporate headshot of an otter"' <<<"$OUT" >/dev/null; then
  ok "dry-run payload has model, aspect, prompt"
else
  bad "dry-run payload has model, aspect, prompt"
fi

# Test 2: GEMINI_IMAGE_MODEL override is reflected in the payload
ARGS=("prompt" "1:1" "$TMP/out.png" --dry-run)
if OUT="$(run_gen env GEMINI_IMAGE_MODEL=test-model-override 2>/dev/null)" \
   && jq -e '.model == "test-model-override"' <<<"$OUT" >/dev/null; then
  ok "GEMINI_IMAGE_MODEL override respected"
else
  bad "GEMINI_IMAGE_MODEL override respected"
fi

# Test 3: dry-run does not create or increment the counter file
if [[ ! -e "$CAP_FILE" ]]; then
  ok "dry-run does not touch counter file"
else
  bad "dry-run does not touch counter file"
fi

# Test 4: missing GEMINI_API_KEY (non-dry-run) exits non-zero with clear message
ARGS=("prompt" "1:1" "$TMP/out.png")
if ERR="$(run_gen env 2>&1)"; then
  bad "missing key exits non-zero"
else
  if grep -q "GEMINI_API_KEY" <<<"$ERR"; then
    ok "missing key exits non-zero"
  else
    bad "missing key exits non-zero (no GEMINI_API_KEY in message: $ERR)"
  fi
fi

# Test 5: missing key path did not create the counter file
if [[ ! -e "$CAP_FILE" ]]; then
  ok "missing key does not touch counter file"
else
  bad "missing key does not touch counter file"
fi

# Test 6: counter at cap refuses with IMAGEGEN_CAP_REACHED, no increment
echo 10 > "$CAP_FILE"
ARGS=("prompt" "1:1" "$TMP/out.png")
if ERR="$(run_gen env GEMINI_API_KEY=dummy 2>&1)"; then
  bad "cap reached refuses"
else
  if grep -q "IMAGEGEN_CAP_REACHED" <<<"$ERR" && [[ "$(cat "$CAP_FILE")" == "10" ]]; then
    ok "cap reached refuses without incrementing"
  else
    bad "cap reached refuses without incrementing (err: $ERR, count: $(cat "$CAP_FILE"))"
  fi
fi
rm -f "$CAP_FILE"

# Test 7: unsupported aspect ratio exits non-zero
ARGS=("prompt" "7:3" "$TMP/out.png" --dry-run)
if run_gen env >/dev/null 2>&1; then
  bad "invalid aspect ratio rejected"
else
  ok "invalid aspect ratio rejected"
fi

# Test 8: wrong number of args exits non-zero with usage
ARGS=("only-a-prompt")
if ERR="$(run_gen env 2>&1)"; then
  bad "bad arg count rejected"
else
  if grep -qi "usage" <<<"$ERR"; then
    ok "bad arg count rejected"
  else
    bad "bad arg count rejected (no usage in: $ERR)"
  fi
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
