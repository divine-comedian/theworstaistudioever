#!/usr/bin/env python3
"""Check real headless QA detects rendered defects and verifies state changes."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from PIL import Image

from pipeline_qa import preview


ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts/check-entry-browser.cjs"


class BrowserTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entry = self.root / "site/entries/fixture-for-dogs"
        self.entry.mkdir(parents=True)
        self.output = self.root / "evidence"
        (self.root / "site/index.html").write_text('<html><body><a href="/entries/fixture-for-dogs/">Fixture</a></body></html>')
        (self.entry / "index.html").write_text('<html><body><h1>Fixture</h1><a href="./demo.html">Open demo</a></body></html>')
        self.demo = '''<html><body><a href="./index.html">Back</a><h1>Requests</h1>
<label>Search <input id="search"></label><div id="dogs">Dog request</div><div id="cats">Cat request</div>
<script>document.querySelector('#search').oninput=e=>{
document.querySelector('#cats').hidden=e.target.value==='dog';
};</script></body></html>'''
        (self.entry / "demo.html").write_text(self.demo)
        self.plan = self.root / "plan.json"
        self.plan.write_text(json.dumps({"demo_test": {
            "actions": [{"action": "fill", "selector": "#search", "value": "dog"}],
            "assertions": [{"check": "hidden", "selector": "#cats", "expected": "-"},
                           {"check": "text", "selector": "#dogs", "expected": "Dog request"}],
        }}))

    def invoke(self, interaction=False):
        with preview(self.root) as base:
            args = ["node", str(CHECKER)]
            if interaction:
                args.append("--interaction")
            args.extend([base, "fixture-for-dogs"])
            if interaction:
                args.append(str(self.plan))
            args.append(str(self.output))
            result = subprocess.run(args, capture_output=True, text=True, timeout=60)
        report = json.loads((self.output / ("interaction.json" if interaction else "browser.json")).read_text())
        return result, report

    def test_render_and_interaction_pass_with_screenshots_on_both_viewports(self):
        result, report = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr + json.dumps(report))
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["pages"]), 4)
        for page in report["pages"]:
            self.assertTrue(Path(page["screenshot"]).is_file())
            with Image.open(page["foldScreenshot"]) as image:
                self.assertEqual(image.size, (page["viewport"]["width"], page["viewport"]["height"]))
        result, report = self.invoke(interaction=True)
        self.assertEqual(result.returncode, 0, result.stderr + json.dumps(report))
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["viewports"]), 2)
        for viewport in report["viewports"]:
            self.assertEqual(viewport["assertions"][0]["before"], "true")
            self.assertEqual(viewport["assertions"][0]["observed"], "false")

    def test_rendered_missing_image_runtime_error_and_mobile_overflow_fail(self):
        (self.entry / "demo.html").write_text(self.demo.replace('</body>',
            '<div style="width:1200px">Overflow</div><img src="missing.webp"><script>throw Error("fixture crash")</script></body>'))
        result, report = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(report["passed"])
        mobile = next(page for page in report["pages"] if page["filename"] == "demo.html" and page["viewport"]["width"] == 390)
        self.assertIn("Page overflows viewport horizontally", mobile["failures"])
        self.assertIn("Broken rendered images", mobile["failures"])
        self.assertIn("fixture crash", mobile["errors"])

    def test_composer_clears_input_after_posting(self):
        (self.entry / "demo.html").write_text('''<html><body>
<form id="composer"><input id="post-text"><button>Post</button></form><p id="result"></p>
<script>document.querySelector('#composer').onsubmit=e=>{
e.preventDefault();const input=document.querySelector('#post-text');
document.querySelector('#result').textContent=input.value;input.value='';
};</script></body></html>''')
        self.plan.write_text(json.dumps({"demo_test": {
            "actions": [{"action": "fill", "selector": "#post-text", "value": "Encore during load-out"},
                        {"action": "click", "selector": "#composer button", "value": ""}],
            "assertions": [{"check": "text", "selector": "#result", "expected": "Encore during load-out"},
                           {"check": "value", "selector": "#post-text", "expected": ""}],
        }}))
        result, report = self.invoke(interaction=True)
        self.assertEqual(result.returncode, 0, result.stderr + json.dumps(report))
        self.assertTrue(report["passed"])
        for viewport in report["viewports"]:
            self.assertEqual(viewport["assertions"][1]["observed"], "")

    def test_native_playback_progress_value_can_be_asserted(self):
        (self.entry / "demo.html").write_text('''<html><body>
<progress id="progress" value="1" max="4"></progress><button id="next">Next scene</button>
<script>document.querySelector('#next').onclick=()=>{
document.querySelector('#progress').value+=1;
};</script></body></html>''')
        self.plan.write_text(json.dumps({"demo_test": {
            "actions": [{"action": "click", "selector": "#next", "value": "-"}],
            "assertions": [{"check": "value", "selector": "#progress", "expected": "2"}],
        }}))
        result, report = self.invoke(interaction=True)
        self.assertEqual(result.returncode, 0, result.stderr + json.dumps(report))
        self.assertTrue(report["passed"])
        for viewport in report["viewports"]:
            self.assertEqual(viewport["assertions"][0]["before"], "1")
            self.assertEqual(viewport["assertions"][0]["observed"], "2")

    def test_static_heading_assertion_cannot_claim_successful_interaction(self):
        plan = json.loads(self.plan.read_text())
        plan["demo_test"]["assertions"] = [{"check": "text", "selector": "h1", "expected": "Requests"}]
        self.plan.write_text(json.dumps(plan))
        result, report = self.invoke(interaction=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(report["passed"])
        self.assertTrue(all(any("changed rendered state" in failure for failure in viewport["failures"])
                            for viewport in report["viewports"]))


if __name__ == "__main__":
    unittest.main()
