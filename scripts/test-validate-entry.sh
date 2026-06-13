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

# --- image checks ---

make_image() { # make_image <path> [side-px]
  python3 -c "
from PIL import Image
Image.new('RGB', ($2, $2), (120, 80, 200)).save('$1')
"
}

# Test 7: entry with a valid local image referenced from HTML passes
make_valid_entry "with-image"
make_image "$TMP/entries/with-image/hero.webp" 64
printf '<!doctype html><html><head><title>t</title></head><body><img src="hero.webp" alt="">%s</body></html>' \
  "$(head -c 3000 < /dev/urandom | base64 | tr -d '\n' | head -c 3000)" \
  > "$TMP/entries/with-image/index.html"
assert_pass "entry with valid local image" "with-image"

# Test 8: <img src> pointing at a missing file fails
make_valid_entry "broken-img"
printf '<!doctype html><html><head><title>t</title></head><body><img src="nope.webp" alt="">%s</body></html>' \
  "$(head -c 3000 < /dev/urandom | base64 | tr -d '\n' | head -c 3000)" \
  > "$TMP/entries/broken-img/index.html"
assert_fail "broken img src" "broken-img"

# Test 9: hotlinked <img src> fails
make_valid_entry "hotlink-img"
printf '<!doctype html><html><head><title>t</title></head><body><img src="https://example.com/x.png" alt="">%s</body></html>' \
  "$(head -c 3000 < /dev/urandom | base64 | tr -d '\n' | head -c 3000)" \
  > "$TMP/entries/hotlink-img/index.html"
assert_fail "hotlinked img src" "hotlink-img"

# Test 10: image file over 500 KB fails
make_valid_entry "fat-img"
python3 -c "
import os
from PIL import Image
Image.frombytes('RGB', (600, 600), os.urandom(600*600*3)).save('$TMP/entries/fat-img/big.png')
assert os.path.getsize('$TMP/entries/fat-img/big.png') > 512000
"
assert_fail "image over 500KB" "fat-img"

# Test 11: image file that does not decode with PIL fails
make_valid_entry "corrupt-img"
head -c 4096 /dev/urandom > "$TMP/entries/corrupt-img/photo.webp"
assert_fail "corrupt image file" "corrupt-img"

# Test 12: data: URIs in img src are still allowed (existing entries use them)
make_valid_entry "data-uri-img"
printf '<!doctype html><html><head><title>t</title></head><body><img src="data:image/svg+xml,%%3Csvg/%%3E" alt="">%s</body></html>' \
  "$(head -c 3000 < /dev/urandom | base64 | tr -d '\n' | head -c 3000)" \
  > "$TMP/entries/data-uri-img/index.html"
assert_pass "data: uri img src allowed" "data-uri-img"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
