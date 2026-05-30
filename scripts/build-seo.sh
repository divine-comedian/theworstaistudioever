#!/usr/bin/env bash
# Regenerate the site's crawler-facing fixtures from the current entries.
# Writes <site-dir>/{sitemap.xml, robots.txt, llms.txt, feed.json, latest.json}.
# Usage: scripts/build-seo.sh <site-dir>
# Idempotent: derives everything from site/entries/*/concept.json + site/CNAME.
#
# feed.json  — JSON Feed 1.1 (jsonfeed.org), full list newest-first; items[0] is latest.
# latest.json — flat object for the single newest entry (url, tagline, description,
#               date_published, app_name). Fetch it to get the latest drop in one hop.
set -euo pipefail

SITE_DIR="${1:?usage: build-seo.sh <site-dir>}"
ENTRIES_DIR="$SITE_DIR/entries"

err() { echo "build-seo: $*" >&2; exit 1; }

[ -d "$ENTRIES_DIR" ] || err "no entries dir at $ENTRIES_DIR"
command -v jq >/dev/null 2>&1 || err "jq not found"

# Real tab, built portably so it survives whatever shell runs this script.
TAB="$(printf '\t')"

# Domain comes from the CNAME the same way the wrapper resolves it.
DOMAIN="$(cat "$SITE_DIR/CNAME" 2>/dev/null || echo "theworstaistudioever.com")"
DOMAIN="$(printf '%s' "$DOMAIN" | tr -d '[:space:]')"
BASE="https://${DOMAIN}"

# One studio summary line, reused across llms.txt and the JSON feed.
SUMMARY="An applied AI studio shipping venture-grade products for underserved, over-instrumented markets. New portfolio company daily."

# Collect every entry as a tab-separated row, newest date first.
# Columns: date  slug  tagline  one_liner
ROWS="$(
  for c in "$ENTRIES_DIR"/*/concept.json; do
    [ -f "$c" ] || continue
    jq -r '[.date, .slug, .tagline, (.one_liner // .hero.sub // "")] | @tsv' "$c"
  done | sort -t$'\t' -k1,1r
)"
[ -n "$ROWS" ] || err "no concept.json files found under $ENTRIES_DIR"

# Newest entry date drives the homepage lastmod.
LATEST_DATE="$(printf '%s\n' "$ROWS" | head -1 | cut -f1)"

xml_escape() { local s="$1"; s="${s//&/&amp;}"; s="${s//</&lt;}"; s="${s//>/&gt;}"; printf '%s' "$s"; }

# ---- sitemap.xml -----------------------------------------------------------
{
  echo '<?xml version="1.0" encoding="UTF-8"?>'
  echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
  echo "  <url><loc>${BASE}/</loc><lastmod>${LATEST_DATE}</lastmod></url>"
  while IFS="$TAB" read -r date slug _tagline _oneliner; do
    [ -n "$slug" ] || continue
    echo "  <url><loc>${BASE}/entries/${slug}/</loc><lastmod>${date}</lastmod></url>"
    echo "  <url><loc>${BASE}/entries/${slug}/demo.html</loc><lastmod>${date}</lastmod></url>"
  done <<< "$ROWS"
  echo '</urlset>'
} > "$SITE_DIR/sitemap.xml"

# ---- robots.txt ------------------------------------------------------------
{
  echo "# Nothing here is load-bearing. Crawl all of it."
  echo "User-agent: *"
  echo "Allow: /"
  echo ""
  echo "Sitemap: ${BASE}/sitemap.xml"
} > "$SITE_DIR/robots.txt"

# ---- llms.txt --------------------------------------------------------------
# llmstxt.org format: H1, blockquote summary, notes, then a linked catalog.
{
  echo "# theworstaistudioever"
  echo ""
  echo "> ${SUMMARY}"
  echo ""
  echo "Each portfolio company is a real-sounding product built for a market that never asked for it. One ships per day. The full catalog is below, newest first."
  echo ""
  echo "## Portfolio"
  echo ""
  while IFS="$TAB" read -r _date slug tagline oneliner; do
    [ -n "$slug" ] || continue
    line="- [${tagline}](${BASE}/entries/${slug}/)"
    [ -n "$oneliner" ] && line="${line}: ${oneliner}"
    line="${line} ([demo](${BASE}/entries/${slug}/demo.html))"
    echo "$line"
  done <<< "$ROWS"
} > "$SITE_DIR/llms.txt"

# ---- feed.json (JSON Feed 1.1) + latest.json -------------------------------
# Built with jq straight from the concept files so JSON escaping is never our
# problem. Both sort newest-first by date; entries only carry a calendar date,
# so date_published is pinned to midnight UTC (RFC 3339).
#
# JSON Feed standard fields: id, url, title (the tagline), summary/content_text
# (the description), date_published. Studio-specific bits live under the "_studio"
# extension object per the spec, where app_name is the invented product name.
jq -s \
  --arg base "$BASE" \
  --arg summary "$SUMMARY" \
  '
  ( map({
      slug: .slug,
      tagline: .tagline,
      description: (.one_liner // .hero.sub // ""),
      app_name: (.product_name // ""),
      date: .date
    })
    | sort_by(.date) | reverse
  ) as $items
  | {
      version: "https://jsonfeed.org/version/1.1",
      title: "theworstaistudioever",
      home_page_url: ($base + "/"),
      feed_url: ($base + "/feed.json"),
      description: $summary,
      items: ($items | map({
        id: ($base + "/entries/" + .slug + "/"),
        url: ($base + "/entries/" + .slug + "/"),
        title: .tagline,
        summary: .description,
        content_text: .description,
        date_published: (.date + "T00:00:00Z"),
        _studio: {
          app_name: .app_name,
          slug: .slug,
          demo_url: ($base + "/entries/" + .slug + "/demo.html")
        }
      }))
    }
  ' "$ENTRIES_DIR"/*/concept.json > "$SITE_DIR/feed.json"

jq -s \
  --arg base "$BASE" \
  '
  ( map({
      slug: .slug,
      tagline: .tagline,
      description: (.one_liner // .hero.sub // ""),
      app_name: (.product_name // ""),
      date: .date
    })
    | sort_by(.date) | reverse | .[0]
  ) as $e
  | {
      app_name: $e.app_name,
      tagline: $e.tagline,
      description: $e.description,
      url: ($base + "/entries/" + $e.slug + "/"),
      demo_url: ($base + "/entries/" + $e.slug + "/demo.html"),
      date_published: ($e.date + "T00:00:00Z"),
      slug: $e.slug
    }
  ' "$ENTRIES_DIR"/*/concept.json > "$SITE_DIR/latest.json"

count="$(printf '%s\n' "$ROWS" | grep -c . || true)"
echo "build-seo: wrote sitemap.xml, robots.txt, llms.txt, feed.json, latest.json for ${count} entries (domain ${DOMAIN})"
