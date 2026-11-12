#!/usr/bin/env python3
"""Verify generator selection, bounded execution, and private trace handling."""

import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest

from pipeline_qa import (apply_exact_patches, read_review, review_schema, review_packet,
                         validate_copy_audit, validate_shape, validate_verdict, validate_visual_audit, StageFailure)
from pipeline_editorial import CONCEPT_SCHEMA, UsageLedger, recent_digest, roll
from pipeline_qa import quality_floor_context


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "scripts/run-pipeline-agent.py"


class GeneratorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        bundle = self.root / "pipelines/codex-v1"
        bundle.mkdir(parents=True)
        self.config = bundle / "config.json"
        self.config.write_text(json.dumps({"model": "gpt-6.1-sol", "reasoning_effort": "high", "timeout_seconds": 3,
            "qa": {"max_repair_attempts": 2, "review_timeout_seconds": 3, "repair_timeout_seconds": 3,
                   "total_timeout_seconds": 20, "browser_timeout_seconds": 3},
            "skills": ["anti-ai-slop", "frontend-design", "ui-ux-pro-max"]}))
        shutil.copy2(ROOT / "pipelines/codex-v1/quality-floor.json", bundle / "quality-floor.json")
        shutil.copytree(ROOT / "pipelines/codex-v1/reference/again-approved", bundle / "reference/again-approved")
        (bundle / "adapter.md").write_text("Read the frozen v1 skills.\n")
        for name in ["qa.md", "heal.md", "concept-qa.md"]:
            shutil.copy2(ROOT / "pipelines/codex-v1" / name, bundle / name)
        for name in ["anti-ai-slop", "frontend-design", "ui-ux-pro-max"]:
            path = bundle / "skills" / name
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text("Fixture skill\n")
        (self.root / "pipeline.md").write_text("DAILY_SOURCE_OF_TRUTH\n")
        (self.root / "seeds").mkdir()
        (self.root / "seeds/companies.json").write_text('["Fixture"]')
        (self.root / "seeds/subjects.json").write_text('["dogs"]')
        archive = self.root / "pipelines/claude-backup"
        archive.mkdir()
        (archive / "pipeline.md").write_text("ARCHIVED_CLAUDE_PROMPT")
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / "build-entry-metadata.py").write_text("print('metadata OK')\n")
        (scripts / "validate-entry.sh").write_text("test ! -f static-bad\n")
        shutil.copy2(ROOT / "scripts/check-entry-browser.cjs", scripts)
        node = self.bin / "node"
        node.write_text('''#!/usr/bin/env python3
import json,pathlib,sys
if '--preflight' in sys.argv:sys.exit(1 if pathlib.Path('browser-unavailable').exists() else 0)
output=pathlib.Path(sys.argv[-1]);output.mkdir(exist_ok=True)
pages=[]
for filename in ['index.html','demo.html']:
 for width in [1440,390]:
  shot=output/(filename+str(width)+'.png');shot.write_bytes(b'fixture-image')
  pages.append({'filename':filename,'viewport':{'width':width,'height':900},'screenshot':str(shot),'foldScreenshot':str(shot),'failures':[]})
(output/'browser.json').write_text(json.dumps({'passed':True,'pages':pages,'failures':[]}))
''')
        node.chmod(0o755)
        fake = self.bin / "codex"
        fake.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys, time
args=sys.argv[1:]
prompt=sys.stdin.read()
workspace=pathlib.Path(args[args.index('-C')+1])
result=pathlib.Path(args[args.index('--output-last-message')+1])
phase='concept-review' if result.stem.startswith('concept-review-') else 'concept-repair' if result.stem.startswith('concept-repair-') else 'concept' if result.stem=='concept-draft' else 'review' if '--output-schema' in args else 'repair' if result.stem.startswith('repair-') else 'generation'
capture={'args':args,'prompt':prompt,'phase':phase}
with (workspace/'calls.jsonl').open('a') as log:log.write(json.dumps(capture)+'\\n')
if phase=='generation':(workspace/'captured.json').write_text(json.dumps(capture))
print('PRIVATE_TRACE_TOKEN',flush=True)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':5,'cached_input_tokens':3,'reasoning_output_tokens':2}}),flush=True)
def audit(concept):
 targets=[f'features.{i}' for i,_ in enumerate(concept.get('features',[]))]
 targets += [f'pricing_tiers.{i}.perks.{j}' for i,tier in enumerate(concept.get('pricing_tiers',[])) for j,_ in enumerate(tier['perks'])]
 return [{'target':target,'behavior':'Pack barking','mechanic':'Requests','connection':'Dogs submit requests'} for target in targets]
