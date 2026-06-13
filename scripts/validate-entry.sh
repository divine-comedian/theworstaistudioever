#!/usr/bin/env bash
# Usage: validate-entry.sh <site-root> <slug>
# Exits 0 if entry passes all checks, non-zero with a stderr message otherwise.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <site-root> <slug>" >&2
  exit 2
fi

SITE_ROOT="$1"
SLUG="$2"
DIR="$SITE_ROOT/entries/$SLUG"

fail() { echo "validate-entry [$SLUG]: $*" >&2; exit 1; }

[[ -d "$DIR" ]] || fail "entry directory missing: $DIR"

# 1. Required files exist
for f in index.html demo.html concept.json; do
  [[ -f "$DIR/$f" ]] || fail "missing required file: $f"
done

# 2. HTML files are >= 2KB
for f in index.html demo.html; do
  size=$(wc -c < "$DIR/$f")
  [[ "$size" -ge 2048 ]] || fail "$f too small: ${size} bytes (need >= 2048)"
done

# 3. HTML files have <html>, </html>, and non-empty <body>
for f in index.html demo.html; do
  grep -qi '<html' "$DIR/$f" || fail "$f missing <html> tag"
  grep -qi '</html>' "$DIR/$f" || fail "$f missing </html> tag"
  grep -qi '<body' "$DIR/$f" || fail "$f missing <body> tag"
done

# 4. concept.json parses
jq empty "$DIR/concept.json" 2>/dev/null || fail "concept.json is not valid JSON"

# 5. concept.json has required top-level fields
for field in date tagline product_name one_liner design_direction; do
  has=$(jq --arg f "$field" 'has($f)' "$DIR/concept.json")
  [[ "$has" == "true" ]] || fail "concept.json missing required field: $field"
done

# 6. Every <img src> is local (no hotlinking) and resolves inside the entry dir.
#    data: URIs are allowed — they're self-contained.
DIR_REAL="$(realpath "$DIR")"
for f in index.html demo.html; do
  while IFS= read -r src; do
    [[ -z "$src" ]] && continue
    case "$src" in
      data:*) continue ;;
      http://*|https://*|//*) fail "$f hotlinks an image: $src" ;;
    esac
    path="${src%%\?*}"; path="${path%%#*}"; path="${path#./}"
    target="$DIR/$path"
    [[ -f "$target" ]] || fail "$f references missing image: $src"
    case "$(realpath -m "$target")" in
      "$DIR_REAL"/*) ;;
      *) fail "$f image path escapes entry dir: $src" ;;
    esac
  done < <(grep -oi '<img[^>]*src="[^"]*"' "$DIR/$f" 2>/dev/null | sed 's/.*src="\([^"]*\)".*/\1/' || true)
done

# 7. Every image file in the entry dir decodes with PIL and is <= 500 KB
shopt -s nullglob
for img in "$DIR"/*.png "$DIR"/*.jpg "$DIR"/*.jpeg "$DIR"/*.webp "$DIR"/*.gif; do
  size=$(wc -c < "$img")
  [[ "$size" -le 512000 ]] || fail "image too large: $(basename "$img") (${size} bytes > 512000)"
  python3 -c "import sys; from PIL import Image; Image.open(sys.argv[1]).verify()" "$img" 2>/dev/null \
    || fail "image does not decode: $(basename "$img")"
done
shopt -u nullglob

echo "validate-entry [$SLUG]: OK"
