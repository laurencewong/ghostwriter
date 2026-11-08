"""Tests for scripts/ghostwriter.py. Run: python3 -m unittest discover -s tests"""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ghostwriter as gw  # noqa: E402

DEMO = ROOT / "examples" / "demo-book"

GOOD = """---
chapter: ch01
thesis_role: advances
claim: Shared tools beat owned tools for occasional jobs.
---

# Chapter

The drill went out 96 times. [S001] I think that matters. [opinion]

## The strongest objection

Owning a tool means you never wait for it, and for people with no slack in their week that
certainty is worth more than any saving. The library runs on its schedule, not yours, and the
people who most need certainty are the ones least able to plan around a pickup window. Calling
an idle tool waste ignores what the idle time buys, which is the ability to act right away.

## Where this leaves the thesis

Advanced, with a fence around emergency tools. [opinion]
"""


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = gw.main(list(args))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class BookTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.book = self.tmp / "book"
        code, _, _ = run_cli("init", str(self.book), "--title", "T", "--author", "A")
        self.assertEqual(code, 0)
        src = self.tmp / "data.md"
        src.write_text("Fictional data: the drill went out 96 times.\n")
        code, out, _ = run_cli("add-source", str(self.book), str(src), "--kind", "dataset", "--title", "Log")
        self.assertEqual(code, 0)
        self.assertIn("S001", out)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def draft(self, text, name="d.md"):
        p = self.tmp / name
        p.write_text(text)
        return p


class TestInitAndSources(BookTestCase):
    def test_init_creates_workspace(self):
        cfg = json.loads((self.book / "ghostwriter.json").read_text())
        self.assertEqual(cfg["author"], "A")
        for p in ("thesis.md", "spine.md", "interview/questions.md", "sources/index.json"):
            self.assertTrue((self.book / p).exists(), p)

    def test_init_refuses_existing(self):
        code, _, _ = run_cli("init", str(self.book))
        self.assertNotEqual(code, 0)

    def test_source_ids_increment_and_origin_is_not_a_full_path(self):
        src = self.tmp / "note.md"
        src.write_text("a note")
        run_cli("add-source", str(self.book), str(src), "--kind", "note")
        idx = json.loads((self.book / "sources/index.json").read_text())
        self.assertEqual([s["id"] for s in idx["sources"]], ["S001", "S002"])
        self.assertEqual(idx["sources"][1]["origin"], "note.md")

    def test_pointer_source_does_not_copy(self):
        src = self.tmp / "secret.md"
        src.write_text("PRIVATE CONTENT")
        run_cli("add-source", str(self.book), str(src), "--kind", "note", "--pointer")
        rec = (self.book / "sources" / "S002.md").read_text()
        self.assertNotIn("PRIVATE CONTENT", rec)
        self.assertIn("pointer", rec)

    def test_bad_kind_rejected(self):
        code, _, _ = run_cli("add-source", str(self.book), "x", "--kind", "rumor")
        self.assertNotEqual(code, 0)


class TestInterview(BookTestCase):
    def test_file_answer_becomes_source_and_closes_question(self):
        qf = self.book / "interview" / "questions.md"
        qf.write_text(qf.read_text() + "- [ ] Q001 (ch01) Tell me about the ladder.\n")
        ans = self.tmp / "a.txt"
        ans.write_text("I bought it twice.")
        code, out, _ = run_cli("interview-file", str(self.book), "Q001", "--answer-file", str(ans))
        self.assertEqual(code, 0)
        self.assertIn("S002", out)
        self.assertIn("- [x] Q001", qf.read_text())
        code, _, _ = run_cli("interview-file", str(self.book), "Q001", "--answer-file", str(ans))
        self.assertNotEqual(code, 0, "answering twice should fail")


class TestProvenance(BookTestCase):
    def test_good_draft_passes(self):
        rep = gw.provenance_report(self.book, self.draft(GOOD))
        self.assertTrue(rep["pass"], rep)

    def test_trailing_citation_binds_to_previous_sentence(self):
        rep = gw.provenance_report(self.book, self.draft("Loans hit 96. [S001] Then it rained.\n"))
        self.assertTrue(rep["pass"], rep)

    def test_uncited_number_fails(self):
        rep = gw.provenance_report(self.book, self.draft("The average drill is used for 13 minutes.\n"))
        self.assertFalse(rep["pass"])
        self.assertEqual(len(rep["unsupported"]), 1)

    def test_unknown_source_id_fails(self):
        rep = gw.provenance_report(self.book, self.draft("Loans hit 96. [S999]\n"))
        self.assertEqual(rep["unknown_ids"], ["S999"])
        self.assertFalse(rep["pass"])

    def test_needs_source_marker_fails(self):
        rep = gw.provenance_report(self.book, self.draft("Libraries are older than we think [NEEDS SOURCE: founding date].\n"))
        self.assertFalse(rep["pass"])

    def test_cross_reference_is_not_a_claim(self):
        rep = gw.provenance_report(self.book, self.draft("Chapter 3 picks this up.\n"))
        self.assertTrue(rep["pass"], rep)

    def test_opinion_tag_counts(self):
        rep = gw.provenance_report(self.book, self.draft("Most people own too much. [opinion]\n"))
        self.assertTrue(rep["pass"])
        self.assertEqual(rep["opinion"], 1)


