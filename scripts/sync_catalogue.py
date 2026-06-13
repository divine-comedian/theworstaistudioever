#!/usr/bin/env python3
"""Inject repo-owned catalogue rows into the live ui-ux-pro-max plugin CSVs.

The repo's seeds/catalogue/*.additions.csv files are the source of truth. This script
appends any row not already present (matched by its unique name column) into every
installed copy of the plugin's styles.csv / landing.csv. Idempotent and version-bump safe:
it globs ALL installed plugin versions, so re-running after an update re-injects rows into
the new version's freshly-copied CSVs.

stdlib only. Usage: sync_catalogue.py <repo_root>
"""
import csv
import glob
import os
import sys
from pathlib import Path

# (additions filename, target plugin filename, unique-key column)
TARGETS = [
    ("styles.additions.csv", "styles.csv", "Style Category"),
    ("landing.additions.csv", "landing.csv", "Pattern Name"),
]

# Every installed plugin data dir (cache + marketplace, all versions).
PLUGIN_GLOBS = [
    "~/.claude/plugins/cache/ui-ux-pro-max-skill/ui-ux-pro-max/*/src/ui-ux-pro-max/data",
    "~/.claude/plugins/marketplaces/ui-ux-pro-max-skill/src/ui-ux-pro-max/data",
]


def plugin_data_dirs():
    dirs = []
    for pat in PLUGIN_GLOBS:
        dirs.extend(glob.glob(os.path.expanduser(pat)))
    # de-dupe, keep only real dirs
    return sorted({d for d in dirs if os.path.isdir(d)})


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        rows = list(r)
    return rows[0], rows[1:]  # header, data


def max_no(data_rows):
    mx = 0
    for row in data_rows:
        if row and row[0].strip().isdigit():
            mx = max(mx, int(row[0].strip()))
    return mx


def sync_one(additions_path, target_path, key_col):
    if not os.path.exists(additions_path):
        return (0, 0, f"no additions file ({os.path.basename(additions_path)})")
    add_header, add_rows = read_rows(additions_path)
    add_rows = [r for r in add_rows if any(c.strip() for c in r)]  # drop blank lines
    if not add_rows:
        return (0, 0, "additions file empty")

    tgt_header, tgt_rows = read_rows(target_path)
    if tgt_header != add_header:
        raise SystemExit(
            f"SCHEMA MISMATCH for {target_path}\n  plugin : {tgt_header}\n  repo   : {add_header}"
        )
    key_idx = tgt_header.index(key_col)
    existing = {r[key_idx].strip() for r in tgt_rows if len(r) > key_idx}

    next_no = max_no(tgt_rows) + 1
    appended, skipped = 0, 0
    to_append = []
    for row in add_rows:
        name = row[key_idx].strip() if len(row) > key_idx else ""
        if not name or name in existing:
            skipped += 1
            continue
        row = list(row)
        row[0] = str(next_no)  # renumber against the live target
        next_no += 1
        existing.add(name)
        to_append.append(row)
        appended += 1

    if to_append:
        with open(target_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(to_append)
    return (appended, skipped, None)


def main():
    repo_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    cat_dir = repo_root / "seeds" / "catalogue"
    data_dirs = plugin_data_dirs()
    if not data_dirs:
        raise SystemExit("ERROR: no ui-ux-pro-max plugin data dir found. Is the skill installed?")

    print(f"catalogue: {cat_dir}")
    grand_added = 0
    for data_dir in data_dirs:
        print(f"\n-> {data_dir}")
        for add_name, tgt_name, key_col in TARGETS:
            add_path = str(cat_dir / add_name)
            tgt_path = str(Path(data_dir) / tgt_name)
            if not os.path.exists(tgt_path):
                print(f"   {tgt_name}: target missing, skipped")
                continue
            added, skipped, note = sync_one(add_path, tgt_path, key_col)
            grand_added += added
            tail = f" ({note})" if note else ""
            print(f"   {tgt_name}: +{added} added, {skipped} already present{tail}")

    print(f"\nsync complete. {grand_added} row(s) injected across {len(data_dirs)} plugin dir(s).")


if __name__ == "__main__":
    main()