checks={key:True for key in ['comprehension','satire','composition','continuity']}
mode=os.environ.get('FAKE_MODE','success')
qa=os.environ.get('FAKE_QA_MODE','pass')
if phase in ['concept','concept-repair','concept-review']:
 if phase=='concept':
  identity=json.JSONDecoder().raw_decode(prompt.split('FIXED IDENTITY:\\n',1)[1])[0]
  concept={**identity,'product_name':'Fixture','one_liner':'Requests for dogs','brand_voice_notes':'Straight faced','hero':{'h1':'Weak reference','sub':'Pack requests','primary_cta':'Try'},'features':[{'title':'Request','blurb':'The dog requests a walk'} for _ in range(3)],'pricing_tiers':[{'name':'Pack','price':'$3','tagline':'For dogs','perks':['Walk requests','Bark filtering']} for _ in range(3)],'testimonials':[{'quote':'I requested a walk','name':'Dog','title':'Dog'} for _ in range(3)],'demo_screen_concept':'Requests','editorial_plan':{'observations':[{'behavior':'Barks','mechanic':'Requests','consequence':'More walks'} for _ in range(3)],'source_product_patterns':['List','Search','Filter','Submit'],'composition_plan':'Product preview then artwork','audience_design':{'references':[{'reference':'Dog show catalogues','cues':'Portrait framing and ribbons','application':'Portrait record cards'},{'reference':'Dog walking maps','cues':'Green paths','application':'Route navigation'}],'landing_application':'Dog portraits and route graphics','demo_application':'Route cues around a request list'}}}
  result.write_text(json.dumps(concept))
 else:
  data=json.JSONDecoder().raw_decode(prompt.split('HOST CONTEXT:\\n',1)[1])[0] if phase=='concept-review' else json.JSONDecoder().raw_decode(prompt.split('publish.\\n',1)[1])[0]
  concept=data['concept'];cq=os.environ.get('FAKE_CONCEPT_QA','pass')
  if phase=='concept-repair':
   concept['hero']['h1']='Clear request'
   if cq=='identity':concept['product_name']='Changed'
   result.write_text(json.dumps(concept))
  else:
   number=int(result.stem.split('-')[-1]);needed={'once':1,'twice':2,'identity':1}.get(cq,3 if cq=='never' else 0)
   finding={'id':'C1','target':'hero.h1','acceptance':'Understand the request','category':'satire','file':'concept.json','quote':'Weak reference','problem':'Unclear connection','fix':'Use a clear request','patch':{'old':'','new':''}}
   report={'slug':concept['slug'],'verdict':'repair' if number<needed else 'pass','premise':'Dogs request walks','strengths':['Specific'],'checks':checks,'copy_audit':audit(concept),'resolved_findings':['C1'] if number else [],'findings':[finding] if number<needed else []}
   if number<needed:report['resolved_findings']=[]
   result.write_text('not JSON' if cq=='malformed' else json.dumps(report))
 sys.exit(0)
if phase=='generation':
 if mode=='fail':sys.exit(7)
 if mode=='timeout':time.sleep(20)
 entry=workspace/'site/entries/fixture-for-dogs';entry.mkdir(parents=True,exist_ok=True)
 if not (entry/'concept.json').exists():
  concept={'date':'2026-11-01','company':'Fixture','subject':'dogs','slug':entry.name,'product_name':'Fixture','demo_screen_concept':'Requests','design_direction':{'style':'plain'}}
  (entry/'concept.json').write_text(json.dumps(concept))
 concept=json.loads((entry/'concept.json').read_text());concept.setdefault('design_direction',{'style':'plain'});(entry/'concept.json').write_text(json.dumps(concept))
 (entry/'index.html').write_text('Original landing');(entry/'demo.html').write_text('Original demo')
 (workspace/'site/index.html').write_text('New gallery')
 history=workspace/'state/history.json';history.parent.mkdir(exist_ok=True)
 if not history.exists():history.write_text('[{"slug":"fixture-for-dogs"}]')
 result.write_text('RUN_COMPLETE: fixture-for-dogs\\n' if mode=='success' else 'DRAFT_READY: fixture-for-dogs\\n' if mode=='draft' else 'I did not finish.\\n')
