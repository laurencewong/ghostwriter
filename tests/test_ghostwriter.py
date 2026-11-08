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
