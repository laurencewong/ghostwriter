"""Tests for scripts/ghostwriter.py. Run: python3 -m unittest discover -s tests"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

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
        self.set_phase("writing")   # most tests exercise drafting; phase gating has its own tests
        src = self.tmp / "data.md"
        src.write_text("Fictional data: the drill went out 96 times.\n")
        code, out, _ = run_cli("add-source", str(self.book), str(src), "--kind", "dataset", "--title", "Log")
        self.assertEqual(code, 0)
        self.assertIn("S001", out)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def set_phase(self, phase):
        cfg_path = self.book / "ghostwriter.json"
        cfg = json.loads(cfg_path.read_text())
        cfg["phase"] = phase
        cfg_path.write_text(json.dumps(cfg))

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


DEMO_R = ROOT / "examples" / "demo-research"


def grid(**over):
    """A tiny coverage file: 2 mechanisms x 3 situations = 6 cells."""
    d = {"title": "t", "mode": "grid",
         "framework": {"name": "A stage model", "citation": "Someone (2000), fictional"},
         "mechanisms": [{"code": "M1", "name": "one"}, {"code": "M2", "name": "two"}],
         "situations": [{"code": "S1", "name": "a"}, {"code": "S2", "name": "b"}, {"code": "S3", "name": "c"}],
         "cells": [{"situation": "S1", "mechanism": "M1", "status": "filled", "practice": "p", "evidence": "M"},
                   {"situation": "S1", "mechanism": "M2", "status": "na"},
                   {"situation": "S2", "mechanism": "M1", "status": "dup", "dup_of": "S1xM1"},
                   {"situation": "S2", "mechanism": "M2", "status": "empty", "priority": 2, "why": "second"},
                   {"situation": "S3", "mechanism": "M1", "status": "empty", "priority": 1, "why": "first"}],
         "items": []}
    d.update(over)
    return d


class TestPhaseGating(BookTestCase):
    def test_new_book_starts_in_research(self):
        book = self.tmp / "fresh"
        run_cli("init", str(book))
        cfg = json.loads((book / "ghostwriter.json").read_text())
        self.assertEqual(cfg["phase"], "research")
        self.assertTrue((book / "research" / "PLAN.md").exists())
        self.assertTrue((book / "author-voice" / "README.md").exists())

    def write_run(self):
        d = self.book / "drafts" / "ch01"
        d.mkdir(parents=True, exist_ok=True)
        (d / "run-1.md").write_text(GOOD)

    def test_drafting_commands_refuse_in_research_and_synthesis(self):
        self.write_run()
        for ph in ("research", "synthesis", "proposal"):
            self.set_phase(ph)
            code, _, err = run_cli("tournament", str(self.book), "ch01")
            self.assertNotEqual(code, 0, ph)
            self.assertIn(f"in the {ph} phase", err)
            self.assertNotEqual(run_cli("promote", str(self.book), "ch01", "run-1")[0], 0, ph)
        self.assertFalse((self.book / "chapters" / "ch01.md").exists())

    def test_author_override_runs_and_is_logged(self):
        self.write_run()
        self.set_phase("research")
        code, _, err = run_cli("tournament", str(self.book), "ch01", "--override-phase", "testing a sample chapter")
        self.assertEqual(code, 0)
        cfg = json.loads((self.book / "ghostwriter.json").read_text())
        self.assertEqual(cfg["phase_overrides"][0]["why"], "testing a sample chapter")
        self.assertEqual(cfg["phase_overrides"][0]["command"], "tournament")

    def test_book_without_a_phase_counts_as_writing(self):
        self.write_run()
        cfg_path = self.book / "ghostwriter.json"
        cfg = json.loads(cfg_path.read_text())
        cfg.pop("phase")
        cfg_path.write_text(json.dumps(cfg))
        self.assertEqual(run_cli("tournament", str(self.book), "ch01")[0], 0)

    def test_phase_require(self):
        self.set_phase("research")
        self.assertEqual(run_cli("phase", "require", str(self.book), "writing")[0], 1)
        self.assertEqual(run_cli("phase", "require", str(self.book), "research")[0], 0)


class ResearchBook(BookTestCase):
    """A book in research with every CLI exit criterion met except the ones a test removes."""

    def setUp(self):
        super().setUp()
        self.set_phase("research")
        (self.book / "research" / "PLAN.md").write_text("# Plan\n\n## Exit criteria\n- [x] reader defined\n- [x] interview done\n")
        run_cli("hypothesis", str(self.book), "--set", "Shared shelves beat garages.")
        for i in range(5):
            run_cli("voice-log", str(self.book), f"line {i} in my words")
        (self.book / "research" / "coverage" / "g.json").write_text(json.dumps(grid()))

    def cfg(self):
        return json.loads((self.book / "ghostwriter.json").read_text())


class TestPhaseAdvance(ResearchBook):
    def test_refuses_with_unmet_criteria_then_advances(self):
        # grid() is 2 filled of 5 meaningful = 40%, under the 75% default
        code, _, err = run_cli("phase", "advance", str(self.book))
        self.assertEqual(code, 1)
        self.assertIn("coverage", err)
        self.assertEqual(self.cfg()["phase"], "research")
        (self.book / "research" / "coverage" / "g.json").write_text(json.dumps(grid(cells=grid()["cells"][:3])))
        code, out, _ = run_cli("phase", "advance", str(self.book))   # 2 filled / 2 meaningful... + unassessed
        self.assertEqual(code, 1, "unassessed cells are not filled")
        full = grid()["cells"][:3] + [{"situation": s, "mechanism": m, "status": "filled", "evidence": "W"}
                                      for s, m in (("S2", "M2"), ("S3", "M1"), ("S3", "M2"))]
        (self.book / "research" / "coverage" / "g.json").write_text(json.dumps(grid(cells=full)))
        code, out, _ = run_cli("phase", "advance", str(self.book))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.cfg()["phase"], "synthesis")
        self.assertEqual(self.cfg()["phase_history"][-1]["from"], "research")

    def test_unticked_plan_blocks(self):
        (self.book / "research" / "coverage" / "g.json").write_text(json.dumps(grid(mode="breadth",
            domains=[{"name": "D"}], items=[{"name": f"p{i}", "domain": "D", "mechanism": "M1", "evidence": "W"} for i in range(3)])))
        (self.book / "research" / "PLAN.md").write_text("# Plan\n\n## Exit criteria\n- [x] a\n- [ ] b\n")
        code, _, err = run_cli("phase", "advance", str(self.book))
        self.assertEqual(code, 1)
        self.assertIn("1/2 ticked", err)

    def test_override_is_logged_with_unmet_criteria(self):
        code, _, _ = run_cli("phase", "advance", str(self.book), "--override", "author wants to start synthesis")
        self.assertEqual(code, 0)
        h = self.cfg()["phase_history"][-1]
        self.assertEqual(h["override"], "author wants to start synthesis")
        self.assertTrue(any("coverage" in u for u in h["unmet"]))

    def test_research_cannot_jump_to_writing_without_override(self):
        self.assertEqual(run_cli("phase", "advance", str(self.book), "--to", "writing")[0], 1)

    def test_going_back_needs_a_reason(self):
        self.set_phase("writing")
        self.assertNotEqual(run_cli("phase", "advance", str(self.book), "--to", "research")[0], 0)
        self.assertEqual(run_cli("phase", "advance", str(self.book), "--to", "research", "--reason", "thesis pivot")[0], 0)
        self.assertEqual(self.cfg()["phase"], "research")

    def test_status_lists_every_criterion(self):
        code, out, _ = run_cli("phase", "status", str(self.book))
        self.assertEqual(code, 0)
        self.assertIn("phase: research", out)
        self.assertIn("[x] the author's own words logged", out)
        self.assertIn("[ ] coverage at 75%+", out)
        self.assertIn("drafting commands are off", out)


class TestThesisPivots(BookTestCase):
    def test_hypothesis_replacement_needs_a_reason_and_archives(self):
        run_cli("hypothesis", str(self.book), "--set", "First idea.")
        self.assertNotEqual(run_cli("hypothesis", str(self.book), "--set", "Second idea.")[0], 0)
        self.assertEqual(run_cli("hypothesis", str(self.book), "--set", "Second idea.", "--reason", "author pivot")[0], 0)
        cur = (self.book / "input" / "thesis" / "working-hypothesis.md").read_text()
        self.assertIn("Second idea.", cur)
        self.assertIn("not a pick", cur)
        arch = list((self.book / "input" / "thesis" / "archive").glob("*-hypothesis.md"))
        self.assertEqual(len(arch), 1)
        self.assertIn("reason: author pivot", arch[0].read_text())
        self.assertIn("First idea.", arch[0].read_text())

    def test_supersede_archives_pick_and_options_with_reason(self):
        (self.book / "thesis.md").write_text("# Thesis\n\n## The statement\nOld pick.\n")
        (self.book / "input" / "thesis" / "options.md").write_text("Option A. Option B.\n")
        self.assertEqual(run_cli("supersede", str(self.book), "--reason", "superseded by research")[0], 0)
        self.assertIn("TODO", (self.book / "thesis.md").read_text())
        self.assertFalse((self.book / "input" / "thesis" / "options.md").exists())
        arch = sorted((self.book / "input" / "thesis" / "archive").glob("*.md"))
        self.assertEqual(len(arch), 2)
        self.assertTrue(all("reason: superseded by research" in a.read_text() for a in arch))
        cfg = json.loads((self.book / "ghostwriter.json").read_text())
        self.assertEqual(cfg["thesis_history"][0]["reason"], "superseded by research")

    def test_supersede_with_nothing_fails(self):
        self.assertNotEqual(run_cli("supersede", str(self.book), "--reason", "x")[0], 0)


class TestCoverageScore(unittest.TestCase):
    def test_score_excludes_na_counts_dups_and_unassessed(self):
        r = gw.coverage_report(grid())
        self.assertEqual(r["grid"]["cells"], 6)
        self.assertEqual(r["grid"]["meaningful"], 5)       # 6 - 1 na
        self.assertEqual(r["grid"]["filled"], 2)           # filled + dup
        self.assertEqual(r["grid"]["unassessed"], 1)       # S3 x M2 never assessed: not filled
        self.assertAlmostEqual(r["score"], 0.4)

    def test_empty_cells_ranked_by_priority(self):
        r = gw.coverage_report(grid())
        self.assertEqual([x.split(":")[0] for x in r["ranked_empty"]], ["S3\u00d7M1", "S2\u00d7M2"])

    def test_mece_each_item_exactly_one_known_mechanism(self):
        r = gw.coverage_report(grid(items=[{"name": "a", "mechanism": ["M1", "M2"], "evidence": "W"},
                                           {"name": "b", "mechanism": "M9", "evidence": "W"}]))
        self.assertTrue(any("exactly one" in p for p in r["problems"]))
        self.assertTrue(any("unknown mechanism M9" in p for p in r["problems"]))

    def test_duplicates_and_no_evidence_flagged(self):
        r = gw.coverage_report(grid(items=[{"name": "Buddy system", "domain": "X", "mechanism": "M1", "evidence": "W"},
                                           {"name": "buddy-system", "domain": "Y", "mechanism": "M1", "evidence": "none"}]))
        self.assertTrue(any("merge" in m for m in r["merges"]))
        self.assertIn("buddy-system", r["no_evidence"])
        self.assertEqual(r["mechanisms_without_items"], ["M2"])

    def test_breadth_mode(self):
        items = [{"name": f"p{i}", "domain": "Choirs", "mechanism": "M1", "evidence": "W"} for i in range(3)]
        items.append({"name": "q", "domain": "Unions", "mechanism": "M1", "evidence": "W"})
        r = gw.coverage_report(grid(mode="breadth", items=items,
                                    domains=[{"name": "Choirs"}, {"name": "Unions"}, {"name": "Optional", "required": False}]))
        self.assertEqual(r["mode"], "breadth")
        self.assertAlmostEqual(r["score"], 0.5)            # Choirs has 3 evidenced; Unions 1 of 3
        self.assertIn("Unions (1/3)", r["breadth"]["thin"])

    def test_situations_need_a_framework(self):
        r = gw.coverage_report(grid(framework={}))
        self.assertTrue(any("framework" in p for p in r["problems"]))

    def test_cli_writes_report(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            book = tmp / "b"
            run_cli("init", str(book))
            f = book / "research" / "coverage" / "g.json"
            f.write_text(json.dumps(grid()))
            code, out, _ = run_cli("coverage", str(book))
            self.assertEqual(code, 0)
            self.assertIn("40%", out)
            rep = (book / "research" / "coverage" / "g.report.md").read_text()
            self.assertIn("Empty cells, ranked", rep)
        finally:
            shutil.rmtree(tmp)

    def test_demo_grid(self):
        data = json.loads(next((DEMO_R / "research" / "coverage").glob("*.json")).read_text())
        r = gw.coverage_report(data)
        self.assertEqual((r["grid"]["filled"], r["grid"]["meaningful"]), (14, 17))
        self.assertEqual(r["problems"], [])


class TestCitationStatus(BookTestCase):
    def cbp_source(self):
        code, out, _ = run_cli("add-source", str(self.book), "https://example.org/fictional", "--kind", "article",
                               "--title", "Fictional study")
        self.assertIn("confirm-before-print", out)
        return out.split()[0]

    def test_link_defaults_to_confirm_before_print_and_fails_a_chapter(self):
        sid = self.cbp_source()
        rep = gw.provenance_report(self.book, self.draft(f"Loans hit 96. [{sid}]\n"))
        self.assertFalse(rep["pass"])
        self.assertEqual(rep["confirm_before_print"], [sid])

    def test_promote_refuses_confirm_before_print(self):
        sid = self.cbp_source()
        d = self.book / "drafts" / "ch01"
        d.mkdir(parents=True)
        (d / "run-1.md").write_text(GOOD.replace("[S001]", f"[{sid}]"))
        code, _, err = run_cli("promote", str(self.book), "ch01", "run-1")
        self.assertNotEqual(code, 0)
        self.assertFalse((self.book / "chapters" / "ch01.md").exists())
        run_cli("cite-status", str(self.book), sid, "--status", "verified", "--how", "fetched the source")
        self.assertEqual(run_cli("promote", str(self.book), "ch01", "run-1")[0], 0)

    def test_verified_needs_how_and_secondhand_needs_via(self):
        sid = self.cbp_source()
        self.assertNotEqual(run_cli("cite-status", str(self.book), sid, "--status", "verified")[0], 0)
        self.assertNotEqual(run_cli("cite-status", str(self.book), sid, "--status", "secondhand")[0], 0)
        self.assertEqual(run_cli("cite-status", str(self.book), sid, "--status", "secondhand", "--via", "S001")[0], 0)
        rep = gw.provenance_report(self.book, self.draft(f"Loans hit 96. [{sid}]\n"))
        self.assertTrue(rep["pass"], rep)
        self.assertTrue(rep["warnings"])

    def test_inline_cbp_marker_fails(self):
        rep = gw.provenance_report(self.book, self.draft("Loans hit 96. [S001] [CBP: exact year]\n"))
        self.assertFalse(rep["pass"])

    def test_research_notes_may_hold_confirm_before_print(self):
        note = self.book / "research" / "n.md"
        note.write_text(ANALOGY.replace("verified | fetched", "confirm-before-print | "))
        self.assertTrue(gw.research_report(note)["pass"], gw.research_report(note))
        note.write_text(ANALOGY.replace("verified | fetched the source", "probably fine | "))
        self.assertFalse(gw.research_report(note)["pass"])
        note.write_text(ANALOGY.replace("| fetched the source |", "| |"))
        self.assertFalse(gw.research_report(note)["pass"], "verified needs a how")

    def test_ingest_research_keeps_status_and_is_idempotent(self):
        note = self.book / "research" / "n.md"
        note.write_text(ANALOGY)
        code, out, _ = run_cli("ingest-research", str(self.book), "research/n.md")
        self.assertEqual(code, 0, out)
        idx = json.loads((self.book / "sources" / "index.json").read_text())["sources"]
        new = [s for s in idx if s.get("from_research")]
        self.assertEqual([s["status"] for s in new], ["confirm-before-print", "verified"])
        self.assertEqual(new[1]["verified_how"], "fetched the source")
        run_cli("ingest-research", str(self.book), "research/n.md")
        self.assertEqual(len(json.loads((self.book / "sources" / "index.json").read_text())["sources"]), len(idx))


ANALOGY = """---
type: analogy
analogy: "A founder leaving is like a CEO retiring."
---

