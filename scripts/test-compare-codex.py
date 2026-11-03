#!/usr/bin/env python3
"""Check that trial preparation isolates production inputs and private files."""

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("comparison", Path(__file__).with_name("compare-codex.py"))
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


class TrialIsolationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "scripts/helper.py").write_text("# harmless fixture\n")
        (self.root / "pipeline.md").write_text("Generate one entry.\n")
        (self.root / "prompts/comparisons").mkdir(parents=True)
        (self.root / "prompts/codex-quality.md").write_text("Apply source-product patterns and edit the satire.\n")
        (self.root / "prompts/comparisons/notion-for-wedding-djs.json").write_text(
            json.dumps({"demo_requirements": ["Use a compact document workspace"]}))
        (self.root / ".env").write_text("PRIVATE_TOKEN=must-not-copy\n")
        (self.root / "state").mkdir()
        (self.root / "state/history.json").write_text('[{"production":true}]\n')
        site = self.root / "site"
        site.mkdir()
        for filename in ["styles.css", "404.html", "CNAME", "favicon.png", "logo.png"]:
            (site / filename).write_text("fixture")
        for index, (slug, date) in enumerate([("previous-for-dogs", "2026-10-30"),
                                              ("notion-for-wedding-djs", "2026-10-31"),
                                              ("later-for-cats", "2026-11-01")]):
            directory = site / "entries" / slug
            directory.mkdir(parents=True)
            (directory / "concept.json").write_text(json.dumps({
                "date": date, "company": "Notion", "subject": "wedding DJs",
                "slug": slug, "tagline": "Notion for wedding DJs",
                "product_name": "Cuebook", "demo_screen_concept": "Editable request database",
                "hero": {"h1": "ORIGINAL HEADLINE MUST STAY PRIVATE FROM TRIAL"},
            }))
            (directory / "index.html").write_text("ORIGINAL LANDING HTML")
            (directory / "headshot-1.webp").write_bytes(b"same-image-bytes")
        self.skill = self.root / "fixture-skill"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text("Use the local dataset.\n")
        (self.root / "data").mkdir()
        (self.root / "data/palettes.csv").write_text("name,color\nexample,#123456\n")
        (self.skill / "data").symlink_to(self.root / "data", target_is_directory=True)

    def test_prepare_preserves_production_and_copies_only_trial_inputs(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*")
                  if p.is_file() and "fixture-skill/data" not in str(p)}
        with patch.object(comparison, "ROOT", self.root), patch.object(comparison, "skill_source", return_value=self.skill):
            output = comparison.prepare("notion-for-wedding-djs")
        manifest = json.loads((output / "manifest.json").read_text())
        workspace = Path(manifest["workspace"])
        self.addCleanup(shutil.rmtree, workspace)
        self.assertFalse((workspace / ".env").exists())
        entry = workspace / "site/entries/notion-for-wedding-djs"
        self.assertFalse((entry / "index.html").exists())
        self.assertFalse((entry / "concept.json").exists())
        self.assertEqual((entry / "headshot-1.webp").read_bytes(), b"same-image-bytes")
        self.assertNotIn("ORIGINAL HEADLINE", (workspace / "trial-brief.json").read_text())
        brief = json.loads((workspace / "trial-brief.json").read_text())
        self.assertEqual(brief["comparison_requirements"]["demo_requirements"], ["Use a compact document workspace"])
        self.assertEqual(manifest["quality_revision"], 2)
        self.assertEqual((workspace / "codex-quality.md").read_bytes(), (self.root / "prompts/codex-quality.md").read_bytes())
        self.assertTrue((workspace / ".agents/skills/frontend-skill/SKILL.md").is_file())
        self.assertEqual((Path(manifest["baseline"]) / "index.html").read_text(), "ORIGINAL LANDING HTML")
        history = json.loads((workspace / "state/history.json").read_text())
        self.assertEqual([row["slug"] for row in history], ["previous-for-dogs"])
        self.assertFalse((workspace / "site/entries/later-for-cats").exists())
        copied_data = workspace / ".agents/skills/ui-ux-pro-max/data"
        self.assertFalse(copied_data.is_symlink())
        self.assertIn("#123456", (copied_data / "palettes.csv").read_text())
        self.assertFalse((output / "public").exists())
        for path, content in before.items():
            self.assertEqual((self.root / path).read_bytes(), content, str(path))

    def test_missing_quality_review_rejects_output_before_validation_or_publication(self):
        output = self.root / "trial"
        output.mkdir()
        with patch.object(comparison.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "Missing quality checkpoint"):
                comparison.finish(output, {"workspace": str(self.root), "entry": "notion-for-wedding-djs", "quality_revision": 2})
        run.assert_not_called()
        self.assertFalse((output / "public").exists())

    def test_empty_quality_fields_cannot_satisfy_the_checkpoint(self):
        output = self.root / "trial"
        output.mkdir()
        (self.root / "quality-plan.json").write_text('{"source_product_patterns": []}')
        with self.assertRaisesRegex(RuntimeError, "Incomplete quality checkpoint"):
            comparison.finish(output, {"workspace": str(self.root), "entry": "notion-for-wedding-djs", "quality_revision": 2})
        self.assertFalse((output / "public").exists())

    def test_plan_must_describe_enough_source_product_patterns(self):
        output = self.root / "trial"
        output.mkdir()
        plan = {
            "source_product_patterns": ["Sidebar", "Document", "Database"],
            "primary_workflow": "Find and edit requests",
            "landing_direction": "Quiet product-led composition",
            "demo_direction": "Document workspace",
            "satire_observations": ["Duplicate requests", "Photographer timing", "Venue curfew"],
            "headline_candidates": ["First", "Second", "Third"],
            "selected_headline": "First",
        }
        (self.root / "quality-plan.json").write_text(json.dumps(plan))
        with self.assertRaisesRegex(RuntimeError, "at least 4 source_product_patterns"):
            comparison.finish(output, {"workspace": str(self.root), "entry": "notion-for-wedding-djs", "quality_revision": 2})
        self.assertFalse((output / "public").exists())

    def test_a_second_repair_is_rejected_before_invoking_codex(self):
        output = self.root / "trial"
        output.mkdir()
        (output / "manifest.json").write_text(json.dumps({
            "workspace": str(self.root), "status": "validated", "repair_count": 1,
        }))
        feedback = self.root / "feedback.txt"
        feedback.write_text("Fix a browser-confirmed defect.")
        with patch("sys.argv", ["compare-codex.py", "--repair", str(output), "--feedback", str(feedback)]), \
             patch.object(comparison.shutil, "which", return_value="/fake/codex"), \
             patch.object(comparison.subprocess, "Popen") as invoke:
            with self.assertRaisesRegex(SystemExit, "no previous repair pass"):
                comparison.main()
        invoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