elif phase=='review':
 if qa=='review-fail':sys.exit(8)
 if qa=='review-timeout':time.sleep(20)
 number=int(result.stem.split('-')[-1])
 needed={'once':1,'twice':2,'patch':1,'omitted':1,'floor-repair':1}.get(qa,3 if qa in ['never','scope','identity','repair-fail','repair-timeout'] else 0)
 finding={'id':'F1','target':'h1','acceptance':'Understand the request','patch':{'old':'Original landing' if qa=='patch' else '','new':'Repaired landing' if qa=='patch' else ''},'category':'satire','file':'site/entries/fixture-for-dogs/index.html','quote':'Weak reference','problem':'Unclear connection','fix':'Make the mapping explicit'}
 report={'slug':'fixture-for-dogs','verdict':'repair' if number<needed else 'pass','quality_floor':{'reference_id':'again-2026-11-11-approved','assessments':{key:{'meets':True,'evidence':'Specific requests, purposeful visuals and usable controls meet the reference standard.'} for key in ['comprehension','satire','composition','continuity']}},'premise':'Dogs submit requests.','strengths':['Specific subject'],'checks':checks,'visual_audit':[{'page':p,'viewport':v,'dominant_content':'Requests','product_visual':'Request list','caption_legibility':'Readable','comprehension_pass':True,'audience_cues':'Dog portrait framing and green route cues','audience_fit_pass':True} for p in ['index.html','demo.html'] for v in ['desktop','mobile']],'copy_audit':audit(json.loads((workspace/'site/entries/fixture-for-dogs/concept.json').read_text())),'resolved_findings':['F1'] if number>0 and number>=needed and qa!='omitted' else [],
         'findings':[finding] if number<needed else [],'demo_test':{'actions':[{'action':'click','selector':'#submit','value':'-'}],'assertions':[{'check':'visible','selector':'#result','expected':'-'}]}}
 if qa=='below-floor' or (qa=='floor-repair' and number==0):report['quality_floor']['assessments']['composition']['meets']=False
 if qa=='bad-pass':report['findings']=[finding]
 if qa=='no-interaction':report['demo_test']['actions']=[]
 if qa=='empty-input':
  report['demo_test']['actions']=[{'action':'fill','selector':'#post-text','value':''},{'action':'click','selector':'#submit','value':''}]
  report['demo_test']['assertions']=[{'check':'value','selector':'#post-text','expected':''}]
 result.write_text('not JSON' if qa=='malformed' else json.dumps(report))
else:
 (workspace/'site/entries/fixture-for-dogs/index.html').write_text('Repaired landing')
 if qa=='scope':(workspace/'pipeline.md').write_text('Corrupted prompt')
 if qa=='identity':
  concept=workspace/'site/entries/fixture-for-dogs/concept.json';data=json.loads(concept.read_text());data['product_name']='Different';concept.write_text(json.dumps(data))
 if qa=='repair-fail':sys.exit(9)
 if qa=='repair-timeout':time.sleep(20)
 if qa!='no-fix':(workspace/'static-bad').unlink(missing_ok=True)
 result.write_text('Repaired the reported defect.\\n')
''')
        fake.chmod(0o755)
        claude = self.bin / "claude"
        claude.write_text('''#!/usr/bin/env python3