## What the other world does
- Succession plans. [M] (K1)

## Translation
- Name the founder's jobs before they go.

## Where the analogy breaks
A volunteer group cannot pay a successor, and the founder is often also the social center, so the
friends who joined for them may leave with them. Nobody signed a contract, so planning a handover
can feel like pushing someone out, and the overlap can turn into the founder never leaving at all.

## Evidence strength
- [W] reasoned borrowing.

## Sources
| key | citation | url | status | how |
|---|---|---|---|---|
| K0 | Someone (2020), fictional | | confirm-before-print | |
| K1 | Other (2018), fictional | https://example.org/x | verified | fetched the source |
"""


class TestAuthorVoice(BookTestCase):
    WORDS = "People don't quit the work. They quit the feeling that nobody would notice."

    def setUp(self):
        super().setUp()
        code, out, _ = run_cli("voice-log", str(self.book), self.WORDS, "--kind", "belief", "--chapter", "ch01")
        self.assertIn("V001", out)

    def chapter(self, body_line, listed="V001"):
        return GOOD.replace("claim:", f"author_voice: {listed}\nclaim:", 1).replace(
            "I think that matters. [opinion]", body_line)

    def test_log_is_verbatim_and_timestamped(self):
        e = gw.load_voice_log(self.book)[0]
        self.assertEqual(e["text"], self.WORDS)
        self.assertEqual(e["kind"], "belief")
        self.assertRegex(e["at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
        self.assertIn(self.WORDS, (self.book / "author-voice" / "log.md").read_text())

    def test_verbatim_passes_even_with_curly_quotes_and_emphasis(self):
        d = self.draft(self.chapter("As the author put it: \u201c*People don\u2019t quit the work.* They quit the feeling "
                                    "that nobody would notice.\u201d [V001]"))
        rep = gw.author_voice_report(self.book, d)
        self.assertTrue(rep["pass"], rep)
        self.assertTrue(gw.gate_all(self.book, d)["pass"], gw.gate_all(self.book, d))

    def test_paraphrase_fails(self):
        d = self.draft(self.chapter("People leave when they feel nobody would notice them. [V001]"))
        rep = gw.author_voice_report(self.book, d)
        self.assertFalse(rep["pass"])
        self.assertEqual(len(rep["paraphrased_or_missing"]), 1)

    def test_chapter_tagged_entry_is_required_even_if_not_listed(self):
        d = self.draft(GOOD)   # chapter: ch01, no author_voice listed
        self.assertFalse(gw.author_voice_report(self.book, d)["pass"])

    def test_unknown_voice_id_fails(self):
        d = self.draft(self.chapter(self.WORDS + " [V001]", listed="V001, V009"))
        self.assertEqual(gw.author_voice_report(self.book, d)["unknown_ids"], ["V009"])
        self.assertFalse(gw.provenance_report(self.book, self.draft("Fine. [V009]\n"))["pass"])

    def test_promote_refuses_paraphrase_and_tournament_counts_four_checks(self):
        d = self.book / "drafts" / "ch01"
        d.mkdir(parents=True)
        (d / "run-1.md").write_text(self.chapter("People leave when nobody notices. [V001]"))
        code, out, _ = run_cli("tournament", str(self.book), "ch01")
        self.assertIn("eligible: none", out)
        self.assertNotEqual(run_cli("promote", str(self.book), "ch01", "run-1")[0], 0)
        (d / "run-1.md").write_text(self.chapter(self.WORDS + " [V001]"))
        self.assertEqual(gw.gate_all(self.book, d / "run-1.md")["checks"], 4)
        self.assertEqual(run_cli("promote", str(self.book), "ch01", "run-1")[0], 0)

    def test_books_without_a_voice_log_keep_three_checks(self):
        (self.book / "author-voice" / "log.jsonl").unlink()
        self.assertEqual(gw.gate_all(self.book, self.draft(GOOD))["checks"], 3)


THEORY = """---
type: theory
---

