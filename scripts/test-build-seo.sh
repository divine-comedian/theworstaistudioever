#!/usr/bin/env bash
# Tests for build-seo.sh — builds a temp site, runs the generator, asserts the
# fixtures are well-formed and ordered newest-first.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD="$SCRIPT_DIR/build-seo.sh"

PASS=0
FAIL=0
pass() { echo "  ok: $*"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $*"; FAIL=$((FAIL+1)); }

make_entry() { # make_entry <site> <slug> <date> <tagline> <product> <one_liner>
  local site="$1" slug="$2" date="$3" tagline="$4" product="$5" oneliner="$6" dir
  dir="$site/entries/$slug"
  mkdir -p "$dir"
  jq -n \
    --arg date "$date" --arg slug "$slug" --arg tagline "$tagline" \
    --arg product "$product" --arg oneliner "$oneliner" \
    '{date:$date, slug:$slug, tagline:$tagline, product_name:$product,
      one_liner:$oneliner, design_direction:{style:"brutalist"}}' \
    > "$dir/concept.json"
  printf '<html><body>%*s</body></html>' 3000 '' > "$dir/index.html"
  printf '<html><body>%*s</body></html>' 3000 '' > "$dir/demo.html"
}

# Build a site with deliberately out-of-order, multi-word taglines (the bug the
# whole-line sort tripped on) plus a tied date, so we exercise ordering for real.
site="$(mktemp -d)"
echo "theworstaistudioever.com" > "$site/CNAME"
make_entry "$site" "box-for-octopuses"     "2026-05-27" "Box for octopuses"     "Mantle"    "The Containment Cloud for octopuses."
make_entry "$site" "notion-for-red-pandas" "2026-05-30" "Notion for red pandas" "Canopy"    "The connected workspace for solitary mammals."
make_entry "$site" "okta-for-barn-owls"    "2026-05-14" "Okta for barn owls"    "Strix"     "Identity governance for nocturnal raptors."
make_entry "$site" "palantir-for-dogs"     "2026-05-14" "Palantir for dogs"     "Houndsight" "Operational intelligence for the multi-dog household."

echo "test-build-seo:"

"$BUILD" "$site" >/dev/null 2>&1 || fail "build-seo exited non-zero"

# All five fixtures exist
for f in sitemap.xml robots.txt llms.txt feed.json latest.json; do
  [ -f "$site/$f" ] && pass "wrote $f" || fail "missing $f"
done

# sitemap.xml is well-formed and has homepage + 2 urls per entry (1 landing + 1 demo)
if python3 -c "import xml.dom.minidom,sys; xml.dom.minidom.parse(sys.argv[1])" "$site/sitemap.xml" 2>/dev/null; then
  pass "sitemap.xml is well-formed XML"
else
  fail "sitemap.xml is malformed"
fi
url_count="$(grep -c '<loc>' "$site/sitemap.xml" || true)"
[ "$url_count" -eq 9 ] && pass "sitemap has 9 urls (1 home + 4*2)" || fail "sitemap url count: $url_count (want 9)"

# feed.json and latest.json parse
jq empty "$site/feed.json" 2>/dev/null && pass "feed.json parses" || fail "feed.json invalid"
jq empty "$site/latest.json" 2>/dev/null && pass "latest.json parses" || fail "latest.json invalid"

# feed.json is JSON Feed 1.1 with the right item count
ver="$(jq -r '.version' "$site/feed.json")"
[ "$ver" = "https://jsonfeed.org/version/1.1" ] && pass "feed declares JSON Feed 1.1" || fail "feed version: $ver"
item_count="$(jq '.items | length' "$site/feed.json")"
[ "$item_count" -eq 4 ] && pass "feed has 4 items" || fail "feed item count: $item_count (want 4)"

# Ordering: items[0] is the newest date, regardless of insertion order
first_date="$(jq -r '.items[0].date_published' "$site/feed.json")"
[ "$first_date" = "2026-05-30T00:00:00Z" ] && pass "feed items[0] is newest" || fail "feed items[0] date: $first_date"
first_title="$(jq -r '.items[0].title' "$site/feed.json")"
[ "$first_title" = "Notion for red pandas" ] && pass "feed items[0] is the right entry" || fail "feed items[0] title: $first_title"

# Dates are non-increasing across the feed (true newest-first sort)
if jq -e '[.items[].date_published] | . == (sort | reverse)' "$site/feed.json" >/dev/null; then
  pass "feed dates are newest-first"
else
  fail "feed dates not sorted newest-first"
fi

# latest.json points at the single newest entry with every required field
for field in app_name tagline description url demo_url date_published slug; do
  v="$(jq -r --arg f "$field" '.[$f] // "MISSING"' "$site/latest.json")"
  [ "$v" != "MISSING" ] && [ -n "$v" ] && pass "latest.json has $field" || fail "latest.json missing $field"
done
latest_slug="$(jq -r '.slug' "$site/latest.json")"
[ "$latest_slug" = "notion-for-red-pandas" ] && pass "latest.json is the newest entry" || fail "latest.json slug: $latest_slug"
latest_app="$(jq -r '.app_name' "$site/latest.json")"
[ "$latest_app" = "Canopy" ] && pass "latest.json app_name is the product name" || fail "latest.json app_name: $latest_app"

# latest.json equals feed items[0] on the shared fields (single source of truth)
if [ "$(jq -r '.url' "$site/latest.json")" = "$(jq -r '.items[0].url' "$site/feed.json")" ]; then
  pass "latest.json url matches feed items[0]"
else
  fail "latest.json and feed disagree on the newest url"
fi

# robots.txt advertises the sitemap
grep -q "Sitemap: https://theworstaistudioever.com/sitemap.xml" "$site/robots.txt" \
  && pass "robots.txt advertises sitemap" || fail "robots.txt missing Sitemap line"

# Idempotent: a second run produces byte-identical output
before="$(cat "$site"/sitemap.xml "$site"/robots.txt "$site"/llms.txt "$site"/feed.json "$site"/latest.json | sha1sum)"
"$BUILD" "$site" >/dev/null 2>&1
after="$(cat "$site"/sitemap.xml "$site"/robots.txt "$site"/llms.txt "$site"/feed.json "$site"/latest.json | sha1sum)"
[ "$before" = "$after" ] && pass "output is idempotent" || fail "output changed on second run"

# Empty site (no entries) fails loudly rather than writing junk
empty="$(mktemp -d)"; mkdir -p "$empty/entries"
if "$BUILD" "$empty" >/dev/null 2>&1; then
  fail "empty site accepted (should error)"
else
  pass "empty site rejected"
fi

echo "  ---"
echo "  $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
echo "  all tests passed"
