#!/usr/bin/env bash
# Tests for validate-entry.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VALIDATE="$SCRIPT_DIR/validate-entry.sh"
TMP="$(mktemp -d)"
trap "rm -rf $TMP" EXIT

PASS=0
FAIL=0

assert_pass() {
  local name="$1" slug="$2"
  if "$VALIDATE" "$TMP" "$slug" >/dev/null 2>&1; then
    echo "PASS: $name"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $name (expected pass, got fail)"
    FAIL=$((FAIL + 1))
  fi
}

assert_fail() {
  local name="$1" slug="$2"
  if "$VALIDATE" "$TMP" "$slug" >/dev/null 2>&1; then
    echo "FAIL: $name (expected fail, got pass)"
    FAIL=$((FAIL + 1))
  else
    echo "PASS: $name"
    PASS=$((PASS + 1))
  fi
}

make_valid_entry() {
  local slug="$1"
  mkdir -p "$TMP/entries/$slug"
  # ~3KB of real-looking HTML
  printf '<!doctype html><html><head><title>Test</title></head><body>%s</body></html>' \
    "$(head -c 3000 < /dev/urandom | base64 | tr -d '\n' | head -c 3000)" \
    > "$TMP/entries/$slug/index.html"
  cp "$TMP/entries/$slug/index.html" "$TMP/entries/$slug/demo.html"
  cat > "$TMP/entries/$slug/concept.json" <<JSON
{
  "date": "2026-05-13",
  "tagline": "Tinder for dogs",
  "product_name": "Bark",
  "one_liner": "swipe right on good boys",
  "design_direction": {"style":"brutalist","palette":{},"fonts":{},"archetype":"saas-landing"}
}
JSON
}

# Test 1: valid entry passes
make_valid_entry "tinder-for-dogs"
assert_pass "valid entry" "tinder-for-dogs"

# Test 2: missing index.html fails
mkdir -p "$TMP/entries/missing-index"
touch "$TMP/entries/missing-index/demo.html"
echo '{}' > "$TMP/entries/missing-index/concept.json"
assert_fail "missing index.html" "missing-index"

# Test 3: tiny HTML (<2KB) fails
mkdir -p "$TMP/entries/tiny"
echo "<html></html>" > "$TMP/entries/tiny/index.html"
echo "<html></html>" > "$TMP/entries/tiny/demo.html"
echo '{"date":"x","tagline":"x","product_name":"x","one_liner":"x","design_direction":{}}' \
  > "$TMP/entries/tiny/concept.json"
assert_fail "tiny html under 2KB" "tiny"

# Test 4: malformed JSON fails
make_valid_entry "bad-json"
echo "not json" > "$TMP/entries/bad-json/concept.json"
assert_fail "malformed concept.json" "bad-json"

# Test 5: concept.json missing required field fails
make_valid_entry "missing-field"
echo '{"tagline":"x"}' > "$TMP/entries/missing-field/concept.json"
assert_fail "concept.json missing required field" "missing-field"

# Test 6: HTML missing <body> fails
mkdir -p "$TMP/entries/no-body"
printf '<!doctype html><html><head><title>x</title></head></html>%s' \
  "$(head -c 3000 < /dev/urandom | base64 | tr -d '\n' | head -c 3000)" \
  > "$TMP/entries/no-body/index.html"
cp "$TMP/entries/no-body/index.html" "$TMP/entries/no-body/demo.html"
echo '{"date":"x","tagline":"x","product_name":"x","one_liner":"x","design_direction":{}}' \
  > "$TMP/entries/no-body/concept.json"
assert_fail "html missing body tag" "no-body"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