## Propositions

### P1 One
- **Wrong if:** x.

### P2 Two
- **Wrong if:** y.

## Decision rule: The Chair Test
1. Would anyone notice?

## Predictions
| # | Prediction | Tests | How |
|---|---|---|---|
| 1 | By 2027 a | P1 | x |
| 2 | By 2028 b | P1 | x |
| 3 | By 2028 c | P2 | x |
| 4 | By 2029 d | P2 | x |
| 5 | By 2030 e | P1 | x |

## Scoring
These are judgment calls.

## Where the evidence is thin
1. a
2. b
"""


class TestResearchNotes(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def rep(self, text):
        p = self.tmp / "n.md"
        p.write_text(text)
        return gw.research_report(p)

    def test_theory_passes(self):
        self.assertTrue(self.rep(THEORY)["pass"], self.rep(THEORY))

    def test_theory_needs_falsifiers_dated_predictions_rule_and_thin_section(self):
        self.assertFalse(self.rep(THEORY.replace("- **Wrong if:** y.", "- trust me"))["pass"])
        self.assertFalse(self.rep(THEORY.replace("| 5 | By 2030 e | P1 | x |\n", ""))["pass"])   # only 4
        self.assertFalse(self.rep(THEORY.replace("By 2030 e", "Someday e"))["pass"])
        self.assertFalse(self.rep(THEORY.replace("## Decision rule: The Chair Test", "## Rule"))["pass"])
        self.assertFalse(self.rep(THEORY.replace("These are judgment calls.", "Scores below."))["pass"])
        self.assertFalse(self.rep(THEORY.split("## Where the evidence is thin")[0])["pass"])

    def test_analogy_must_say_where_it_breaks(self):
        self.assertTrue(self.rep(ANALOGY)["pass"])
        short = re.sub(r"(?s)## Where the analogy breaks\n.*?\n\n## Evidence", "## Where the analogy breaks\nIt mostly holds.\n\n## Evidence", ANALOGY)
        self.assertFalse(self.rep(short)["pass"])
        self.assertFalse(self.rep(ANALOGY.replace("- [W] reasoned borrowing.", "- fine."))["pass"])

    def test_scorecard_statuses(self):
        sc = ("---\ntype: scorecard\n---\n\n## Scorecard\n| Finding | Source | Status | Replication | Use |\n|---|---|---|---|---|\n"
              "| A | x | HOLDS | replicated | supporting |\n| B | x | **MISREAD**: the popular version | resolved | foil |\n"
              "| C | x | CONTESTED | mixed | foil |\n\n## Foils\n- B\n")
        self.assertTrue(self.rep(sc)["pass"], self.rep(sc))
        self.assertFalse(self.rep(sc.replace("| CONTESTED |", "| DEBUNKED |"))["pass"])
        self.assertFalse(self.rep(sc.replace("| mixed |", "| |"))["pass"])

    def test_borrow_scan_needs_every_part_per_domain(self):
        dom = ("### {n}\n- **Mechanisms:** a\n- **Signature practices:** b\n- **Evidence:** [W]\n"
               "- **Failure modes / dark side:** c\n- **Translation:** d\n\n")
        note = "---\ntype: borrow-scan\n---\n\n## Domains\n\n" + dom.format(n="Choirs") + dom.format(n="Brigades")
        self.assertTrue(self.rep(note)["pass"], self.rep(note))
        self.assertFalse(self.rep(note.replace("- **Failure modes / dark side:** c\n", "", 1))["pass"])

    def test_scaffolds_create_each_kind(self):
        book = self.tmp / "b"
        run_cli("init", str(book))
        for kind in ("borrow", "analogy", "scorecard", "theory", "coverage"):
            code, out, _ = run_cli("scaffold", str(book), kind, "--name", f"My {kind}")
            self.assertEqual(code, 0, out)
        self.assertEqual(len(list((book / "research").glob("*.md"))), 6)   # 4 notes + PLAN + README
        json.loads(next((book / "research" / "coverage").glob("*.json")).read_text())

    def test_demo_research_notes_pass(self):
        notes = gw.research_notes(DEMO_R)
        self.assertEqual(len(notes), 2)
        for n in notes:
            self.assertTrue(gw.research_report(n)["pass"], (n, gw.research_report(n)))


class TestDemoResearch(unittest.TestCase):
    def test_is_in_research_and_not_ready_to_leave(self):
        cfg = json.loads((DEMO_R / "ghostwriter.json").read_text())
        self.assertEqual(cfg["phase"], "research")
        self.assertIn("fictional", cfg["author"].lower())
        crit = gw.phase_criteria(DEMO_R, cfg, "research")
        self.assertEqual([n for n, ok, _ in crit if not ok], ["research plan: every exit criterion ticked by the author"])

    def test_every_source_is_fictional_and_has_a_status(self):
        for s in json.loads((DEMO_R / "sources" / "index.json").read_text())["sources"]:
            self.assertIn("fictional", s["title"].lower(), s["id"])
            self.assertIn(s["status"], gw.CITE_STATUSES)

    def test_hypothesis_pivot_is_archived_with_reason(self):
        arch = list((DEMO_R / "input" / "thesis" / "archive").glob("*-hypothesis.md"))
        self.assertEqual(len(arch), 1)
        self.assertIn("reason:", arch[0].read_text())


class TTY(io.StringIO):
    def isatty(self):
        return True


STATUS = {"sponsor_url": "https://github.com/sponsors/laurencewong", "cost_usd": 412.5, "raised_usd": 37,
          "value_moments": [{"id": "chapter-passed", "surface": "cli", "when": "w", "why": "y"},
                            {"id": "full-draft", "surface": "cli", "when": "w", "why": "y"}]}
T0 = datetime(2026, 11, 8, tzinfo=timezone.utc)


class FundTestCase(BookTestCase):
    """The in-flow sponsor line: value moments only, capped, opt-out, never from the model."""

    def setUp(self):
        super().setUp()
        env = {k: v for k, v in os.environ.items() if k not in gw.CI_VARS and k != "GHOSTWRITER_NO_FUND"}
        env["XDG_CONFIG_HOME"] = str(self.tmp / "xdg")
        self.env = mock.patch.dict(os.environ, env, clear=True)
        self.env.start()
        self.status_file = self.tmp / "FUNDING-STATUS.json"
        self.status_file.write_text(json.dumps(STATUS))
        self.fsf = mock.patch.object(gw, "FUNDING_STATUS_FILE", self.status_file)
        self.fsf.start()

    def tearDown(self):
        self.fsf.stop()
        self.env.stop()

    def moment(self, key, now=T0, moment="chapter-passed", tty=True, a=None, words=None):
        out = TTY() if tty else io.StringIO()
        with contextlib.redirect_stdout(out):
            line = gw.fund_milestone(moment, key, "Chapter 3 passed all 3 checks ✓.", a, now=now, words=words)
        return line, out.getvalue()

    def cli(self, *args):
        out = TTY()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = gw.main(list(args))
        return code, out.getvalue()

    def state(self):
        f = gw.fund_state_path()
        return json.loads(f.read_text()) if f.exists() else {}


class TestFundCap(FundTestCase):
    def test_first_moment_asks_with_the_exact_line(self):
        line, out = self.moment("ch03")
        self.assertEqual(line, "Chapter 3 passed all 3 checks ✓. Ghost Writer is free; building it cost "
                               "~$412 in AI, $37 covered. Chip in $3: https://github.com/sponsors/laurencewong")
        self.assertIn(line, out)
        self.assertEqual(gw.fund_state_path(), self.tmp / "xdg" / "ghostwriter" / "fund.json")

    def test_then_every_10th_and_never_within_7_days(self):
        self.assertIsNotNone(self.moment("k0")[0])
        for i in range(1, 10):                       # moments 2..10: 9 since the ask, too few
            self.assertIsNone(self.moment(f"k{i}", T0 + timedelta(days=30))[0])
        self.assertIsNotNone(self.moment("k10", T0 + timedelta(days=30))[0])   # 10th since the ask
        for i in range(11, 40):                      # 10+ more, but all inside 7 days of that ask
            self.assertIsNone(self.moment(f"k{i}", T0 + timedelta(days=33))[0])
        self.assertIsNotNone(self.moment("k40", T0 + timedelta(days=38))[0])   # 7 days later
        self.assertEqual(self.state()["asks"], 3)

    def test_a_chapter_counts_once(self):
        self.moment("ch01")
        self.moment("ch01")
        self.assertEqual(self.state()["moments"], 1)

    def test_only_declared_value_moments_ask(self):
        self.assertIsNone(self.moment("ch01", moment="sources-added")[0])
        self.assertEqual(self.state(), {})

    def test_missing_status_file_says_pending(self):
        self.status_file.unlink()
        line, _ = self.moment("ch01")
        self.assertIn("pending", line)
        self.assertIn("https://github.com/sponsors/laurencewong", line)

    def test_tournament_and_full_draft_moments_from_the_cli(self):
        d = self.book / "drafts" / "ch01"
        d.mkdir(parents=True)
        (d / "run-1.md").write_text(GOOD)
        code, out = self.cli("tournament", str(self.book), "ch01")
        self.assertEqual(code, 0)
        self.assertIn("Chapter 1 passed all 3 checks ✓. Ghost Writer is free;", out)
        (self.book / "spine.md").write_text("| # | Chapter |\n|---|---|\n| ch01 | Only chapter |\n")
        code, out = self.cli("promote", str(self.book), "ch01", "run-1")
        self.assertEqual(code, 0)
        self.assertNotIn("sponsors", out)                          # counted, but capped: 1 since the last ask
        self.assertIn("full-draft:", " ".join(self.state()["seen"]))
        self.assertEqual(self.state()["moments"], 2)


class TestValueEstimate(FundTestCase):
    """The line leads with the value, as a labeled, deliberately low estimate."""

    def test_line_leads_with_value_then_free_then_cost_then_ask(self):
        line, _ = self.moment("ch03", words=6840)     # 6840 / 1140 = 6 h naive, 50% claimed = 3 h
        self.assertEqual(line, "Chapter 3 passed all 3 checks ✓. That's about 3 hours of drafting you didn't do "
                               "(estimate: `ghostwriter.py fund`). Ghost Writer is free; building it cost ~$412 "
                               "in AI, $37 covered. Chip in $3: https://github.com/sponsors/laurencewong")
        self.assertEqual(line.count("\n"), 0)

    def test_claims_at_most_half_and_rounds_down(self):
        est = gw.value_estimate(4000, STATUS)
        self.assertAlmostEqual(est["claimed_hours"], 4000 / 1140 / 2)
        self.assertEqual(gw.hours_phrase(est["claimed_hours"]), "about 1.5 hours")   # 1.75 -> 1.5
        greedy = dict(STATUS, value_estimates={"baseline_words_per_hour": 1140, "claim_share": 0.9})
        self.assertEqual(gw.value_estimate(4000, greedy)["claim_share"], 0.5)        # capped at half
        self.assertEqual(gw.hours_phrase(0.99), "about 50 minutes")
        self.assertEqual(gw.hours_phrase(1.0), "about 1 hour")

    def test_tiny_value_is_not_claimed(self):
        line, _ = self.moment("ch01", words=300)       # ~8 minutes claimed: say nothing about value
        self.assertNotIn("That's", line)
        self.assertTrue(line.startswith("Chapter 3 passed all 3 checks ✓. Ghost Writer is free;"))

    def test_assumptions_come_from_funding_status(self):
        fs = dict(STATUS, value_estimates={"baseline_words_per_hour": 500, "claim_share": 0.25})
        self.assertAlmostEqual(gw.value_estimate(1000, fs)["claimed_hours"], 0.5)

    def test_repo_value_estimates_are_cited_and_labeled(self):
        ve = json.loads((ROOT / "FUNDING-STATUS.json").read_text())["value_estimates"]
        self.assertEqual(ve["label"], "estimate")
        self.assertLessEqual(ve["claim_share"], 0.5)
        self.assertTrue(ve["benchmarks"] and all(b.get("source") and b.get("url") for b in ve["benchmarks"]))

    def test_fund_shows_the_math_sources_and_the_last_estimate(self):
        self.status_file.write_text((ROOT / "FUNDING-STATUS.json").read_text())
        self.moment("ch03", words=6840)
        code, out = self.cli("fund")
        self.assertEqual(code, 0)
        self.assertIn("ESTIMATE", out)
        self.assertIn("/ 1,140 words per hour x 50%", out)
        self.assertIn("Karat", out)
        self.assertIn("your last: Chapter 3, 6,840 words / 1,140 = 6.0 h naive x 50% = 3.0 h", out)

    def test_full_draft_sums_every_chapter(self):
        (self.book / "spine.md").write_text("| # | Chapter |\n|---|---|\n| ch01 | One |\n| ch02 | Two |\n")
        (self.book / "chapters").mkdir(exist_ok=True)
        (self.book / "chapters" / "ch01.md").write_text(GOOD)
        d = self.book / "drafts" / "ch02"
        d.mkdir(parents=True)
        (d / "run-1.md").write_text(GOOD)
        seen = {}
        real = gw.fund_milestone
        def spy(moment, key, prefix, a=None, **kw):
            seen[moment] = kw.get("words")
            return real(moment, key, prefix, a, **kw)
        with mock.patch.object(gw, "fund_milestone", spy):
            self.assertEqual(self.cli("promote", str(self.book), "ch02", "run-1")[0], 0)
        one = gw.ai_tell_report(self.book / "chapters" / "ch01.md")["words"]
        self.assertEqual(seen, {"full-draft": 2 * one})


class TestResearchReadyMoment(FundTestCase):
    """Leaving research with every criterion met is a value moment; an override is not."""

    def research_book(self, cover_full=True):
        self.set_phase("research")
        (self.book / "research" / "PLAN.md").write_text("# Plan\n\n## Exit criteria\n- [x] done\n")
        run_cli("hypothesis", str(self.book), "--set", "A hypothesis.")
        for i in range(5):
            run_cli("voice-log", str(self.book), f"words {i}")
        cells = [{"situation": "S1", "mechanism": "M1", "status": "filled" if cover_full else "empty", "evidence": "W"}]
        (self.book / "research" / "coverage" / "g.json").write_text(json.dumps(
            {"framework": {"name": "f"}, "mechanisms": [{"code": "M1"}], "situations": [{"code": "S1"}], "cells": cells}))

    def test_clean_advance_is_a_value_moment_with_no_hours_claim(self):
        self.status_file.write_text((ROOT / "FUNDING-STATUS.json").read_text())
        self.research_book()
        code, out = self.cli("phase", "advance", str(self.book))
        self.assertEqual(code, 0)
        self.assertIn("Research phase complete: all 5 exit criteria met ✓. Ghost Writer is free;", out)
        self.assertNotIn("That's about", out)

    def test_override_advance_is_not_a_value_moment(self):
        self.status_file.write_text((ROOT / "FUNDING-STATUS.json").read_text())
        self.research_book(cover_full=False)
        code, out = self.cli("phase", "advance", str(self.book), "--override", "moving on")
        self.assertEqual(code, 0)
        self.assertNotIn("Ghost Writer is free", out)
        self.assertEqual(self.state(), {})


class TestFundSilence(FundTestCase):
    def assertSilent(self, **kw):
        line, out = self.moment("ch01", **kw)
        self.assertIsNone(line)
        self.assertNotIn("sponsors", out)

    def test_silent_when_not_a_terminal(self):
        self.assertSilent(tty=False)
        self.assertEqual(self.state(), {})       # silence writes no state either

    def test_silent_in_ci(self):
        for var in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE"):
            with mock.patch.dict(os.environ, {var: "true"}):
                self.assertSilent()

    def test_silent_with_env_opt_out(self):
        with mock.patch.dict(os.environ, {"GHOSTWRITER_NO_FUND": "1"}):
            self.assertSilent()

    def test_silent_with_quiet_flag_before_or_after_the_command(self):
        d = self.book / "drafts" / "ch01"
        d.mkdir(parents=True)
        (d / "run-1.md").write_text(GOOD)
        for args in (["--quiet", "tournament", str(self.book), "ch01"],
                     ["tournament", str(self.book), "ch01", "-q"]):
            code, out = self.cli(*args)
            self.assertEqual(code, 0)
            self.assertNotIn("sponsors", out)

    def test_silent_after_fund_off_and_back_on(self):
        self.assertEqual(self.cli("fund", "--off")[0], 0)
        self.assertSilent()
        self.cli("fund", "--on")
        self.assertIsNotNone(self.moment("ch02")[0])

    def test_stops_once_the_goal_is_covered(self):
        self.status_file.write_text(json.dumps(dict(STATUS, raised_usd=412.5)))
        self.assertSilent()
        code, out = self.cli("fund")
        self.assertIn("fully covered", out)
        self.assertNotIn("Chip in", out)

    def test_fund_command_shows_cost_raised_and_link_on_demand(self):
        code, out = self.cli("fund")
        self.assertEqual(code, 0)
        self.assertIn("~$412 in AI, $37 covered. Chip in $3: https://github.com/sponsors/laurencewong", out)


import fund_line_hook as hook  # noqa: E402

HOOK_STATUS = json.loads(json.dumps(STATUS))
for _m in HOOK_STATUS["value_moments"]:
    _m["hook_match"] = {"command": r"ghostwriter\.py",
                        "output": r"^\[value moment\] " + _m["id"]
                        + r" key=(?P<key>[0-9a-f]{16}) words=(?P<words>\d+) \| (?P<prefix>.+)$"}


class TestFundHook(FundTestCase):
    """The opt-in Claude Code hook: the CLI prints a neutral marker when not a terminal; the hook shows
    the line to the USER as a systemMessage, under the same caps, opt-outs and state as the CLI."""

    def setUp(self):
        super().setUp()
        self.status_file.write_text(json.dumps(HOOK_STATUS))

    def marker(self, key, moment="chapter-passed", words=None):
        line, out = self.moment(key, moment=moment, tty=False, words=words)
        self.assertIsNone(line)
        return out

    def event(self, out, cmd="python3 scripts/ghostwriter.py promote books/b ch03 run-1"):
        return {"tool_name": "Bash", "tool_input": {"command": cmd},
                "tool_response": {"stdout": out, "stderr": ""}}

    def run_hook(self, event):
        out = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))), contextlib.redirect_stdout(out):
            self.assertEqual(hook.main([]), 0)
        return out.getvalue()

    def test_not_a_terminal_prints_a_neutral_marker_and_no_money(self):
        out = self.marker("ch03", words=6840)
        self.assertIn("[value moment] chapter-passed key=", out)
        self.assertIn("words=6840 | Chapter 3 passed all 3 checks ✓.", out)
        self.assertIsNone(re.search(r"(?i)sponsor|chip in|\$", out))
        self.assertEqual(self.state(), {})            # the CLI counts nothing on this path

    def test_hook_shows_the_exact_cli_line_as_a_system_message(self):
        printed = self.run_hook(self.event(self.marker("ch03", words=6840)))
        msg = json.loads(printed)["systemMessage"]
        self.assertEqual(msg, "Chapter 3 passed all 3 checks ✓. That's about 3 hours of drafting you didn't do "
                              "(estimate: `ghostwriter.py fund`). Ghost Writer is free; building it cost ~$412 "
                              "in AI, $37 covered. Chip in $3: https://github.com/sponsors/laurencewong")
        self.assertEqual(self.state()["asks"], 1)

    def test_hook_and_cli_share_one_set_of_caps(self):
        self.assertIsNotNone(hook.handle(self.event(self.marker("k0")), now=T0))
        for i in range(1, 10):
            self.assertIsNone(hook.handle(self.event(self.marker(f"k{i}")), now=T0 + timedelta(days=30)))
        self.assertIsNotNone(hook.handle(self.event(self.marker("k10")), now=T0 + timedelta(days=30)))
        self.assertIsNone(hook.handle(self.event(self.marker("k11")), now=T0 + timedelta(days=31)))
        self.assertIsNone(self.moment("k12", now=T0 + timedelta(days=32))[0])   # terminal: within 7 days
        self.assertEqual(self.state()["asks"], 2)

    def test_an_outcome_counts_once_and_the_marker_stops(self):
        out = self.marker("ch01")
        self.assertIsNotNone(hook.handle(self.event(out)))
        self.assertIsNone(hook.handle(self.event(out)))
        self.assertEqual(self.state()["moments"], 1)
        self.assertNotIn("[value moment]", self.marker("ch01"))   # already counted: no marker either

    def test_only_ghostwriter_commands_and_declared_moments(self):
        out = self.marker("ch01")
        self.assertIsNone(hook.handle(self.event(out, cmd="cat notes.txt")))
        self.assertIsNone(hook.handle(self.event(out.replace("chapter-passed", "sources-added"))))
        self.assertIsNone(hook.handle({"tool_name": "Bash", "tool_input": {"command": "ls"},
                                       "tool_response": {"stdout": "ok"}}))
        self.assertEqual(self.state(), {})

    def test_silent_in_ci_with_env_opt_out_and_after_off(self):
        out = self.marker("ch01")
        for env in ({"CI": "true"}, {"GITHUB_ACTIONS": "true"}, {"GHOSTWRITER_NO_FUND": "1"}):
            with mock.patch.dict(os.environ, env):
                self.assertEqual(self.run_hook(self.event(out)), "")
        with contextlib.redirect_stdout(io.StringIO()):
            hook.main(["--off"])
        self.assertEqual(self.run_hook(self.event(out)), "")
        self.assertEqual(self.cli("fund")[1].count("occasional line: off"), 1)   # one switch for both
        self.assertEqual(self.marker("ch02"), "")                                  # and no marker when off

    def test_stops_once_the_goal_is_covered(self):
        out = self.marker("ch01")
        self.status_file.write_text(json.dumps(dict(HOOK_STATUS, raised_usd=412.5)))
        self.assertEqual(self.run_hook(self.event(out)), "")
        self.assertEqual(self.marker("ch02"), "")

    def test_research_moment_makes_no_hours_claim(self):
        out = self.marker("b", moment="research-ready")
        self.assertEqual(out, "")                       # not declared in this status file
        fs = json.loads((ROOT / "FUNDING-STATUS.json").read_text())
        self.status_file.write_text(json.dumps(fs))
        with mock.patch.object(gw, "fund_line", lambda f: "LINE"):
            line, out = self.moment("b", moment="research-ready", tty=False)
            msg = hook.handle(self.event(out))
        self.assertTrue(msg.startswith("Chapter 3 passed all 3 checks ✓. LINE"))
        self.assertNotIn("That's", msg)

    def test_bad_input_never_breaks_the_tool_call(self):
        with mock.patch.object(sys, "stdin", io.StringIO("not json")):
            self.assertEqual(hook.main([]), 0)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "fund_line_hook.py")], input="{}",
                           capture_output=True, text=True, env={**os.environ, "XDG_CONFIG_HOME": str(self.tmp)})
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_repo_moments_all_have_a_hook_match_for_the_cli_marker(self):
        fs = json.loads((ROOT / "FUNDING-STATUS.json").read_text())
        for m in fs["value_moments"]:
            marker = gw.value_moment_marker(m["id"], "0123456789abcdef", 10, "Done.")
            self.assertRegex(marker, re.compile(m["hook_match"]["output"], re.M))
            self.assertRegex("python3 scripts/ghostwriter.py promote b ch01 run-1", m["hook_match"]["command"])

    def test_hook_is_not_enabled_by_default(self):
        settings = (ROOT / ".claude" / "settings.json").read_text()
        self.assertNotIn("fund_line_hook", settings)


class TestNoAskFromTheModel(unittest.TestCase):
    """Only the CLI ever mentions money. The prompts and charter files the model reads never do."""
    PATTERN = re.compile(r"sponsor|donat|chip in", re.I)

    def llm_files(self):
        files = [ROOT / "AGENT.md", ROOT / "CLAUDE.md"]
        for d in ("prompts", "book-template", ".claude/agents", "skills"):
            if (ROOT / d).is_dir():
                files += [p for p in (ROOT / d).rglob("*") if p.is_file()]
        return [f for f in files if f.is_file()]

    def test_prompts_and_charter_never_ask_for_money(self):
        files = self.llm_files()
        self.assertGreater(len(files), 10)
        hits = [f"{f.relative_to(ROOT)}: {m.group(0)}" for f in files
                for m in [self.PATTERN.search(f.read_text(errors="replace"))] if m]
        self.assertEqual(hits, [])

    def test_repo_declares_its_value_moments(self):
        fs = json.loads((ROOT / "FUNDING-STATUS.json").read_text())
        self.assertTrue(fs["value_moments"])
        for m in fs["value_moments"]:
            self.assertTrue(m["id"] and m["when"] and len(m["why"].split()) >= 8, m)


class TestBoundaryHook(unittest.TestCase):
    @unittest.skipUnless(shutil.which("jq"), "jq not installed")
    def test_boundary_suite_passes(self):
        r = subprocess.run(["bash", str(ROOT / "tests" / "test_boundary_lite.sh")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