import sys
assert sys.argv[sys.argv.index('-p')+1]=='ARCHIVED_CLAUDE_PROMPT'
assert sys.argv[sys.argv.index('--max-turns')+1]=='80'
print('RUN_COMPLETE: claude-for-dogs')
''')
        claude.chmod(0o755)

    def invoke(self, mode="success", engine="codex", preflight=False, recover_today=None, qa="pass", qa_existing=None, concept_qa="pass"):
        env = os.environ.copy()
        env.update(PATH=str(self.bin) + os.pathsep + env["PATH"], FAKE_MODE=mode, FAKE_QA_MODE=qa, FAKE_CONCEPT_QA=concept_qa)
        args = [sys.executable, str(RUNNER), "--engine", engine, "--workspace", str(self.root)]
        if preflight:
            args.append("--preflight")
        if recover_today:
            args.extend(["--recover-today", recover_today])
        if qa_existing:
            args.extend(["--qa-existing", qa_existing])
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=10)

    def test_preferred_model_prompt_and_private_trace(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        captured = json.loads((self.root / "captured.json").read_text())
        self.assertIn("DAILY_SOURCE_OF_TRUTH", captured["prompt"])
        self.assertIn('model_reasoning_effort="high"', captured["args"])
        self.assertIn("sandbox_workspace_write.network_access=true", captured["args"])
        self.assertEqual(captured["args"][captured["args"].index("--model") + 1], "gpt-6.1-sol")
        self.assertIn("RUN_COMPLETE: fixture-for-dogs", result.stdout)
        self.assertNotIn("PRIVATE_TRACE_TOKEN", result.stdout + result.stderr)
        traces = list((self.root / ".tmp-codex").glob("*/trace.log"))
        self.assertEqual(len(traces), 1)
        self.assertIn("PRIVATE_TRACE_TOKEN", traces[0].read_text())
        self.assertEqual((self.root / ".tmp-codex").stat().st_mode & 0o777, 0o700)

    def test_failed_cli_cannot_report_success(self):
        result = self.invoke("fail")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("RUN_COMPLETE:", result.stdout)
        self.assertNotIn("PRIVATE_TRACE_TOKEN", result.stdout + result.stderr)

    def test_missing_completion_marker_rejects_publication(self):
        result = self.invoke("incomplete")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing publication", result.stderr)

    def test_timeout_stops_the_generator(self):
        config = json.loads(self.config.read_text())
        config["timeout_seconds"] = 0.1
        self.config.write_text(json.dumps(config))
        result = self.invoke("timeout")
        self.assertEqual(result.returncode, 124)
        self.assertIn("timed out", result.stderr)

    def test_claude_fallback_uses_archived_prompt(self):
        result = self.invoke(engine="claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RUN_COMPLETE: claude-for-dogs", result.stdout)

    def test_preflight_does_not_invoke_generator(self):
        result = self.invoke(preflight=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "captured.json").exists())
        self.assertFalse((self.root / ".tmp-codex").exists())

    def test_missing_browser_stops_before_spending_on_generation(self):
        (self.root / "browser-unavailable").touch()
        for preflight in [True, False]:
            with self.subTest(preflight=preflight):
                result = self.invoke(preflight=preflight)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("browser preflight failed", result.stderr)
                self.assertFalse((self.root / "calls.jsonl").exists())

    def recovery_fixture(self, duplicate=False):
        from datetime import datetime, timezone
        concept = {"date": datetime.now(timezone.utc).date().isoformat(), "company": "Fixture", "subject": "dogs", "slug": "fixture-for-dogs", "product_name": "Fixture", "demo_screen_concept": "A request table", "design_direction": {"style": "plain"}}
        entry = self.root / "site/entries/fixture-for-dogs"
        entry.mkdir(parents=True)
        (entry / "concept.json").write_text(json.dumps(concept))
        (self.root / "state").mkdir()
        history = [{key: concept[key] for key in ["date", "company", "subject", "slug"]}]
        if duplicate:
            history.append(history[0].copy())
        path = self.root / "state/history.json"
        path.write_text(json.dumps(history, indent=2) + "\n")
        return path.read_bytes()

    def phases(self):
        return [json.loads(line)["phase"] for line in (self.root / "calls.jsonl").read_text().splitlines()]

    def test_initial_qa_pass_has_no_repairs_and_uses_read_only_schema(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["generation", "review"])
        call = json.loads((self.root / "calls.jsonl").read_text().splitlines()[-1])
        self.assertIn("--output-schema", call["args"])
        self.assertEqual(call["args"].count("--image"), 9)
        self.assertIn("approved_quality_floor", call["prompt"])
        self.assertIn("quality_reference", call["prompt"])
        self.assertEqual(call["args"][call["args"].index("--sandbox") + 1], "read-only")

    def enable_checkpoint(self):
        config = json.loads(self.config.read_text())
        config["concept_checkpoint"] = {"enabled": True, "draft_timeout_seconds": 3,
                                         "review_timeout_seconds": 3, "repair_timeout_seconds": 3}
        config["usage"] = {"require_events": True, "max_total_tokens": None, "max_stage_tokens": {}}
        self.config.write_text(json.dumps(config))

    def test_concept_pass_precedes_build_and_accounts_each_stage(self):
        self.enable_checkpoint()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["concept", "concept-review", "generation", "review"])
        calls = [json.loads(line) for line in (self.root / "calls.jsonl").read_text().splitlines()]
        for call in calls[:2]:
            self.assertEqual(call["args"][call["args"].index("--sandbox") + 1], "read-only")
        self.assertIn("Start at Step 3", calls[2]["prompt"])
        usage = json.loads(next((self.root / ".tmp-codex").glob("*/usage.json")).read_text())
        self.assertEqual(usage["total_tokens"], 60)
        self.assertEqual(sum(stage["cached_input_tokens"] for stage in usage["stages"]), 12)
        self.assertEqual(sum(stage["reasoning_output_tokens"] for stage in usage["stages"]), 8)

    def test_concept_and_final_share_two_repairs(self):
        self.enable_checkpoint()
        result = self.invoke(concept_qa="once", qa="once")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["concept", "concept-review", "concept-repair", "concept-review",
                                        "generation", "review", "repair", "review"])
        ledger = json.loads(next((self.root / ".tmp-codex").glob("*/repair-budget.json")).read_text())
        self.assertEqual([item["stage"] for item in ledger], ["concept", "final"])
        summary = json.loads(next((self.root / ".tmp-codex").glob("*/qa-summary.json")).read_text())
        self.assertEqual(summary["repair_attempts"], 2)

    def test_concept_exhaustion_stops_before_assets_and_build(self):
        self.enable_checkpoint()
        result = self.invoke(concept_qa="never")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.phases().count("concept-repair"), 2)
        self.assertNotIn("generation", self.phases())
        self.assertFalse((self.root / "site/entries/fixture-for-dogs").exists())
        self.assertNotIn("RUN_COMPLETE:", result.stdout)

    def test_final_cannot_obtain_more_repairs_after_concept_uses_both(self):
        self.enable_checkpoint()
        result = self.invoke(concept_qa="twice", qa="once")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.phases().count("concept-repair"), 2)
        self.assertNotIn("repair", self.phases())
        self.assertNotIn("RUN_COMPLETE:", result.stdout)
        self.assertFalse((self.root / "site/entries/fixture-for-dogs").exists())

    def test_bad_concept_review_or_identity_change_stops_before_build(self):
        self.enable_checkpoint()
        for mode in ("malformed", "identity"):
            with self.subTest(mode=mode):
                (self.root / "calls.jsonl").unlink(missing_ok=True)
                result = self.invoke(concept_qa=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("generation", self.phases())

    def test_usage_exhaustion_prevents_next_invocation(self):
        self.enable_checkpoint()
        config = json.loads(self.config.read_text())
        config["usage"]["max_total_tokens"] = 15
        self.config.write_text(json.dumps(config))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.phases(), ["concept"])
        self.assertIn("allowance exhausted", result.stderr)

    def test_exact_patch_skips_repair_model_but_requires_fresh_review(self):
        result = self.invoke(qa="patch")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["generation", "review", "review"])
        self.assertEqual((self.root / "site/entries/fixture-for-dogs/index.html").read_text(), "Repaired landing")
        self.assertIn("passed after 1 repair", result.stdout)

    def test_verifier_cannot_silently_drop_a_finding(self):
        result = self.invoke(qa="omitted")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("omitted an earlier finding", result.stderr)

    def test_passing_checks_cannot_waive_a_lower_quality_than_the_approved_entry(self):
        result = self.invoke(qa="below-floor")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("below the user-approved quality floor", result.stderr)
        self.assertNotIn("RUN_COMPLETE:", result.stdout)
        self.assertFalse((self.root / "site/entries/fixture-for-dogs").exists())

    def test_missing_or_changed_reference_stops_preflight_before_model_spend(self):
        reference = self.root / "pipelines/codex-v1/reference/again-approved/desktop-opening.png"
        reference.write_bytes(reference.read_bytes() + b'changed')
        result = self.invoke(preflight=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("quality floor image missing or changed", result.stderr)
        self.assertFalse((self.root / "calls.jsonl").exists())

    def test_quality_floor_shortfall_can_be_repaired_and_verified_within_allowance(self):
        result = self.invoke(qa="floor-repair")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["generation", "review", "repair", "review"])
        run = next((self.root / ".tmp-codex").glob("*/qa-summary.json")).parent
        before = json.loads((run / "review-0.json").read_text())
        after = json.loads((run / "review-1.json").read_text())
        self.assertFalse(before["quality_floor"]["assessments"]["composition"]["meets"])
        self.assertTrue(after["quality_floor"]["assessments"]["composition"]["meets"])
        self.assertEqual(json.loads((run / "qa-summary.json").read_text())["repair_attempts"], 1)

    def test_reference_is_pinned_independently_of_catalogue_rotation(self):
        floor, images = quality_floor_context(self.root)
        self.assertEqual(floor["id"], "again-2026-11-11-approved")
        self.assertEqual(len(images), 3)
        self.assertFalse((self.root / "site/entries/youtube-for-crossfit-junkies").exists())
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        prompt = json.loads((self.root / "captured.json").read_text())["prompt"]
        self.assertIn("HOST APPROVED QUALITY FLOOR", prompt)
        self.assertIn("again-2026-11-11-approved", prompt)

    def test_copy_audit_and_separate_acceptance_checks_are_enforced(self):
        with self.assertRaises(ValueError):
            validate_copy_audit({"copy_audit": []}, {"features": [{}]})
        with self.assertRaises(ValueError):
            validate_verdict({"verdict": "pass", "findings": [], "checks": {"composition": False},
                              "resolved_findings": []})

    def test_visual_audit_cannot_omit_a_page_or_contradict_composition(self):
        with self.assertRaises(ValueError):
            validate_visual_audit({"visual_audit": [], "checks": {"composition": True}})
        audit = [{"page": page, "viewport": viewport, "comprehension_pass": True, "audience_fit_pass": True}
                 for page in ["index.html", "demo.html"] for viewport in ["desktop", "mobile"]]
        audit[0]["comprehension_pass"] = False
        with self.assertRaises(ValueError):
            validate_visual_audit({"visual_audit": audit, "checks": {"composition": True}})

    def test_audience_mismatch_cannot_pass_composition(self):
        audit = [{"page": page, "viewport": viewport, "comprehension_pass": True,
                  "audience_fit_pass": True}
                 for page in ["index.html", "demo.html"] for viewport in ["desktop", "mobile"]]
        validate_visual_audit({"visual_audit": audit, "checks": {"composition": True}})
        audit[2]["audience_fit_pass"] = False
        with self.assertRaisesRegex(ValueError, "audience fit"):
            validate_visual_audit({"visual_audit": audit, "checks": {"composition": True}})
        # A repair verdict may honestly report the failed audience fit.
        validate_visual_audit({"visual_audit": audit, "checks": {"composition": False}})
        del audit[2]["audience_fit_pass"]
        with self.assertRaisesRegex(ValueError, "audience fit"):
            validate_visual_audit({"visual_audit": audit, "checks": {"composition": True}})

    def test_concept_needs_concrete_audience_references_before_build(self):
        schema = CONCEPT_SCHEMA["properties"]["editorial_plan"]["properties"]["audience_design"]
        valid = {"references": [{"reference": "Album inserts", "cues": "Card frames",
                                 "application": "Member cards"},
                                {"reference": "Music release posters", "cues": "Bold typography",
                                 "application": "Hero and booking header"}],
                 "landing_application": "Fan identity around product preview",
                 "demo_application": "Workspace booking with album colors"}
        validate_shape(valid, schema)
        valid["references"].pop()
        with self.assertRaises(ValueError):
            validate_shape(valid, schema)
        with self.assertRaises(ValueError):
            validate_shape({}, schema)

    def test_literal_patch_batch_is_all_or_nothing(self):
        entry = self.root / "site/entries/fixture-for-dogs"
        entry.mkdir(parents=True)
        target = entry / "index.html"
        target.write_text("Old heading. Old caption.")
        findings = [{"file": "site/entries/fixture-for-dogs/index.html", "patch": patch} for patch in
                    [{"old": "Old heading", "new": "New heading"}, {"old": "Absent", "new": "New caption"}]]
        self.assertFalse(apply_exact_patches(self.root, "fixture-for-dogs", findings))
        self.assertEqual(target.read_text(), "Old heading. Old caption.")
        findings[1]["patch"]["old"] = "Old caption"
        self.assertTrue(apply_exact_patches(self.root, "fixture-for-dogs", findings))
        self.assertEqual(target.read_text(), "New heading. New caption.")
        findings[0]["file"] = "pipeline.md"
        self.assertFalse(apply_exact_patches(self.root, "fixture-for-dogs", findings))

    def test_usage_missing_events_and_stage_limit_fail_closed(self):
        trace = self.root / "events.log"
        trace.write_text('noise\\n')
        usage = UsageLedger(self.root, {"usage": {"require_events": True}})
        with self.assertRaises(StageFailure):
            usage.record("review-0", trace)
        usage = UsageLedger(self.root, {"usage": {"max_total_tokens": 100}})
        with self.assertRaises(StageFailure):
            usage.record("review-0", trace)
        trace.write_text(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5,
                                                                         "cached_input_tokens": 9, "reasoning_output_tokens": 3}}) + "\n")
        usage = UsageLedger(self.root, {"usage": {"max_stage_tokens": {"review": 15}}})
        with self.assertRaises(StageFailure):
            usage.record("review-0", trace)
        self.assertEqual(usage.total, 15)

    def test_review_packet_omits_styles_and_metadata_but_keeps_feedback(self):
        entry = self.root / "site/entries/fixture-for-dogs"
        entry.mkdir(parents=True)
        (entry / "index.html").write_text('<html><head><title>Duplicate</title><style>STYLE</style></head><body><h1>Visible</h1></body></html>')
        (entry / "demo.html").write_text('<html><body><button id="go">Go</button><script>status.textContent="Feedback"</script></body></html>')
        packet = review_packet(self.root, "fixture-for-dogs", self.root).read_text()
        self.assertIn("Visible", packet)
        self.assertIn("Feedback", packet)
        self.assertNotIn("STYLE", packet)
        self.assertNotIn("Duplicate", packet)

    def test_roll_is_deterministic_and_exhaustion_does_not_overwrite(self):
        self.assertEqual(roll(self.root), roll(self.root))
        (self.root / "state").mkdir()
        (self.root / "state/history.json").write_text('[{"company":"Fixture","subject":"dogs"}]')
        with self.assertRaises(StageFailure):
            roll(self.root)

    def test_empty_input_values_reach_the_host_interaction_check(self):
        result = self.invoke(qa="empty-input")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["generation", "review"])
        summary = json.loads(next((self.root / ".tmp-codex").glob("*/qa-summary.json")).read_text())
        self.assertEqual(summary["status"], "passed")
        technical = json.loads(next((self.root / ".tmp-codex").glob("*/checks-0/technical.json")).read_text())
        self.assertTrue(any(check["name"] == "interaction" and check["passed"] for check in technical["checks"]))

    def test_empty_values_do_not_allow_invalid_review_fields(self):
        result = self.invoke(qa="empty-input")
        self.assertEqual(result.returncode, 0, result.stderr)
        path = next((self.root / ".tmp-codex").glob("*/review-0.json"))
        report = json.loads(path.read_text())
        for field, value in [("premise", ""), ("premise", "  "), ("selector", ""),
                             ("value", None), ("expected", None), ("press", ""),
                             ("text", ""), ("count", "")]:
            with self.subTest(field=field, value=value):
                invalid = json.loads(json.dumps(report))
                if field == "premise":
                    invalid[field] = value
                elif field in {"selector", "value"}:
                    invalid["demo_test"]["actions"][0][field] = value
                elif field == "expected":
                    invalid["demo_test"]["assertions"][0][field] = value
                elif field == "press":
                    invalid["demo_test"]["actions"][0].update(action=field, value=value)
                else:
                    invalid["demo_test"]["assertions"][0].update(check=field, expected=value)
                path.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    read_review(path, "fixture-for-dogs")

    def test_review_schema_distinguishes_selectors_from_input_values(self):
        schema = review_schema("fixture-for-dogs")["properties"]["demo_test"]["properties"]
        self.assertEqual(schema["actions"]["items"]["properties"]["selector"]["minLength"], 1)
        self.assertEqual(schema["actions"]["items"]["properties"]["value"]["minLength"], 0)
        self.assertEqual(schema["assertions"]["items"]["properties"]["expected"]["minLength"], 0)

    def test_repairs_recheck_and_stop_as_soon_as_passed(self):
        result = self.invoke(qa="once")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["generation", "review", "repair", "review"])
        self.assertIn("passed after 1 repair", result.stdout)

    def test_second_attempt_can_pass_but_no_third_repair_is_possible(self):
        result = self.invoke(qa="twice")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["generation", "review", "repair", "review", "repair", "review"])
        summary = json.loads(next((self.root / ".tmp-codex").glob("*/qa-summary.json")).read_text())
        self.assertEqual(summary["repair_attempts"], 2)
        self.assertEqual(summary["status"], "passed")

    def test_exhausted_repairs_quarantine_draft_and_restore_gallery_history(self):
        (self.root / "site/entries").mkdir(parents=True)
        (self.root / "site/index.html").write_text("Original gallery")
        (self.root / "state").mkdir()
        (self.root / "state/history.json").write_text("[]\n")
        result = self.invoke(qa="never")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.phases().count("repair"), 2)
        self.assertEqual(self.phases().count("review"), 3)
        self.assertNotIn("RUN_COMPLETE:", result.stdout)
        self.assertFalse((self.root / "site/entries/fixture-for-dogs").exists())
        self.assertEqual((self.root / "site/index.html").read_text(), "Original gallery")
        self.assertEqual((self.root / "state/history.json").read_text(), "[]\n")
        self.assertTrue(list((self.root / ".tmp-codex").glob("*/rejected/fixture-for-dogs/index.html")))

    def test_invalid_reviews_and_failed_processes_fail_closed(self):
        for mode in ["malformed", "bad-pass", "no-interaction", "review-fail", "repair-fail"]:
            with self.subTest(mode=mode):
                result = self.invoke(qa=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("RUN_COMPLETE:", result.stdout)
                self.assertFalse((self.root / "site/entries/fixture-for-dogs").exists())

    def test_technical_failure_cannot_be_waived_by_model_pass(self):
        (self.root / "static-bad").touch()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["generation", "review", "repair", "review"])

    def test_human_finding_is_healed_even_when_model_review_omits_it(self):
        ledger = {"fixture-for-dogs": [{"id": "human-feedback", "reason": "This phrase was explicitly rejected",
                                       "rejected_phrases": ["Original landing"]}]}
        (self.root / "pipelines/codex-v1/editorial-regressions.json").write_text(json.dumps(ledger))
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phases(), ["generation", "review", "repair", "review"])
        report = json.loads(next((self.root / ".tmp-codex").glob("*/checks-0/editorial-regressions.json")).read_text())
        self.assertFalse(report["passed"])
        self.assertEqual(report["checks"][0]["matches"][0]["quote"], "Original landing")

    def test_unresolved_human_finding_blocks_a_passing_model_verdict(self):
        ledger = {"fixture-for-dogs": [{"id": "human-feedback", "reason": "Still unresolved after repair",
                                       "rejected_phrases": ["landing"]}]}
        (self.root / "pipelines/codex-v1/editorial-regressions.json").write_text(json.dumps(ledger))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.phases().count("repair"), 2)
        self.assertNotIn("RUN_COMPLETE:", result.stdout)

    def test_complete_draft_with_validation_failure_enters_the_bounded_heal(self):
        (self.root / "static-bad").touch()
        result = self.invoke(mode="draft")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RUN_COMPLETE: fixture-for-dogs", result.stdout)
        self.assertNotIn("DRAFT_READY:", result.stdout)
        self.assertEqual(self.phases(), ["generation", "review", "repair", "review"])

    def test_persistent_technical_failure_blocks_even_with_passing_reviews(self):
        (self.root / "static-bad").touch()
        result = self.invoke(qa="no-fix")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.phases().count("repair"), 2)
        self.assertNotIn("RUN_COMPLETE:", result.stdout)

    def test_overall_budget_bounds_a_longer_generation_allowance(self):
        import time
        config = json.loads(self.config.read_text())
        config["qa"]["total_timeout_seconds"] = 0.1
        self.config.write_text(json.dumps(config))
        started = time.monotonic()
        result = self.invoke(mode="timeout")
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertLess(time.monotonic() - started, 2)

    def test_repair_scope_violation_is_restored_and_rejected(self):
        result = self.invoke(qa="scope")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / "pipeline.md").read_text(), "DAILY_SOURCE_OF_TRUTH\n")
        self.assertIn("protected content", result.stderr)

    def test_repair_cannot_change_identity(self):
        result = self.invoke(qa="identity")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("product identity", result.stderr)

    def test_existing_draft_restored_after_qa_failure(self):
        history = self.recovery_fixture()
        entry = self.root / "site/entries/fixture-for-dogs"
        (entry / "index.html").write_text("Keep this original")
        original_concept = (entry / "concept.json").read_bytes()
        result = self.invoke(qa="never", qa_existing="fixture-for-dogs")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.phases().count("generation"), 0)
        self.assertEqual((entry / "index.html").read_text(), "Keep this original")
        self.assertEqual((entry / "concept.json").read_bytes(), original_concept)
        self.assertEqual((self.root / "state/history.json").read_bytes(), history)

    def test_review_and_repair_timeouts_fail_without_publishing(self):
        config = json.loads(self.config.read_text())
        config["qa"].update(review_timeout_seconds=0.1, repair_timeout_seconds=0.1)
        self.config.write_text(json.dumps(config))
        for mode in ["review-timeout", "repair-timeout"]:
            with self.subTest(mode=mode):
                result = self.invoke(qa=mode)
                self.assertEqual(result.returncode, 124, result.stderr)
                self.assertNotIn("RUN_COMPLETE:", result.stdout)

    def test_configuration_cannot_increase_attempts_above_two(self):
        config = json.loads(self.config.read_text())
        config["qa"]["max_repair_attempts"] = 3
        self.config.write_text(json.dumps(config))
        result = self.invoke(preflight=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "calls.jsonl").exists())

    def test_recovery_keeps_history_and_records_codex_provenance(self):
        history = self.recovery_fixture()
        result = self.invoke(recover_today="fixture-for-dogs")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "state/history.json").read_bytes(), history)
        concept = json.loads((self.root / "site/entries/fixture-for-dogs/concept.json").read_text())
        self.assertEqual(concept["generation"]["engine"], "codex")
        prompt = json.loads((self.root / "captured.json").read_text())["prompt"]
        self.assertIn("Leave state/history.json byte-for-byte", prompt)

    def test_recovery_rejects_ambiguous_history_before_running_codex(self):
        self.recovery_fixture(duplicate=True)
        result = self.invoke(recover_today="fixture-for-dogs")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one matching", result.stderr)
        self.assertFalse((self.root / "captured.json").exists())


if __name__ == "__main__":
    unittest.main()
