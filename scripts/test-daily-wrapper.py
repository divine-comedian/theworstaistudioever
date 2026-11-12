#!/usr/bin/env python3
"""Exercise the real wrapper and validators with isolated fake external commands."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent


class DailyWrapperTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ["scripts", "site/entries", "state", "pipelines/codex-v1", "home/.local/bin"]:
            (self.root / directory).mkdir(parents=True)
        for name in ["run-daily.sh", "run-pipeline-agent.py", "pipeline_qa.py", "pipeline_editorial.py", "check-entry-browser.cjs", "build-seo.sh", "build-entry-metadata.py", "validate-entry.sh", "validate-brand-kit.py"]:
            shutil.copy2(ROOT / "scripts" / name, self.root / "scripts" / name)
        shutil.copy2(ROOT / "site/logo.png", self.root / "site/logo.png")
        (self.root / "site/CNAME").write_text("example.com\n")
        (self.root / "pipeline.md").write_text("Fixture generation prompt")
        (self.root / "state/history.json").write_text("[]")
        (self.root / "pipelines/engine").write_text("codex\n")
        bundle = self.root / "pipelines/codex-v1"
        config = json.loads((ROOT / "pipelines/codex-v1/config.json").read_text())
        config.update(timeout_seconds=5, skills=["fixture"], concept_checkpoint={"enabled": False})
        config["qa"].update(review_timeout_seconds=5, repair_timeout_seconds=5, total_timeout_seconds=30, browser_timeout_seconds=5)
        (bundle / "config.json").write_text(json.dumps(config))
        for name in ["qa.md", "heal.md"]:
            shutil.copy2(ROOT / "pipelines/codex-v1" / name, bundle / name)
        shutil.copy2(ROOT / "pipelines/codex-v1/quality-floor.json", bundle / "quality-floor.json")
        shutil.copytree(ROOT / "pipelines/codex-v1/reference/again-approved", bundle / "reference/again-approved")
        (bundle / "adapter.md").write_text("Fixture adapter")
        (bundle / "skills/fixture").mkdir(parents=True)
        (bundle / "skills/fixture/SKILL.md").write_text("Fixture")
        commands = self.root / "home/.local/bin"
        node = commands / "node"
        node.write_text('''#!/usr/bin/env python3
import json,pathlib,sys
if '--preflight' in sys.argv:sys.exit(0)
output=pathlib.Path(sys.argv[-1]);output.mkdir(exist_ok=True)
pages=[]
for filename in ['index.html','demo.html']:
 for width in [1440,390]:
  shot=output/(filename+str(width)+'.png');shot.write_bytes(b'fixture-image')
  pages.append({'filename':filename,'viewport':{'width':width,'height':900},'screenshot':str(shot),'foldScreenshot':str(shot),'failures':[]})
(output/'browser.json').write_text(json.dumps({'passed':True,'pages':pages,'failures':[]}))
''')
        node.chmod(0o755)
        fake_git = commands / "git"
        fake_git.write_text('''#!/usr/bin/env python3
from pathlib import Path
import sys
with Path('git-calls.txt').open('a') as log:log.write(' '.join(sys.argv[1:])+'\\n')
sys.exit(1 if sys.argv[1]=='diff' else 0)
''')
        fake_git.chmod(0o755)
        fake_codex = commands / "codex"
        fake_codex.write_text('''#!/usr/bin/env python3
from pathlib import Path
import datetime,json,sys
sys.stdin.read()
print('PRIVATE_SERVICE_SESSION_TOKEN',flush=True)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':5}}),flush=True)
result=Path(sys.argv[sys.argv.index('--output-last-message')+1])
if '--output-schema' in sys.argv:
 failed=Path('fail-qa').exists()
 report={'slug':'fixture-for-dogs','verdict':'repair' if failed else 'pass','quality_floor':{'reference_id':'again-2026-11-11-approved','assessments':{key:{'meets':True,'evidence':'Specific requests, purposeful visuals and usable controls meet the reference standard.'} for key in ['comprehension','satire','composition','continuity']}},'premise':'Dogs submit requests.','strengths':['Specific subject'],'checks':{key:True for key in ['comprehension','satire','composition','continuity']},'copy_audit':[],'resolved_findings':[],'visual_audit':[{'page':p,'viewport':v,'dominant_content':'Requests','product_visual':'Request list','caption_legibility':'Readable','comprehension_pass':True,'audience_cues':'Dog portrait framing','audience_fit_pass':True} for p in ['index.html','demo.html'] for v in ['desktop','mobile']],
         'findings':[{'id':'F1','target':'p','acceptance':'Clear mechanic','patch':{'old':'','new':''},'category':'satire','file':'site/entries/fixture-for-dogs/index.html','quote':'Bark.','problem':'Unclear mapping','fix':'Use a clear request mechanic'}] if failed else [],
         'demo_test':{'actions':[{'action':'click','selector':'#submit','value':'-'}],'assertions':[{'check':'visible','selector':'#result','expected':'-'}]}}
 result.write_text(json.dumps(report));sys.exit(0)
if result.stem.startswith('repair-'):
 result.write_text('Repair attempted.');sys.exit(0)
if Path('fail-generator').exists():sys.exit(7)
entry=Path('site/entries/fixture-for-dogs');entry.mkdir()
concept={'date':datetime.datetime.now(datetime.timezone.utc).date().isoformat(),'company':'Fixture','subject':'dogs','slug':entry.name,'tagline':'Fixture for dogs','product_name':'Fixture','one_liner':'Requests for the entire pack.','hero':{'h1':'The pack has requests.','sub':'One system for all the barking.'},'design_direction':{'palette':{'bg':'#ffffff'}}}
(entry/'concept.json').write_text(json.dumps(concept))
for name in ['index.html','demo.html']:(entry/name).write_text('<html><head><title>Fixture</title></head><body><h1>The pack has requests.</h1><p>'+('Bark. '*500)+'</p></body></html>')
Path('state/history.json').write_text(json.dumps([{k:concept[k] for k in ['date','company','subject','slug']}]))
result.write_text('RUN_COMPLETE: fixture-for-dogs\\n')
''')
        fake_codex.chmod(0o755)
        fake_curl = commands / "curl"
        fake_curl.write_text("#!/bin/sh\necho unexpected-notification > curl-called\nexit 1\n")
        fake_curl.chmod(0o755)

    def invoke(self, *options):
        return subprocess.run(["bash", "scripts/run-daily.sh", *options], cwd=self.root,
                              env={"HOME": str(self.root / "home"), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                              capture_output=True, text=True, timeout=15)

    def test_selected_codex_flows_through_metadata_validation_seo_and_wrapper_git(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads((self.root / "site/latest.json").read_text())["slug"], "fixture-for-dogs")
        self.assertTrue((self.root / "site/entries/fixture-for-dogs/social-preview.jpg").is_file())
        calls = (self.root / "git-calls.txt").read_text()
        self.assertIn("commit -m feat: Fixture for dogs", calls)
        self.assertIn("push\n", calls)
        log = next((self.root / "state/runs").glob("*.log")).read_text()
        self.assertIn("daily run complete", log)
        self.assertNotIn("PRIVATE_SERVICE_SESSION_TOKEN", log)
        self.assertFalse((self.root / "curl-called").exists())

    def test_failed_codex_stops_before_validation_or_publish(self):
        (self.root / "fail-generator").touch()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        calls = (self.root / "git-calls.txt").read_text()
        self.assertNotIn("commit", calls)
        self.assertNotIn("push", calls)
        self.assertFalse((self.root / "site/latest.json").exists())
        self.assertFalse((self.root / "curl-called").exists())

    def test_publish_existing_revalidates_without_calling_codex(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.root / "fail-generator").touch()
        result = self.invoke("--publish-existing", "fixture-for-dogs", "--no-notify")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("generation skipped", result.stdout)
        self.assertEqual((self.root / "git-calls.txt").read_text().count("push\n"), 2)
        self.assertFalse((self.root / "curl-called").exists())

    def test_publish_existing_rejects_a_missing_entry(self):
        result = self.invoke("--publish-existing", "missing-for-dogs", "--no-notify")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("push", (self.root / "git-calls.txt").read_text())

    def test_failed_qa_blocks_git_and_removes_rejected_new_entry(self):
        (self.root / "fail-qa").touch()
        result = self.invoke("--no-notify")
        self.assertNotEqual(result.returncode, 0)
        calls = (self.root / "git-calls.txt").read_text()
        self.assertNotIn("commit", calls)
        self.assertNotIn("push", calls)
        self.assertEqual(json.loads((self.root / "state/history.json").read_text()), [])
        self.assertFalse((self.root / "site/entries/fixture-for-dogs").exists())
        self.assertTrue(list((self.root / ".tmp-codex").glob("*/rejected/fixture-for-dogs/concept.json")))
        self.assertFalse((self.root / "curl-called").exists())

    def test_publish_existing_cannot_bypass_qa(self):
        result = self.invoke("--no-notify")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.root / "fail-qa").touch()
        original = (self.root / "site/entries/fixture-for-dogs/index.html").read_bytes()
        result = self.invoke("--publish-existing", "fixture-for-dogs", "--no-notify")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("QA rejected existing entry", result.stdout)
        self.assertEqual((self.root / "git-calls.txt").read_text().count("push\n"), 1)
        self.assertEqual((self.root / "site/entries/fixture-for-dogs/index.html").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