class TestAiTells(BookTestCase):
    def test_hard_tell_fails(self):
        rep = gw.ai_tell_report(self.draft("Let us delve into the tapestry of tools.\n"))
        self.assertFalse(rep["pass"])
        self.assertTrue(rep["hard"])

    def test_imitation_request_is_a_hard_tell(self):
        rep = gw.ai_tell_report(self.draft("Write this in the style of a famous novelist.\n"))
        self.assertFalse(rep["pass"])

    def test_clean_prose_passes(self):
        self.assertTrue(gw.ai_tell_report(self.draft(GOOD))["pass"])


class TestThesis(BookTestCase):
    def test_good_passes(self):
        self.assertTrue(gw.thesis_report(self.draft(GOOD))["pass"])

    def test_missing_role_and_objection_fails(self):
        rep = gw.thesis_report(self.draft("---\nclaim: x\n---\n\nJust a case for.\n"))
        self.assertFalse(rep["pass"])
        self.assertGreaterEqual(len(rep["problems"]), 3)

    def test_thin_objection_fails(self):
        thin = GOOD.split("## The strongest objection")[0] + "## The strongest objection\n\nSome disagree.\n\n## Where this leaves the thesis\n\nFine.\n"
        rep = gw.thesis_report(self.draft(thin))
        self.assertFalse(rep["pass"])


class TestVoice(BookTestCase):
    def test_voice_build_from_own_samples(self):
        (self.book / "voice" / "samples" / "p1.md").write_text("I like tools. I borrow them. Do you?\n\nI'm sure.")
        code, _, _ = run_cli("voice-build", str(self.book))
        self.assertEqual(code, 0)
        prof = json.loads((self.book / "voice" / "profile.json").read_text())
        self.assertGreater(prof["sentences"], 0)

    def test_voice_refuses_other_writers(self):
        cfg_path = self.book / "ghostwriter.json"
        cfg = json.loads(cfg_path.read_text())
        cfg["voice"]["samples"] = [{"path": "voice/samples/*.md", "owner": "someone-else"}]
        cfg_path.write_text(json.dumps(cfg))
        code, _, err = run_cli("voice-build", str(self.book))
        self.assertNotEqual(code, 0)
        self.assertIn("own writing", err)

    def test_voice_reads_jsonl(self):
        (self.book / "voice" / "posts.jsonl").write_text(json.dumps({"text": "Short one. Another short one."}) + "\n")
        cfg_path = self.book / "ghostwriter.json"
        cfg = json.loads(cfg_path.read_text())
        cfg["voice"]["samples"] = [{"path": "voice/posts.jsonl", "owner": "self"}]
        cfg_path.write_text(json.dumps(cfg))
        self.assertEqual(run_cli("voice-build", str(self.book))[0], 0)


class TestTournamentAndPromote(BookTestCase):
    def test_promote_only_gate_passing_drafts(self):
        d = self.book / "drafts" / "ch01"
        d.mkdir(parents=True)
        (d / "run-1.md").write_text(GOOD)
        (d / "run-2.md").write_text(GOOD.replace("[S001]", ""))
        code, out, _ = run_cli("tournament", str(self.book), "ch01")
        self.assertEqual(code, 0)
        self.assertIn("eligible: run-1", out)
        self.assertNotEqual(run_cli("promote", str(self.book), "ch01", "run-2")[0], 0)
        self.assertEqual(run_cli("promote", str(self.book), "ch01", "run-1")[0], 0)
        self.assertTrue((self.book / "chapters" / "ch01.md").exists())

    def test_tournament_keeps_judge_verdict(self):
        d = self.book / "drafts" / "ch01"
        d.mkdir(parents=True)
        (d / "run-1.md").write_text(GOOD)
        run_cli("tournament", str(self.book), "ch01")
        sb = d / "scoreboard.md"
        sb.write_text(sb.read_text().split("## Judge verdict")[0] + "## Judge verdict\n\nWinner: run-1.\n")
        run_cli("tournament", str(self.book), "ch01")
        self.assertIn("Winner: run-1.", sb.read_text())


class TestDemoBook(unittest.TestCase):
    def test_demo_chapter_passes_every_gate(self):
        g = gw.gate_all(DEMO, DEMO / "chapters" / "ch01.md")
        self.assertTrue(g["pass"], g)

    def test_demo_failing_draft_still_fails(self):
        self.assertFalse(gw.gate_all(DEMO, DEMO / "drafts" / "ch01" / "run-2.md")["pass"])

    def test_demo_is_labeled_fictional(self):
        cfg = json.loads((DEMO / "ghostwriter.json").read_text())
        self.assertIn("fictional", cfg["author"].lower())
        for s in json.loads((DEMO / "sources" / "index.json").read_text())["sources"]:
            if s["kind"] != "interview":
                self.assertIn("fictional", (s["title"] + s["origin"]).lower(), s["id"])


class TestBoundaryHook(unittest.TestCase):
    @unittest.skipUnless(shutil.which("jq"), "jq not installed")
    def test_boundary_suite_passes(self):
        r = subprocess.run(["bash", str(ROOT / "tests" / "test_boundary_lite.sh")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
