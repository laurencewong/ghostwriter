#!/usr/bin/env python3
"""ghostwriter.py: the deterministic half of Ghost Writer.

The judgment steps (pick a thesis, write a chapter, judge a tournament) are prompts in
prompts/, run by an AI coding agent. This script does everything that should NOT be left
to a model's judgment: scaffolding, the source registry, filing interview answers,
measuring the author's voice, and the gates a chapter must pass before it is promoted.

Standard library only. Python 3.9+.

Phases: research -> synthesis -> proposal (optional) -> writing. A new book starts in research.
Drafting commands (tournament, promote) refuse to run before the writing phase unless the author
overrides, and every override is logged in ghostwriter.json.

Commands (run `python3 scripts/ghostwriter.py <command> -h` for flags):
  init                 create a book workspace (starts in the research phase)
  phase                `phase status`: where the book is and which exit criteria are met;
                       `phase advance`: move on (refuses until the criteria pass, unless overridden);
                       `phase require`: exit non-zero unless the book is in the named phase
  hypothesis           show or set the working hypothesis (archives the old one with a reason)
  supersede            archive the thesis pick and options with the reason they were dropped
  voice-log            log the author's own words (quote, metaphor, analogy, belief, correction) verbatim
  check-author-voice   a draft keeps the author's logged words verbatim instead of paraphrasing them
  scaffold             start a research note from a template: borrow, analogy, scorecard, theory, coverage
  check-research       structural check of a research note (falsifiers, where-it-breaks, statuses...)
  coverage             score a coverage grid or breadth checklist and write a report
  ingest-research      turn a research note's Sources table into registered, citable sources
  add-source           register a post, note, dataset, article or interview as a cited source
  cite-status          record how a source was verified (verified / confirm-before-print / secondhand)
  interview-open       list interview questions that have no answer yet
  interview-file       file an answer to an interview question as a source
  voice-build          measure the author's voice from their own published writing
  check-provenance     every factual claim cites a source or is marked as opinion
  check-ai-tells       flag generic machine-sounding prose
  check-thesis         the chapter advances or tests the thesis and steelmans the other side
  tournament           run all gates on every draft of a chapter and write a scoreboard
  promote              copy a winning draft to chapters/, only if it passes every gate
  status               show where a book is in the pipeline
  fund                 show what building Ghost Writer has cost, how much sponsors have covered, and
                       the math behind the "hours of drafting" estimate
                       (`fund --off` turns off the occasional thank-you line; `fund --on` turns it back on)
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "book-template"
AI_TELLS_FILE = ROOT / "data" / "ai-tells.txt"
FUNDING_STATUS_FILE = ROOT / "FUNDING-STATUS.json"

SOURCE_KINDS = ("post", "note", "dataset", "article", "interview", "book", "talk", "other")
XREF_RX = re.compile(r"\b(chapters?|ch|part|section|stage|step|figure|table)\s*\d+\b", re.I)  # cross-references are not claims
THESIS_ROLES = ("advances", "tests", "complicates")
PHASES = ("research", "synthesis", "proposal", "writing")
CITE_STATUSES = ("verified", "confirm-before-print", "secondhand")
CITE_RX = re.compile(r"\[(S\d{3,})\]")
VOICE_TAG_RX = re.compile(r"\[(V\d{3,})\]")
OPINION_RX = re.compile(r"\[(opinion|author|V\d{3,})\]", re.I)
CBP_MARK_RX = re.compile(r"\[(?:CBP|confirm[- ]before[- ]print)[^\]]*\]", re.I)
CLAIM_RX = re.compile(
    r"\d|%|\bpercent\b|\baccording to\b|\bstud(y|ies)\b|\bsurvey(s|ed)?\b|\bresearch(ers)?\b"
    r"|\breport(s|ed)?\b|\bfound that\b|\bmillions?\b|\bbillions?\b|\bdata\b|\bevidence\b"
    r"|\bmost (people|households|teams|companies|users)\b|\bon average\b",
    re.I,
)
STOPWORDS = set("""a an the and or but if then so of to in on at by for with from as is are was were be been being
it its this that these those i you he she we they me my your our their his her them us not no do does did
have has had will would can could should may might just than too very also into out up down over about
what which who whom when where why how all any each few more most other some such only own same there here
""".split())


# ---------------------------------------------------------------- helpers
def die(msg: str, code: int = 2) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def load_config(book: Path) -> dict:
    cfg = book / "ghostwriter.json"
    if not cfg.is_file():
        die(f"{book} is not a book workspace (no ghostwriter.json). Run `init` first.")
    return json.loads(cfg.read_text())


def resolve(book: Path, p: str) -> Path:
    p = os.path.expanduser(p)
    return Path(p) if os.path.isabs(p) else book / p


def split_front_matter(text: str) -> tuple[dict, str]:
    """Tiny `key: value` front matter parser (no YAML dependency)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[end + 4:].lstrip("\n")


def prose_lines(body: str) -> list[str]:
    """Body lines that are prose: drop headings, code fences, tables, html comments."""
    out, in_code = [], False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not s or s.startswith(("#", "|", "<!--")):
            continue
        out.append(s)
    return out


TRAILING_TAGS_RX = re.compile(r"([.!?])((?:\s*\[(?:S\d{3,}|V\d{3,}|opinion|author)\])+)", re.I)


def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    # "A fact. [S001] Next sentence." -> the tag belongs to the sentence before it.
    text = TRAILING_TAGS_RX.sub(lambda m: m.group(2) + m.group(1), text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(\[*_])", text)
    return [p.strip() for p in parts if len(p.strip()) > 1]


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'\-]*", text)


def load_index(book: Path) -> dict:
    f = book / "sources" / "index.json"
    return json.loads(f.read_text()) if f.is_file() else {"sources": []}


def save_index(book: Path, idx: dict) -> None:
    (book / "sources").mkdir(parents=True, exist_ok=True)
    (book / "sources" / "index.json").write_text(json.dumps(idx, indent=2) + "\n")


def next_source_id(idx: dict) -> str:
    nums = [int(s["id"][1:]) for s in idx["sources"]]
    return f"S{(max(nums) + 1 if nums else 1):03d}"


# ---------------------------------------------------------------- init
def cmd_init(a) -> int:
    book = Path(a.dir)
    if (book / "ghostwriter.json").exists():
        die(f"{book} already has a ghostwriter.json")
    shutil.copytree(TEMPLATE, book, dirs_exist_ok=True)
    cfg = json.loads((book / "ghostwriter.json").read_text())
    cfg["title"] = a.title or cfg["title"]
    cfg["author"] = a.author or cfg["author"]
    cfg["created"] = date.today().isoformat()
    cfg["phase"] = "research"
    cfg["phase_history"] = [{"to": "research", "at": now_stamp()}]
    (book / "ghostwriter.json").write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"created book workspace at {book} (phase: research)")
    print("next: write the research plan and its exit criteria (prompts/R0-research-plan.md), then "
          "`phase status`. Drafting stays off until the writing phase.")
    return 0


# ---------------------------------------------------------------- sources
def register_source(book: Path, kind: str, title: str, origin: str, when: str,
                    body: str | None, pointer: str | None, note: str = "",
                    status: str | None = None, how: str | None = None, extra: dict | None = None) -> str:
    idx = load_index(book)
    sid = next_source_id(idx)
    rec = {"id": sid, "kind": kind, "title": title, "origin": origin, "date": when,
           "file": f"sources/{sid}.md"}
    if pointer:
        rec["pointer"] = pointer
    if note:
        rec["note"] = note
    if status:
        rec["status"] = status
    if how:
        rec["verified_how"] = how
    rec.update(extra or {})
    idx["sources"].append(rec)
    save_index(book, idx)
    head = "\n".join(f"{k}: {v}" for k, v in rec.items() if k != "file" and not isinstance(v, (dict, list)))
    content = body if body is not None else f"(pointer only; content lives at `{pointer}`)\n"
    (book / rec["file"]).write_text(f"---\n{head}\n---\n\n{content.rstrip()}\n")
    return sid


def cmd_add_source(a) -> int:
    book = Path(a.book)
    load_config(book)
    if a.kind not in SOURCE_KINDS:
        die(f"--kind must be one of {', '.join(SOURCE_KINDS)}")
    body, pointer = None, None
    src = a.path
    if a.pointer:
        pointer = src
    elif src.startswith(("http://", "https://")):
        body = f"Link: {src}\n\n{a.summary or '(add a summary and the exact passages you will cite)'}"
    else:
        p = Path(os.path.expanduser(src))
        if not p.is_file():
            die(f"no such file: {src}")
        body = p.read_text(errors="replace")
    # Default origin is the file name, never the full local path (paths leak machine layout).
    is_url = src.startswith(("http://", "https://"))
    origin = a.origin or (src if is_url else Path(src).name)
    # Citation honesty: a link with a summary has not been checked yet; a copy in hand has.
    status = a.status or ("confirm-before-print" if is_url else "verified")
    how = a.how or (None if is_url else ("pointer to the author's file" if a.pointer else "copy in workspace"))
    check_status_args(status, how, a.via)
    sid = register_source(book, a.kind, a.title or Path(src).name, origin,
                          a.date or date.today().isoformat(), body, pointer, a.note or "",
                          status=status, how=how, extra={"via": a.via} if a.via else None)
    print(f"{sid}  {a.kind}  {status}  {a.title or src}")
    return 0


def check_status_args(status: str, how: str | None, via: str | None) -> None:
    if status not in CITE_STATUSES:
        die(f"--status must be one of {', '.join(CITE_STATUSES)}")
    if status == "verified" and not how:
        die("a verified source needs --how: what you checked (fetched the source, PubMed, Crossref, DOI, book in hand...)")
    if status == "secondhand" and not via:
        die("a secondhand source needs --via: the source that cites it")


def cmd_cite_status(a) -> int:
    book = Path(a.book)
    load_config(book)
    check_status_args(a.status, a.how, a.via)
    idx = load_index(book)
    rec = next((s for s in idx["sources"] if s["id"] == a.source_id), None)
    if not rec:
        die(f"{a.source_id} is not registered")
    rec["status"] = a.status
    if a.how:
        rec["verified_how"] = a.how
    elif a.status != "verified":
        rec.pop("verified_how", None)
    if a.via:
        rec["via"] = a.via
    rec["status_date"] = date.today().isoformat()
    if a.note:
        rec["status_note"] = a.note
    save_index(book, idx)
    print(f"{a.source_id} -> {a.status}" + (f" ({a.how})" if a.how else "") + (f" via {a.via}" if a.via else ""))
    return 0


# ---------------------------------------------------------------- interview
Q_RX = re.compile(r"^- \[( |x)\] (Q\d{3,})\b(.*)$")


def read_questions(book: Path) -> list[tuple[int, bool, str, str]]:
    f = book / "interview" / "questions.md"
    if not f.is_file():
        return []
    out = []
    for i, line in enumerate(f.read_text().splitlines()):
        m = Q_RX.match(line)
        if m:
            out.append((i, m.group(1) == "x", m.group(2), m.group(3).strip()))
    return out


def cmd_interview_open(a) -> int:
    book = Path(a.book)
    load_config(book)
    open_qs = [q for q in read_questions(book) if not q[1]]
    for _, _, qid, text in open_qs:
        print(f"{qid} {text}")
    print(f"({len(open_qs)} open)", file=sys.stderr)
    return 0


def cmd_interview_file(a) -> int:
    book = Path(a.book)
    load_config(book)
    qs = {q[2]: q for q in read_questions(book)}
    if a.question_id not in qs:
        die(f"{a.question_id} is not in interview/questions.md")
    line_no, done, qid, qtext = qs[a.question_id]
    if done:
        die(f"{qid} is already answered")
    answer = Path(os.path.expanduser(a.answer_file)).read_text() if a.answer_file else sys.stdin.read()
    if not answer.strip():
        die("empty answer")
    body = f"**Question ({qid}):** {qtext}\n\n**Answer (the author, first person):**\n\n{answer.strip()}\n"
    sid = register_source(book, "interview", f"Interview answer to {qid}", "author interview",
                          date.today().isoformat(), body, None, status="verified", how="the author, first person")
    qf = book / "interview" / "questions.md"
    lines = qf.read_text().splitlines()
    lines[line_no] = lines[line_no].replace("- [ ]", "- [x]", 1) + f" -> {sid}"
    qf.write_text("\n".join(lines) + "\n")
    print(f"{qid} answered -> {sid}")
    return 0


# ---------------------------------------------------------------- voice
def sample_texts(book: Path, cfg: dict) -> list[tuple[str, float]]:
    """Yield (text, weight) from the configured samples. Refuses anything not owned by the author."""
    out = []
    for s in cfg.get("voice", {}).get("samples", []):
        if s.get("owner") != "self":
            die(f"voice sample {s.get('path')!r} is not marked owner: self. Ghost Writer only learns a "
                "voice from the author's own writing, never from another writer.")
        weight = float(s.get("weight", 1.0))
        field = s.get("jsonl_field", "text")
        for f in sorted(glob.glob(str(resolve(book, s["path"])))):
            if f.endswith(".jsonl"):
                for line in Path(f).read_text(errors="replace").splitlines():
                    try:
                        t = json.loads(line).get(field, "")
                    except ValueError:
                        continue
                    if t and t.strip():
                        out.append((t, weight))
            elif f.endswith((".md", ".txt", ".markdown")):
                _, body = split_front_matter(Path(f).read_text(errors="replace"))
                out.append((body, weight))
    return out


def voice_stats(samples: list[tuple[str, float]]) -> dict:
    sent_lens, para_lens = [], []
    tot = Counter()
    openers, bigrams = Counter(), Counter()
    for text, w in samples:
        text = text.replace("\u2019", "'").replace("\u2018", "'")  # curly apostrophes split words
        paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        for p in paras:
            para_lens.append((len(words(p)), w))
        lines = prose_lines(text)
        sents = sentences(" ".join(lines))
        for s in sents:
            ws = words(s)
            if not ws:
                continue
            sent_lens.append((len(ws), w))
            tot["sentences"] += w
            tot["words"] += w * len(ws)
            tot["questions"] += w * s.endswith("?")
            tot["first_person"] += w * bool(re.match(r"(I|I'm|I've|My|We)\b", s))
            tot["contractions"] += w * len(re.findall(r"\b\w+'(s|re|ve|ll|d|t|m)\b", s))
            tot["dashes"] += w * (s.count("—") + s.count(" - "))
            openers[ws[0].lower()] += w
            low = [x.lower() for x in ws]
            for x, y in zip(low, low[1:]):
                if x not in STOPWORDS and y not in STOPWORDS:
                    bigrams[f"{x} {y}"] += w
        tot["bullets"] += w * len(re.findall(r"(?m)^\s*([-*•]|\d+\.)\s", text))
    def wmean(pairs):
        tw = sum(w for _, w in pairs)
        return round(sum(v * w for v, w in pairs) / tw, 1) if tw else 0.0
    def share(n, lo, hi):
        tw = sum(w for _, w in sent_lens)
        return round(100 * sum(w for v, w in sent_lens if lo <= v <= hi) / tw) if tw else 0
    s = tot["sentences"] or 1
    return {
        "samples": len(samples),
        "sentences": round(tot["sentences"]),
        "avg_sentence_words": wmean(sent_lens),
        "short_sentences_pct": share(0, 1, 8),
        "long_sentences_pct": share(0, 25, 10_000),
        "avg_paragraph_words": wmean(para_lens),
        "questions_per_100_sentences": round(100 * tot["questions"] / s, 1),
        "first_person_openers_pct": round(100 * tot["first_person"] / s, 1),
        "contractions_per_100_words": round(100 * tot["contractions"] / (tot["words"] or 1), 2),
        "dashes_per_100_sentences": round(100 * tot["dashes"] / s, 1),
        "bullets_per_sample": round(tot["bullets"] / (sum(w for _, w in samples) or 1), 1),
        "top_openers": [k for k, _ in openers.most_common(10)],
        "signature_bigrams": [k for k, v in bigrams.most_common(25) if v >= 2],
    }


def cmd_voice_build(a) -> int:
    book = Path(a.book)
    cfg = load_config(book)
    samples = sample_texts(book, cfg)
    if not samples:
        die("no voice samples found. Add the author's own published writing under voice.samples in ghostwriter.json.")
    st = voice_stats(samples)
    (book / "voice").mkdir(exist_ok=True)
    (book / "voice" / "profile.json").write_text(json.dumps(st, indent=2) + "\n")
    lines = [
        f"# Voice profile: {cfg.get('author', 'the author')}",
        "",
        f"Measured from {st['samples']} of the author's own pieces ({st['sentences']} sentences) on {date.today().isoformat()}.",
        "Generated by `ghostwriter.py voice-build`. Do not hand-edit the numbers; add judgment notes at the bottom.",
        "",
        "## Rhythm",
        f"- Average sentence: **{st['avg_sentence_words']} words**. Short (8 words or fewer): {st['short_sentences_pct']}%. Long (25+): {st['long_sentences_pct']}%.",
        f"- Average paragraph: {st['avg_paragraph_words']} words.",
        f"- Questions: {st['questions_per_100_sentences']} per 100 sentences.",
        f"- Dashes: {st['dashes_per_100_sentences']} per 100 sentences.",
        "",
        "## Stance",
        f"- Sentences opening in first person: {st['first_person_openers_pct']}%.",
        f"- Contractions: {st['contractions_per_100_words']} per 100 words.",
        f"- Bullets per piece: {st['bullets_per_sample']}.",
        "",
        "## Habits",
        f"- Most common sentence openers: {', '.join(st['top_openers'])}.",
        f"- Signature phrases (repeated two-word pairs): {', '.join(st['signature_bigrams']) or 'none yet'}.",
        "",
        "## How drafts use this",
        "Drafts aim for the rhythm and stance above. They never copy sentences from the samples, and never",
        "imitate any other writer, living or dead. If the numbers drift more than about 30% in a draft, the",
        "tournament judge marks it down.",
        "",
        "## Judgment notes (human or agent, append below)",
        "",
    ]
    (book / "voice" / "profile.md").write_text("\n".join(lines))
    print(f"wrote {book / 'voice' / 'profile.md'} from {st['samples']} samples")
    return 0


# ---------------------------------------------------------------- gates
def provenance_report(book: Path, draft: Path) -> dict:
    """Every factual-looking sentence carries a tag, every tag is registered, and (citation honesty)
    no cited source is still marked confirm-before-print. Secondhand and unrecorded statuses warn."""
    srcs = {s["id"]: s for s in load_index(book)["sources"]}
    voice_ids = {e["id"] for e in load_voice_log(book)}
    _, body = split_front_matter(draft.read_text())
    unsupported, unknown, cited, opinions, claims = [], set(), 0, 0, 0
    used = set()
    for line in prose_lines(body):
        if line.startswith(">"):
            line = line.lstrip("> ")
        for s in sentences(line):
            ids = CITE_RX.findall(s)
            used.update(ids)
            unknown.update(i for i in ids if i not in srcs)
            unknown.update(v for v in VOICE_TAG_RX.findall(s) if v not in voice_ids)
            bare = XREF_RX.sub("", CITE_RX.sub("", s))
            if "[NEEDS SOURCE" in s.upper() or CBP_MARK_RX.search(s):
                claims += 1
                unsupported.append(s)
                continue
            if not CLAIM_RX.search(bare):
                continue
            claims += 1
            if ids:
                cited += 1
            elif OPINION_RX.search(s):
                opinions += 1
            else:
                unsupported.append(s)
    known_used = sorted(i for i in used if i in srcs)
    status = {i: srcs[i].get("status", "unrecorded") for i in known_used}
    unconfirmed = [i for i in known_used if status[i] == "confirm-before-print"]
    warnings = [f"{i} is secondhand (via {srcs[i].get('via', '?')}): fine to cite, better to check the original"
                for i in known_used if status[i] == "secondhand"]
    warnings += [f"{i} has no citation status yet (`cite-status`)" for i in known_used if status[i] == "unrecorded"]
    return {"claims": claims, "cited": cited, "opinion": opinions,
            "unsupported": unsupported, "unknown_ids": sorted(unknown),
            "confirm_before_print": unconfirmed, "warnings": warnings,
            "pass": not unsupported and not unknown and not unconfirmed}


def load_tells() -> list[tuple[str, re.Pattern]]:
    out = []
    for line in AI_TELLS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sev, _, pat = line.partition(" ")
        out.append((sev, re.compile(pat.strip(), re.I)))
    return out


def ai_tell_report(draft: Path) -> dict:
    _, body = split_front_matter(draft.read_text())
    text = " ".join(prose_lines(body))
    n = max(len(words(text)), 1)
    hits = []
    for sev, rx in load_tells():
        for m in rx.finditer(text):
            hits.append({"severity": sev, "match": m.group(0)})
    dashes = text.count("—")
    dash_rate = round(1000 * dashes / n, 1)
    hard = [h for h in hits if h["severity"] == "hard"]
    soft = [h for h in hits if h["severity"] == "soft"]
    soft_rate = round(1000 * len(soft) / n, 1)
    return {"words": n, "hard": hard, "soft": soft, "soft_per_1000": soft_rate,
            "em_dashes_per_1000": dash_rate,
            "pass": not hard and soft_rate <= 4.0 and dash_rate <= 6.0}


def thesis_report(draft: Path) -> dict:
    meta, body = split_front_matter(draft.read_text())
    problems = []
    role = meta.get("thesis_role", "").lower()
    if role not in THESIS_ROLES:
        problems.append(f"front matter needs thesis_role: one of {', '.join(THESIS_ROLES)}")
    if not meta.get("claim"):
        problems.append("front matter needs claim: the one sentence this chapter argues")
    sec = re.search(r"(?im)^#{2,3} +(counterargument|the strongest objection|the case against)[^\n]*\n(.*?)(?=^#{1,3} |\Z)",
                    body, re.S)
    if not sec:
        problems.append("needs a '## The strongest objection' (or '## Counterargument') section")
    elif len(words(sec.group(2))) < 60:
        problems.append("objection section is under 60 words; steelman it properly")
    if not re.search(r"(?im)^#{2,3} +where this leaves the thesis", body):
        problems.append("needs a '## Where this leaves the thesis' section (advanced, tested, or bent)")
    return {"role": role or None, "problems": problems, "pass": not problems}


def print_report(name: str, rep: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps({name: rep}, indent=2))
        return
    print(f"{name}: {'PASS' if rep['pass'] else 'FAIL'}")
    for k, v in rep.items():
        if k == "pass":
            continue
        if isinstance(v, list) and v and isinstance(v[0], (str, dict)):
            print(f"  {k}:")
            for item in v[:20]:
                print(f"    - {item if isinstance(item, str) else item.get('match')}")
        else:
            print(f"  {k}: {v}")


def cmd_check_provenance(a) -> int:
    rep = provenance_report(Path(a.book), Path(a.draft))
    print_report("provenance", rep, a.json)
    return 0 if rep["pass"] else 1


def cmd_check_ai_tells(a) -> int:
    rep = ai_tell_report(Path(a.draft))
    print_report("ai-tells", rep, a.json)
    return 0 if rep["pass"] else 1


def cmd_check_thesis(a) -> int:
    rep = thesis_report(Path(a.draft))
    print_report("thesis", rep, a.json)
    return 0 if rep["pass"] else 1


GATES = ("provenance", "ai_tells", "thesis", "author_voice")


def gate_all(book: Path, draft: Path) -> dict:
    """The three core gates, plus the author-voice gate once the author's words are logged for this draft."""
    p, t, h = provenance_report(book, draft), ai_tell_report(draft), thesis_report(draft)
    v = author_voice_report(book, draft)
    n = 4 if v["applies"] else 3
    return {"provenance": p, "ai_tells": t, "thesis": h, "author_voice": v, "checks": n,
            "pass": p["pass"] and t["pass"] and h["pass"] and v["pass"]}


def cmd_tournament(a) -> int:
    book = Path(a.book)
    require_writing(book, load_config(book), a, "tournament")
    d = book / "drafts" / a.chapter
    runs = sorted(d.glob("run-*.md"))
    if not runs:
        die(f"no drafts in {d} (expected run-1.md, run-2.md, ...)")
    rows = ["| run | words | claims cited/total | unsupported | confirm-before-print | AI tells (hard/soft per 1k) "
            "| thesis | author's words | all gates |",
            "|---|---|---|---|---|---|---|---|---|"]
    results, run_words, run_checks = {}, {}, {}
    for r in runs:
        g = gate_all(book, r)
        results[r.stem] = g["pass"]
        run_words[r.stem] = g["ai_tells"]["words"]
        run_checks[r.stem] = g["checks"]
        p, t, h, v = g["provenance"], g["ai_tells"], g["thesis"], g["author_voice"]
        rows.append(f"| {r.stem} | {t['words']} | {p['cited'] + p['opinion']}/{p['claims']} | {len(p['unsupported'])} "
                    f"| {len(p['confirm_before_print'])} | {len(t['hard'])}/{t['soft_per_1000']} | {'ok' if h['pass'] else 'FAIL'} "
                    f"| {('ok' if v['pass'] else 'FAIL') if v['applies'] else 'n/a'} | {'PASS' if g['pass'] else 'fail'} |")
    eligible = [k for k, v in results.items() if v]
    out = [f"# Tournament: {a.chapter}", "",
           "Deterministic gates first (this table). Only drafts that pass every gate are eligible.",
           "Then judge the eligible drafts head to head with prompts/07-tournament.md and record the verdict below.",
           "", *rows, "",
           f"Eligible: {', '.join(eligible) if eligible else 'none. Revise or re-run drafts.'}", "",
           "## Judge verdict", "", "(winner, runner-up, and the one thing to steal from each loser)", ""]
    sb = d / "scoreboard.md"
    if sb.exists() and "## Judge verdict" in sb.read_text():
        prior = sb.read_text().split("## Judge verdict", 1)[1]
        out = out[:-4] + ["## Judge verdict" + prior.rstrip("\n"), ""]
    sb.write_text("\n".join(out))
    print("\n".join(rows))
    print(f"eligible: {', '.join(eligible) or 'none'}  (scoreboard: {sb})")
    if eligible:  # the shortest passing draft, so the estimate never rounds up
        best = min(eligible, key=lambda k: run_words[k])
        fund_milestone("chapter-passed", f"{book.resolve()}:{a.chapter}",
                       f"{chapter_label(a.chapter)} passed all {run_checks[best]} checks \u2713.", a,
                       words=run_words[best])
    return 0


def cmd_promote(a) -> int:
    book = Path(a.book)
    require_writing(book, load_config(book), a, "promote")
    src = book / "drafts" / a.chapter / f"{a.run}.md"
    if not src.is_file():
        die(f"no such draft: {src}")
    g = gate_all(book, src)
    if not g["pass"]:
        for name in GATES:
            if not g[name]["pass"]:
                print_report(name, g[name], False)
        die("draft fails a gate; not promoted", 1)
    (book / "chapters").mkdir(exist_ok=True)
    dest = book / "chapters" / f"{a.chapter}.md"
    shutil.copyfile(src, dest)
    print(f"promoted {src.name} -> {dest}")
    spine = spine_chapters(book)
    done = {p.stem for p in (book / "chapters").glob("*.md")}
    if spine and set(spine) <= done:
        total = sum(ai_tell_report(book / "chapters" / f"{c}.md")["words"] for c in spine)
        fund_milestone("full-draft", f"{book.resolve()}",
                       f"Full draft done: all {len(spine)} chapters passed every check \u2713.", a, words=total)
    else:
        fund_milestone("chapter-passed", f"{book.resolve()}:{a.chapter}",
                       f"{chapter_label(a.chapter)} passed all {g['checks']} checks \u2713.", a,
                       words=g["ai_tells"]["words"])
    return 0


def chapter_label(chapter: str) -> str:
    m = re.fullmatch(r"ch0*(\d+)", chapter, re.I)
    return f"Chapter {m.group(1)}" if m else f"Chapter {chapter}"


def spine_chapters(book: Path) -> list[str]:
    f = book / "spine.md"
    return re.findall(r"(?m)^\|\s*(ch\d+)\s*\|", f.read_text()) if f.is_file() else []


# ---------------------------------------------------------------- phases
# research -> synthesis -> proposal (optional) -> writing. Each phase has exit criteria this script
# checks. Drafting commands refuse to run before the writing phase unless the author overrides, and
# every override is logged. Books made before phases existed (no "phase" key) count as writing.
DEFAULT_COVERAGE_THRESHOLD = 0.75
DEFAULT_MIN_VOICE_ENTRIES = 5


def save_config(book: Path, cfg: dict) -> None:
    (book / "ghostwriter.json").write_text(json.dumps(cfg, indent=2) + "\n")


def book_phase(cfg: dict) -> str:
    ph = cfg.get("phase") or "writing"
    return ph if ph in PHASES else "writing"


def research_cfg(cfg: dict) -> dict:
    return cfg.get("research") or {}


def now_stamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")


def checklist(text: str, heading_rx: str) -> list[tuple[bool, str]]:
    """Checkbox items (- [ ] / - [x]) under the first heading matching heading_rx."""
    m = re.search(rf"(?im)^#{{1,3}} +{heading_rx}[^\n]*\n(.*?)(?=^#{{1,3}} |\Z)", text, re.S)
    if not m:
        return []
    return [(c.lower() == "x", t.strip()) for c, t in re.findall(r"(?m)^\s*[-*] \[( |x|X)\] (.+)$", m.group(1))]


def filled(p: Path) -> bool:
    return p.is_file() and p.stat().st_size > 0 and "TODO" not in p.read_text()[:400]


def research_criteria(book: Path, cfg: dict) -> list[tuple[str, bool, str]]:
    rc = research_cfg(cfg)
    out = []
    plan = book / "research" / "PLAN.md"
    items = checklist(plan.read_text(), "exit criteria") if plan.is_file() else []
    done = sum(ok for ok, _ in items)
    out.append(("research plan: every exit criterion ticked by the author", bool(items) and done == len(items),
                f"{done}/{len(items)} ticked in research/PLAN.md" if items else "no '## Exit criteria' checklist in research/PLAN.md"))
    hyp = book / "input" / "thesis" / "working-hypothesis.md"
    out.append(("a working hypothesis is written down (not a pick)", filled(hyp),
                "input/thesis/working-hypothesis.md" if filled(hyp) else "run `hypothesis --set`"))
    need = int(rc.get("min_voice_entries", DEFAULT_MIN_VOICE_ENTRIES))
    n = len(load_voice_log(book))
    out.append((f"the author's own words logged ({need}+ entries)", n >= need, f"{n} in author-voice/log.jsonl"))
    if rc.get("require_coverage", True):
        thr = float(rc.get("coverage_threshold", DEFAULT_COVERAGE_THRESHOLD))
        reps = [(f, coverage_report(json.loads(f.read_text()))) for f in coverage_files(book)]
        if not reps:
            out.append((f"coverage at {thr:.0%}+", False, "no research/coverage/*.json yet (`scaffold coverage`)"))
        for f, r in reps:
            out.append((f"coverage at {thr:.0%}+ ({f.stem}, {r['mode']})", r["score"] >= thr,
                        f"{r['score']:.0%}: {r['summary']}"))
    bad = [f"{f.name}: {p}" for f in research_notes(book) for p in sources_table_problems(f.read_text())]
    out.append(("every research citation has an honest status", not bad, "; ".join(bad[:3]) or "ok"))
    return out


def synthesis_criteria(book: Path, cfg: dict) -> list[tuple[str, bool, str]]:
    thesis = book / cfg.get("thesis_file", "thesis.md")
    picked = filled(thesis) and bool(re.search(r"(?ims)^## The statement\n+\S", thesis.read_text()))
    rows = spine_chapters(book)
    idx = load_index(book)["sources"]
    from_research = sum(1 for s in idx if s.get("from_research"))
    return [("the author picked a thesis (thesis.md filled)", picked, "thesis.md" if picked else "thesis.md still TODO"),
            ("the spine has chapters", bool(rows), f"{len(rows)} chapter rows in spine.md"),
            ("research is registered as citable sources", from_research > 0,
             f"{from_research} sources from research/ (`ingest-research`)")]


def proposal_criteria(book: Path, cfg: dict) -> list[tuple[str, bool, str]]:
    return [("proposal.md written", filled(book / "proposal.md"), "proposal.md")]


CRITERIA = {"research": research_criteria, "synthesis": synthesis_criteria, "proposal": proposal_criteria}


def phase_criteria(book: Path, cfg: dict, phase: str) -> list[tuple[str, bool, str]]:
    fn = CRITERIA.get(phase)
    return fn(book, cfg) if fn else []


def cmd_phase(a) -> int:
    book = Path(a.book)
    cfg = load_config(book)
    ph = book_phase(cfg)
    if a.action == "require":
        if ph != a.phase:
            print(f"{book.name} is in the {ph} phase, not {a.phase}.", file=sys.stderr)
            return 1
        return 0
    if a.action == "status":
        crit = phase_criteria(book, cfg, ph)
        print(f"phase: {ph}" + ("" if "phase" in cfg else " (no phase recorded: a book from before phases)"))
        for name, ok, detail in crit:
            print(f"  [{'x' if ok else ' '}] {name}: {detail}")
        if not crit:
            print("  (no exit criteria: this is the last phase)")
        hyp = book / "input" / "thesis" / "working-hypothesis.md"
        if hyp.is_file():
            print(f"  working hypothesis: {first_statement(hyp.read_text())}")
        if ph != "writing":
            print("  drafting commands are off until the writing phase.")
        return 0
    # advance
    order = list(PHASES)
    target = a.to or (order[order.index(ph) + 1] if ph != "writing" else None)
    if not target:
        die("already in the writing phase (the last one)")
    if target not in PHASES:
        die(f"--to must be one of {', '.join(PHASES)}")
    back = order.index(target) < order.index(ph)
    entry = {"from": ph, "to": target, "at": now_stamp()}
    if back:  # going back (a thesis pivot, a gap found) is always allowed, with a reason
        if not a.reason and not a.override:
            die("going back a phase needs --reason")
        entry["reason"] = a.reason or a.override
    else:
        skipped = order[order.index(ph):order.index(target)]
        skipped = [p for p in skipped if p != "proposal"]  # the proposal phase is optional
        unmet = [(p, n, d) for p in skipped for n, ok, d in phase_criteria(book, cfg, p) if not ok]
        if unmet and not a.override:
            print(f"not ready to leave {ph}:", file=sys.stderr)
            for p, n, d in unmet:
                print(f"  [ ] ({p}) {n}: {d}", file=sys.stderr)
            print("The author can move on anyway with --override \"why\" (logged).", file=sys.stderr)
            return 1
        if unmet:
            entry["override"] = a.override
            entry["unmet"] = [n for _, n, _ in unmet]
    cfg["phase"] = target
    cfg.setdefault("phase_history", []).append(entry)
    save_config(book, cfg)
    print(f"{book.name}: {ph} -> {target}" + (" (override logged)" if entry.get("override") else ""))
    if ph == "research" and target == "synthesis" and not entry.get("override"):
        n = len(phase_criteria(book, cfg, "research"))
        fund_milestone("research-ready", f"{book.resolve()}",
                       f"Research phase complete: all {n} exit criteria met ✓.", a)
    return 0


def require_writing(book: Path, cfg: dict, a, what: str) -> None:
    """Drafting commands run only in the writing phase, unless the author overrides (logged)."""
    ph = book_phase(cfg)
    if ph == "writing":
        return
    why = getattr(a, "override_phase", None)
    if not why:
        die(f"{book.name} is in the {ph} phase. `{what}` is a drafting command and stays off until the author "
            f"moves to writing (`phase status` shows what is left). To run it anyway: --override-phase \"why\".")
    cfg.setdefault("phase_overrides", []).append({"at": now_stamp(), "phase": ph, "command": what, "why": why})
    save_config(book, cfg)
    print(f"note: running `{what}` in the {ph} phase (override logged: {why})", file=sys.stderr)


# ---------------------------------------------------------------- thesis pivots
def first_statement(text: str) -> str:
    _, body = split_front_matter(text)
    for line in body.splitlines():
        s = line.strip()
        if s and not s.startswith(("#", ">", "<!--", "*Working")):
            return s[:200]
    return "(empty)"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "untitled"


def archive(book: Path, src: Path, reason: str, label: str) -> Path:
    d = book / "input" / "thesis" / "archive"
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    dest = d / f"{stamp}-{label}.md"
    _, body = split_front_matter(src.read_text())
    dest.write_text(f"---\nsuperseded: {now_stamp()}\nwas: {src.relative_to(book)}\nreason: {reason}\n---\n\n{body}")
    return dest


def cmd_hypothesis(a) -> int:
    book = Path(a.book)
    cfg = load_config(book)
    f = book / "input" / "thesis" / "working-hypothesis.md"
    if not a.set:
        print(first_statement(f.read_text()) if f.is_file() else "no working hypothesis yet")
        for p in sorted((book / "input" / "thesis" / "archive").glob("*-hypothesis.md")):
            meta, body = split_front_matter(p.read_text())
            print(f"  superseded {meta.get('superseded')}: {first_statement(body)}  (why: {meta.get('reason')})")
        return 0
    if f.is_file() and filled(f):
        if not a.reason:
            die("a working hypothesis already exists. Say why it is being replaced: --reason \"...\"")
        print(f"archived -> {archive(book, f, a.reason, 'hypothesis').relative_to(book)}")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"# Working hypothesis\n\n*Working hypothesis, not a pick. Set {now_stamp()} in the "
                 f"{book_phase(cfg)} phase. The author picks the thesis in synthesis.*\n\n{a.set.strip()}\n")
    print(f"working hypothesis set ({book_phase(cfg)} phase)")
    return 0


def cmd_supersede(a) -> int:
    book = Path(a.book)
    cfg = load_config(book)
    targets = [book / cfg.get("thesis_file", "thesis.md"), book / "input" / "thesis" / "options.md"]
    moved = []
    for t in targets:
        if filled(t):
            moved.append(archive(book, t, a.reason, "pick" if t.name != "options.md" else "options"))
            if t.name == "options.md":
                t.unlink()
            else:
                shutil.copyfile(TEMPLATE / "thesis.md", t)
    if not moved:
        die("nothing to supersede: thesis.md and input/thesis/options.md are empty or TODO")
    cfg.setdefault("thesis_history", []).append({"at": now_stamp(), "reason": a.reason,
                                                 "archived": [str(m.relative_to(book)) for m in moved]})
    save_config(book, cfg)
    for m in moved:
        print(f"archived -> {m.relative_to(book)}")
    print("thesis.md reset. The old options stay in the archive, with the reason, for later chapters to revisit.")
    return 0


# ---------------------------------------------------------------- author voice
# The author's own words are the spine. Quotes, metaphors and analogies are logged verbatim with a
# timestamp. A draft that builds on an entry must keep it word for word.
VOICE_KINDS = ("quote", "metaphor", "analogy", "belief", "correction", "story")


def voice_log_path(book: Path) -> Path:
    return book / "author-voice" / "log.jsonl"


def load_voice_log(book: Path) -> list[dict]:
    f = voice_log_path(book)
    out = []
    if f.is_file():
        for line in f.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def cmd_voice_log(a) -> int:
    book = Path(a.book)
    load_config(book)
    if a.list or not a.text:
        for e in load_voice_log(book):
            ch = f" ({', '.join(e['chapters'])})" if e.get("chapters") else ""
            print(f"{e['id']} {e['at']} {e['kind']}{ch}: “{e['text']}”")
        return 0
    if a.kind not in VOICE_KINDS:
        die(f"--kind must be one of {', '.join(VOICE_KINDS)}")
    log = load_voice_log(book)
    vid = f"V{len(log) + 1:03d}"
    e = {"id": vid, "at": now_stamp(), "kind": a.kind, "text": a.text.strip()}
    if a.context:
        e["context"] = a.context
    if a.chapter:
        e["chapters"] = [c.strip() for c in a.chapter.split(",") if c.strip()]
    voice_log_path(book).parent.mkdir(parents=True, exist_ok=True)
    with voice_log_path(book).open("a") as fh:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    render_voice_log(book)
    print(f"{vid} logged ({a.kind})")
    return 0


def render_voice_log(book: Path) -> None:
    lines = ["# The author's own words", "",
             "Generated from `log.jsonl` by `voice-log`. Verbatim, timestamped. Drafts build around these and",
             "keep them word for word (`check-author-voice`). Never paraphrase them away.", ""]
    for e in load_voice_log(book):
        ch = f" → {', '.join(e['chapters'])}" if e.get("chapters") else ""
        lines.append(f"- **{e['id']}** ({e['at']}, {e['kind']}{ch}): “{e['text']}”"
                     + (f"  \n  _context: {e['context']}_" if e.get("context") else ""))
    (book / "author-voice" / "log.md").write_text("\n".join(lines) + "\n")


def norm(text: str) -> str:
    t = text.lower()
    for a_, b_ in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("—", "-"), ("–", "-")):
        t = t.replace(a_, b_)
    t = re.sub(r"[*_`]", "", t)  # emphasis markup is not a change of words
    return re.sub(r"\s+", " ", t).strip()


def author_voice_report(book: Path, draft: Path) -> dict:
    meta, body = split_front_matter(draft.read_text())
    log = {e["id"]: e for e in load_voice_log(book)}
    listed = [v.strip() for v in re.split(r"[,\s]+", meta.get("author_voice", "")) if v.strip()]
    chapter = meta.get("chapter", draft.parent.name if draft.parent.name.startswith("ch") else "")
    tagged = [vid for vid, e in log.items() if chapter and chapter in e.get("chapters", [])]
    unknown = [v for v in listed if v not in log]
    required = list(dict.fromkeys([v for v in listed if v in log] + tagged))
    text = norm(body)
    missing = [f"{v}: “{log[v]['text']}”" for v in required
               if norm(log[v]["text"]).strip(" .,;:!?\"'") not in text]
    return {"applies": bool(log) and bool(required or listed), "required": required, "unknown_ids": unknown,
            "paraphrased_or_missing": missing, "pass": not unknown and not missing}


def cmd_check_author_voice(a) -> int:
    rep = author_voice_report(Path(a.book), Path(a.draft))
    print_report("author-voice", rep, a.json)
    return 0 if rep["pass"] else 1


# ---------------------------------------------------------------- research notes
RESEARCH_KINDS = {"borrow": "borrow-scan", "analogy": "analogy", "scorecard": "scorecard", "theory": "theory"}
SOURCES_TABLE_RX = re.compile(r"(?ims)^#{2,3} +sources[^\n]*\n(.*?)(?=^#{1,3} |\Z)")


def research_notes(book: Path) -> list[Path]:
    d = book / "research"
    return sorted(p for p in d.glob("*.md") if p.name not in ("PLAN.md", "README.md")) if d.is_dir() else []


def table_rows(block: str) -> list[list[str]]:
    rows = []
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("|") and not re.fullmatch(r"\|[\s:|-]+\|?", s):
            rows.append([c.strip() for c in s.strip("|").split("|")])
    return rows


def sources_table(text: str) -> list[dict]:
    """The `## Sources` table of a research note: | key | citation | url | status | how |"""
    m = SOURCES_TABLE_RX.search(text)
    if not m:
        return []
    rows = table_rows(m.group(1))
    if not rows:
        return []
    head = [h.lower() for h in rows[0]]
    return [dict(zip(head, r)) for r in rows[1:] if any(r)]


def sources_table_problems(text: str) -> list[str]:
    out = []
    for r in sources_table(text):
        key = r.get("key", "?")
        st = r.get("status", "").strip("* ").lower()
        if st not in CITE_STATUSES:
            out.append(f"source {key}: status '{st or 'blank'}' is not one of {', '.join(CITE_STATUSES)}")
        elif st in ("verified", "secondhand") and not r.get("how", "").strip(" -"):
            out.append(f"source {key}: {st} needs a 'how' (what was checked, or the source that cites it)")
    return out


def section(text: str, heading_rx: str) -> str | None:
    m = re.search(rf"(?ims)^(#{{2,3}}) +{heading_rx}[^\n]*\n(.*?)(?=^#{{1,2}} |\Z)", text)
    return m.group(2) if m else None


def subsections(text: str, parent_rx: str) -> list[tuple[str, str]]:
    body = section(text, parent_rx) or ""
    return re.findall(r"(?ms)^### +([^\n]+)\n(.*?)(?=^### |\Z)", body)


def research_report(path: Path) -> dict:
    text = path.read_text()
    meta, body = split_front_matter(text)
    kind = meta.get("type", "")
    problems = []
    if kind == "borrow-scan":
        doms = subsections(body, "domains")
        if len(doms) < 2:
            problems.append("needs 2+ domains as '### <domain>' under '## Domains'")
        for name, txt in doms:
            for need, rx in (("mechanisms", r"mechanism"), ("signature practices", r"signature practice"),
                             ("evidence", r"evidence"), ("failure modes / dark side", r"failure mode|dark side"),
                             ("translation", r"translat")):
                if not re.search(rf"(?im)^\s*[-*]?\s*\**({rx})", txt):
                    problems.append(f"domain '{name.strip()}' is missing: {need}")
    elif kind == "analogy":
        if not meta.get("analogy"):
            problems.append("front matter needs analogy: \"X is like Y\" (the author's words)")
        for need in ("what the other world does", "translation", "where the analogy breaks", "evidence strength"):
            if section(body, need) is None:
                problems.append(f"needs a '## {need.capitalize()}' section")
        brk = section(body, "where the analogy breaks")
        if brk is not None and len(words(brk)) < 40:
            problems.append("'Where the analogy breaks' is under 40 words: find where it really breaks")
        ev = section(body, "evidence strength")
        if ev is not None and not re.search(r"\[(S|M|W|A|C)\]", ev):
            problems.append("evidence strength needs a grade: [S] strong, [M] moderate, [W] weak, [A] anecdotal, [C] contested")
    elif kind == "scorecard":
        tbl = section(body, "scorecard") or ""
        rows = table_rows(tbl)
        head = [h.lower() for h in rows[0]] if rows else []
        if "status" not in head or not any("replicat" in h for h in head):
            problems.append("needs a '## Scorecard' table with Status and Replication columns")
        else:
            si, ri = head.index("status"), next(i for i, h in enumerate(head) if "replicat" in h)
            data = rows[1:]
            if len(data) < 3:
                problems.append("rate at least 3 well-known findings")
            for r in data:
                st = re.sub(r"[^a-z]", " ", (r[si] if si < len(r) else "").lower()).split()
                if not st or st[0] not in ("holds", "contested", "misread"):
                    problems.append(f"'{r[0]}': status must start with HOLDS, CONTESTED or MISREAD")
                if ri >= len(r) or not r[ri].strip(" -"):
                    problems.append(f"'{r[0]}': replication status is blank")
        if section(body, "foils") is None:
            problems.append("needs a '## Foils' section: which findings the book uses as overhyped foils")
    elif kind == "theory":
        props = subsections(body, "propositions")
        if len(props) < 2:
            problems.append("needs 2+ propositions as '### P1 ...' under '## Propositions'")
        for name, txt in props:
            if not re.search(r"(?i)wrong if", txt):
                problems.append(f"proposition '{name.strip()[:40]}' has no falsifier ('Wrong if: ...')")
        pred = [r for r in table_rows(section(body, "predictions") or "")[1:] if any(r)]
        if not 5 <= len(pred) <= 8:
            problems.append(f"needs 5 to 8 dated predictions in a '## Predictions' table (has {len(pred)})")
        undated = [r[0] for r in pred if not re.search(r"\b20\d\d\b", " ".join(r))]
        if undated:
            problems.append(f"predictions without a year: {', '.join(undated)}")
        if not re.search(r"(?im)^## +decision rule: *\S", body):
            problems.append("needs '## Decision rule: The <Name> Test', a rule a reader can apply")
        sc = section(body, "scoring")
        if sc is not None and "judgment" not in sc.lower():
            problems.append("scores are judgment calls: say so in the Scoring section")
        thin = section(body, "where the evidence is thin")
        if thin is None or len(re.findall(r"(?m)^\s*(?:[-*]|\d+\.) ", thin)) < 2:
            problems.append("needs '## Where the evidence is thin' with 2+ honest items")
    else:
        problems.append(f"front matter type: must be one of {', '.join(RESEARCH_KINDS.values())}")
    problems += sources_table_problems(body)
    return {"type": kind or None, "problems": problems, "pass": not problems}


def cmd_check_research(a) -> int:
    rep = research_report(Path(a.note))
    print_report("research", rep, a.json)
    return 0 if rep["pass"] else 1


def cmd_scaffold(a) -> int:
    book = Path(a.book)
    load_config(book)
    kinds = list(RESEARCH_KINDS) + ["coverage"]
    if a.kind not in kinds:
        die(f"kind must be one of {', '.join(kinds)}")
    ext = "json" if a.kind == "coverage" else "md"
    tpl = book / "research" / "templates" / f"{a.kind}.{ext}"
    if not tpl.is_file():
        tpl = TEMPLATE / "research" / "templates" / f"{a.kind}.{ext}"
    sub = "coverage/" if a.kind == "coverage" else ""
    dest = book / "research" / f"{sub}{date.today().strftime('%Y-%m')}-{slug(a.name)}.{ext}"
    if dest.exists():
        die(f"{dest} already exists")
    dest.parent.mkdir(parents=True, exist_ok=True)
    title = a.name.replace('"', "'")
    dest.write_text(tpl.read_text().replace("{{title}}", title).replace("{{date}}", date.today().isoformat()))
    print(f"created {dest.relative_to(book)} from the {a.kind} template")
    return 0


def cmd_ingest_research(a) -> int:
    """Register each row of a research note's Sources table as a source, once. Keeps its status."""
    book = Path(a.book)
    load_config(book)
    note = resolve(book, a.note)
    rel = str(note.resolve().relative_to(book.resolve())) if note.resolve().is_relative_to(book.resolve()) else note.name
    mp_file = book / "research" / "source-map.json"
    mp = json.loads(mp_file.read_text()) if mp_file.is_file() else {}
    rows = sources_table(note.read_text())
    if not rows:
        die(f"{note.name} has no '## Sources' table (| key | citation | url | status | how |)")
    probs = sources_table_problems(note.read_text())
    if probs:
        die("fix the Sources table first:\n  " + "\n  ".join(probs))
    for r in rows:
        k = f"{rel}#{r.get('key')}"
        if k in mp:
            print(f"{r.get('key')} -> {mp[k]} (already registered)")
            continue
        st = r["status"].strip("* ").lower()
        how = r.get("how", "").strip() or None
        url = r.get("url", "").strip()
        body = (f"Link: {url}\n\n" if url else "") + f"From research note `{rel}`, key {r.get('key')}.\n\n{r.get('citation', '')}\n"
        sid = register_source(book, a.kind, r.get("citation", r.get("key", ""))[:160], url or note.name,
                              date.today().isoformat(), body, None, status=st,
                              how=how if st == "verified" else None,
                              extra={"from_research": k, **({"via": how} if st == "secondhand" and how else {})})
        mp[k] = sid
        print(f"{r.get('key')} -> {sid} ({st})")
    mp_file.write_text(json.dumps(mp, indent=2) + "\n")
    return 0


# ---------------------------------------------------------------- coverage
# A coverage file (research/coverage/*.json) has a mechanism key (each item maps to exactly one), a
# situation list grounded in an established framework, and grid cells; and/or a breadth checklist of
# domains (e.g. the major kinds of groups people belong to). "mode" picks which score the phase uses.
CELL_STATES = ("filled", "dup", "empty", "na")


def coverage_files(book: Path) -> list[Path]:
    d = book / "research" / "coverage"
    return sorted(d.glob("*.json")) if d.is_dir() else []


def coverage_report(data: dict) -> dict:
    mechs = {m["code"]: m for m in data.get("mechanisms", [])}
    sits = {s["code"]: s for s in data.get("situations", [])}
    items = data.get("items", [])
    problems = []
    # MECE: every item maps to exactly one known mechanism
    for it in items:
        m = it.get("mechanism")
        if not isinstance(m, str) or not m:
            problems.append(f"item '{it.get('name')}' must map to exactly one mechanism")
        elif m not in mechs:
            problems.append(f"item '{it.get('name')}' maps to unknown mechanism {m}")
    no_items = sorted(set(mechs) - {it.get("mechanism") for it in items if isinstance(it.get("mechanism"), str)}) if items else []
    seen, merges = {}, []
    for it in items:
        k = re.sub(r"[^a-z0-9]+", " ", str(it.get("name", "")).lower()).strip()
        if k in seen:
            merges.append(f"'{it.get('name')}' appears twice ({seen[k]}, {it.get('domain', '?')}): merge")
        else:
            seen[k] = it.get("domain", "?")
    no_evidence = [it.get("name") for it in items if str(it.get("evidence", "none")).lower() in ("", "none")]
    # grid
    cells = {}
    for c in data.get("cells", []):
        key = (c.get("situation"), c.get("mechanism"))
        if key[0] not in sits or key[1] not in mechs:
            problems.append(f"cell {key} uses an unknown situation or mechanism")
            continue
        if key in cells:
            problems.append(f"cell {key[0]}×{key[1]} is listed twice")
        st = c.get("status", "empty")
        if st not in CELL_STATES:
            problems.append(f"cell {key[0]}×{key[1]}: status must be one of {', '.join(CELL_STATES)}")
        if st == "dup" and not c.get("dup_of"):
            problems.append(f"cell {key[0]}×{key[1]} is a dup but has no dup_of")
        if st == "filled" and str(c.get("evidence", "none")).lower() in ("", "none"):
            no_evidence.append(f"{key[0]}×{key[1]}: {c.get('practice', '?')}")
        cells[key] = c
    total = len(sits) * len(mechs)
    st_count = Counter(c.get("status", "empty") for c in cells.values())
    unassessed = total - len(cells)
    meaningful = total - st_count["na"]
    filled_n = st_count["filled"] + st_count["dup"]
    grid_score = filled_n / meaningful if meaningful else 0.0
    empties = [c for c in cells.values() if c.get("status", "empty") == "empty"]
    row_gaps = Counter(c["situation"] for c in empties)
    ranked = sorted(empties, key=lambda c: (int(c.get("priority", 99)), -row_gaps[c["situation"]], c["situation"], c["mechanism"]))
    dup_cells = [f"{c['situation']}×{c['mechanism']} -> {c['dup_of']}" for c in cells.values() if c.get("status") == "dup"]
    # breadth checklist
    min_p = int(data.get("min_practices_per_domain", 3))
    by_dom = Counter(it.get("domain") for it in items if str(it.get("evidence", "none")).lower() not in ("", "none"))
    doms = data.get("domains", [])
    req = [d for d in doms if d.get("required", True)]
    covered = [d for d in req if by_dom[d["name"]] >= min_p]
    thin = [f"{d['name']} ({by_dom[d['name']]}/{min_p})" for d in req if by_dom[d["name"]] < min_p]
    breadth = len(covered) / len(req) if req else 0.0
    mode = data.get("mode") or ("grid" if sits else "breadth")
    score = breadth if mode == "breadth" else grid_score
    summary = (f"{len(covered)}/{len(req)} required domains with {min_p}+ evidenced practices" if mode == "breadth"
               else f"{filled_n}/{meaningful} meaningful cells filled, {st_count['empty']} empty, {unassessed} unassessed")
    if not data.get("framework", {}).get("name") and sits:
        problems.append("situations need a grounding framework: framework.name + framework.citation")
    return {"mode": mode, "score": round(score, 4), "summary": summary,
            "grid": {"cells": total, "na": st_count["na"], "meaningful": meaningful, "filled": filled_n,
                     "empty": st_count["empty"], "unassessed": unassessed, "score": round(grid_score, 4)},
            "breadth": {"required": len(req), "covered": len(covered), "thin": thin, "score": round(breadth, 4)},
            "ranked_empty": [f"{c['situation']}×{c['mechanism']}" + (f": {c['why']}" if c.get("why") else "")
                             for c in ranked],
            "merges": merges + dup_cells, "no_evidence": no_evidence, "mechanisms_without_items": no_items,
            "problems": problems}


def coverage_markdown(name: str, data: dict, r: dict, thr: float) -> str:
    g, b = r["grid"], r["breadth"]
    L = [f"# Coverage report: {data.get('title', name)}", "",
         f"Generated by `ghostwriter.py coverage` on {date.today().isoformat()}. Do not hand-edit; edit the JSON.", "",
         f"**Score ({r['mode']}): {r['score']:.0%}** against a {thr:.0%} exit threshold. {r['summary']}.", ""]
    if g["cells"]:
        L += ["## Grid", "", "| cells | n/a | meaningful | filled (incl. dups) | empty | unassessed | coverage |",
              "|---|---|---|---|---|---|---|",
              f"| {g['cells']} | {g['na']} | {g['meaningful']} | {g['filled']} | {g['empty']} | {g['unassessed']} | {g['score']:.0%} |", "",
              "\"Filled\" means a credible borrowed practice exists, not that it is proven for this audience.", ""]
    if b["required"]:
        L += ["## Breadth checklist", "", f"{b['covered']}/{b['required']} required domains covered ({b['score']:.0%}).", ""]
        L += [f"- thin: {t}" for t in b["thin"]] + [""]
    for title, key in (("Empty cells, ranked", "ranked_empty"), ("Merge or dedupe", "merges"),
                       ("No evidence yet", "no_evidence"), ("Mechanisms with no items", "mechanisms_without_items"),
                       ("Problems (fix the JSON)", "problems")):
        if r[key]:
            L += [f"## {title}", ""] + [f"{i}. {x}" if key == "ranked_empty" else f"- {x}"
                                        for i, x in enumerate(r[key], 1)] + [""]
    return "\n".join(L)


def cmd_coverage(a) -> int:
    book = Path(a.book)
    cfg = load_config(book)
    files = [resolve(book, a.file)] if a.file else coverage_files(book)
    if not files:
        die("no coverage files in research/coverage/ (`scaffold <book> coverage --name ...`)")
    thr = float(research_cfg(cfg).get("coverage_threshold", DEFAULT_COVERAGE_THRESHOLD))
    rc = 0
    for f in files:
        data = json.loads(f.read_text())
        r = coverage_report(data)
        if a.json:
            print(json.dumps({f.stem: r}, indent=2))
        else:
            out = f.with_suffix(".report.md")
            out.write_text(coverage_markdown(f.stem, data, r, thr))
            print(f"{f.stem}: {r['score']:.0%} ({r['mode']}): {r['summary']}  -> {out.relative_to(book) if out.is_relative_to(book) else out}")
            for x in r["ranked_empty"][:5]:
                print(f"  empty: {x}")
            for x in r["problems"][:10]:
                print(f"  problem: {x}")
        rc |= 1 if r["problems"] else 0
    return rc


# ---------------------------------------------------------------- status
def cmd_status(a) -> int:
    book = Path(a.book)
    cfg = load_config(book)
    def has(p):
        q = book / p
        return q.is_file() and q.stat().st_size > 0 and "TODO" not in q.read_text()[:400]
    qs = read_questions(book)
    chapters = sorted((book / "chapters").glob("*.md")) if (book / "chapters").is_dir() else []
    drafts = sorted(p.name for p in (book / "drafts").iterdir() if p.is_dir()) if (book / "drafts").is_dir() else []
    stages = [
        ("1 thesis options", any(p.name not in ("README.md", "working-hypothesis.md")
                                 for p in (book / "input" / "thesis").glob("*.md"))),
        ("2 thesis picked", has("thesis.md")),
        ("3 book spine", has("spine.md")),
        ("4 interview", f"{sum(q[1] for q in qs)}/{len(qs)} answered"),
        ("5 sources", f"{len(load_index(book)['sources'])} registered"),
        ("6 voice profile", (book / "voice" / "profile.json").is_file()),
        ("7 chapter drafts", f"{len(drafts)} chapter(s) drafted"),
        ("8 chapters passed gates", f"{len(chapters)} promoted"),
        ("9 revision notes", f"{len(list((book / 'revision-notes').glob('*.md')))} written" if (book / 'revision-notes').is_dir() else "0 written"),
    ]
    ph = book_phase(cfg)
    voice_n = len(load_voice_log(book))
    covs = [f"{f.stem} {coverage_report(json.loads(f.read_text()))['score']:.0%}" for f in coverage_files(book)]
    research = [
        ("phase", ph + ("" if "phase" in cfg else " (not recorded)")),
        ("working hypothesis", "set" if filled(book / "input" / "thesis" / "working-hypothesis.md") else "-"),
        ("author's words logged", f"{voice_n} entries"),
        ("research notes", f"{len(research_notes(book))} in research/"),
        ("coverage", ", ".join(covs) or "-"),
    ]
    print(f"{cfg.get('title')} by {cfg.get('author')}")
    for name, v in research:
        print(f"  {name:<26} {v}")
    print("  pipeline:")
    for name, v in stages:
        mark = v if isinstance(v, str) else ("done" if v else "-")
        print(f"  {name:<26} {mark}")
    return 0


# ---------------------------------------------------------------- fund
# Ghost Writer is free. Building it costs real money in AI time. At a moment where the author has
# just gotten value (declared in FUNDING-STATUS.json under value_moments), this CLI may print ONE
# plain line saying what the build cost and how much sponsors have covered. Rules:
#   - only at a declared value moment, never mid-task, never from the model (prompts/ and the
#     charter files never mention money; a test enforces that)
#   - the first value moment, then about every 10th, and at most once per 7 days
#   - silent when stdout is not a terminal, in CI, with GHOSTWRITER_NO_FUND=1 or --quiet,
#     after `fund --off`, or once the build cost is fully covered
#   - the line leads with the value the author just got, as a labeled ESTIMATE: words in the
#     passing chapter / a published drafting-speed benchmark, claimed at 50%, rounded DOWN. The
#     assumptions live in FUNDING-STATUS.json (value_estimates); `fund` prints the math and sources.
FUND_EVERY = 10
FUND_MIN_GAP = timedelta(days=7)
CI_VARS = ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE", "CIRCLECI", "TRAVIS", "JENKINS_URL",
           "TF_BUILD", "TEAMCITY_VERSION", "BITBUCKET_BUILD_NUMBER", "CODEBUILD_BUILD_ID", "DRONE")
DEFAULT_SPONSOR_URL = "https://github.com/sponsors/laurencewong"


def fund_state_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "ghostwriter" / "fund.json"


def load_fund_state() -> dict:
    try:
        st = json.loads(fund_state_path().read_text())
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def save_fund_state(st: dict) -> None:
    p = fund_state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st, indent=2) + "\n")
    except OSError:
        pass  # a read-only home must never break the real command


def load_funding_status(path: Path | None = None) -> dict | None:
    """FUNDING-STATUS.json, or None if it is missing or unreadable (the line then says 'pending')."""
    try:
        d = json.loads((path or FUNDING_STATUS_FILE).read_text())
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def money(x: float) -> str:
    return f"${x:,.0f}" if x >= 10 or float(x).is_integer() else f"${x:,.2f}"


def fund_numbers(fs: dict | None) -> tuple[float, float] | None:
    try:
        return float(fs["cost_usd"]), float(fs.get("raised_usd") or 0)
    except (TypeError, KeyError, ValueError):
        return None


def fund_covered(fs: dict | None) -> bool:
    n = fund_numbers(fs)
    return bool(n) and n[0] > 0 and n[1] >= n[0]


def fund_line(fs: dict | None) -> str:
    url = (fs or {}).get("sponsor_url") or DEFAULT_SPONSOR_URL
    n = fund_numbers(fs)
    if n is None:
        return f"Ghost Writer is free; what building it cost in AI is pending a tally. Chip in $3: {url}"
    cost, raised = n
    if fund_covered(fs):
        return f"Ghost Writer is free, and its ~{money(cost)} AI build cost is fully covered by sponsors. Thank you."
    return f"Ghost Writer is free; building it cost ~{money(cost)} in AI, {money(raised)} covered. Chip in $3: {url}"


# Value estimate. Defaults match FUNDING-STATUS.json; the file wins when present.
DEFAULT_BASELINE_WPH = 1140   # Karat et al. 1999: composing at a keyboard averaged 19.0 words/minute
DEFAULT_CLAIM_SHARE = 0.5     # claim at most half of the naive estimate
MIN_CLAIM_HOURS = 1 / 6       # under 10 minutes, say nothing about value


def value_assumptions(fs: dict | None) -> tuple[float, float]:
    ve = (fs or {}).get("value_estimates") or {}
    try:
        wph = float(ve.get("baseline_words_per_hour") or DEFAULT_BASELINE_WPH)
        share = float(ve.get("claim_share") or DEFAULT_CLAIM_SHARE)
    except (TypeError, ValueError):
        wph, share = DEFAULT_BASELINE_WPH, DEFAULT_CLAIM_SHARE
    return max(wph, 1.0), min(max(share, 0.0), DEFAULT_CLAIM_SHARE)  # never claim more than half


def value_estimate(words: int | None, fs: dict | None) -> dict | None:
    """Hours of drafting the author did not do: words / benchmark words-per-hour x claim share."""
    if not words or words <= 0:
        return None
    wph, share = value_assumptions(fs)
    naive = words / wph
    return {"words": int(words), "words_per_hour": wph, "claim_share": share,
            "naive_hours": naive, "claimed_hours": naive * share}


def hours_phrase(h: float) -> str | None:
    """Rounded DOWN, never shown as precise: 'about 40 minutes', 'about 1 hour', 'about 3 hours'."""
    if h < MIN_CLAIM_HOURS:
        return None
    if h < 1:
        return f"about {int(h * 60) // 10 * 10} minutes"
    half = int(h * 2) / 2  # down to the half hour
    if half == 1:
        return "about 1 hour"
    return f"about {half:g} hours"


def value_clause(est: dict | None) -> str:
    phrase = hours_phrase(est["claimed_hours"]) if est else None
    return f" That's {phrase} of drafting you didn't do (estimate: `ghostwriter.py fund`)." if phrase else ""


def declared_moments(fs: dict | None) -> set[str]:
    return {m.get("id") for m in (fs or {}).get("value_moments", []) if isinstance(m, dict)}


def fund_silenced(a=None) -> bool:
    if getattr(a, "quiet", False):
        return True
    if os.environ.get("GHOSTWRITER_NO_FUND", "").strip() not in ("", "0"):
        return True
    if any(os.environ.get(v, "").strip() not in ("", "0", "false") for v in CI_VARS):
        return True
    try:
        return not sys.stdout.isatty()
    except (AttributeError, ValueError):
        return True


def fund_milestone(moment: str, key: str, prefix: str, a=None, now: datetime | None = None,
                   fs: dict | None = None, words: int | None = None) -> str | None:
    """Count a value moment and maybe print the one-line ask. Returns the line printed, or None.
    words: prose words the author now holds at this moment (one chapter, or the whole draft)."""
    if fund_silenced(a):
        return None
    fs = load_funding_status() if fs is None else fs
    if fs is not None and moment not in declared_moments(fs):
        return None  # only at a moment the repo declared as the point the user got value
    if fund_covered(fs):
        return None
    st = load_fund_state()
    if st.get("off"):
        return None
    seen = st.get("seen", [])
    tag = f"{moment}:{hashlib.sha256(key.encode()).hexdigest()[:16]}"  # no book paths in the state file
    if tag in seen:
        return None  # each chapter's first pass counts once
    st["seen"] = (seen + [tag])[-500:]
    st["moments"] = int(st.get("moments", 0)) + 1
    st["since_ask"] = int(st.get("since_ask", 0)) + 1
    est = value_estimate(words, fs)
    if est:  # so `fund` can show the author the math behind their own last estimate
        st["last_estimate"] = {"moment": moment, "label": prefix.split(" passed")[0].split(":")[0],
                               "words": est["words"]}
    now = now or datetime.now(timezone.utc)
    last = st.get("last_ask")
    try:
        last_dt = datetime.fromisoformat(last) if last else None
    except ValueError:
        last_dt = None
    due = last_dt is None or (st["since_ask"] >= FUND_EVERY and now - last_dt >= FUND_MIN_GAP)
    line = None
    if due:
        line = f"{prefix}{value_clause(est)} {fund_line(fs)}"
        st["last_ask"], st["since_ask"], st["asks"] = now.isoformat(), 0, int(st.get("asks", 0)) + 1
        print(f"\n{line}")
    save_fund_state(st)
    return line


def cmd_fund(a) -> int:
    if a.off or a.on:
        st = load_fund_state()
        st["off"] = bool(a.off)
        save_fund_state(st)
        print("fund line off. Turn it back on with `fund --on`." if a.off else "fund line on.")
        return 0
    fs = load_funding_status()
    print(fund_line(fs))
    n = fund_numbers(fs)
    if n:
        print(f"  build cost (AI, at API list price): {money(n[0])}   covered by sponsors: {money(n[1])}"
              f"   updated: {fs.get('updated', 'unknown')}")
    for m in (fs or {}).get("value_moments", []):
        print(f"  asks only when: {m.get('when')}")
    print_value_math(fs, load_fund_state().get("last_estimate"))
    print(f"  occasional line: {'off' if load_fund_state().get('off') else 'on'} "
          "(`fund --off` to hide; also silent in CI, when piped, or with GHOSTWRITER_NO_FUND=1)")
    return 0


def print_value_math(fs: dict | None, last: dict | None) -> None:
    ve = (fs or {}).get("value_estimates") or {}
    wph, share = value_assumptions(fs)
    print("")
    print("How the \"hours of drafting you didn't do\" ESTIMATE is worked out (an estimate, not a measurement):")
    print(f"  hours = words in the passing chapter / {wph:,.0f} words per hour x {share:.0%}, rounded down")
    print("  a full draft = the same math on the words in every promoted chapter")
    for b in ve.get("benchmarks", []):
        print(f"  benchmark: {b.get('claim')}")
        print(f"    source: {b.get('source')} {b.get('url', '')}".rstrip())
    for why in ve.get("why_conservative", []):
        print(f"  conservative because: {why}")
    ex = value_estimate(4000, fs)
    print(f"  example: 4,000 words / {wph:,.0f} = {ex['naive_hours']:.1f} h naive x {share:.0%} = "
          f"{ex['claimed_hours']:.1f} h -> \"{hours_phrase(ex['claimed_hours']) or 'not shown'}\"")
    est = value_estimate((last or {}).get("words"), fs)
    if est:
        print(f"  your last: {last.get('label')}, {est['words']:,} words / {wph:,.0f} = {est['naive_hours']:.1f} h naive "
              f"x {share:.0%} = {est['claimed_hours']:.1f} h -> \"{hours_phrase(est['claimed_hours']) or 'not shown'}\"")


# ---------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ghostwriter.py", description=__doc__.split("\n")[0])
    ap.add_argument("--quiet", "-q", action="store_true", help="never print the occasional sponsor line")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("init"); p.add_argument("dir"); p.add_argument("--title"); p.add_argument("--author")
    p.set_defaults(fn=cmd_init)

    p = sp.add_parser("add-source"); p.add_argument("book"); p.add_argument("path")
    p.add_argument("--kind", required=True); p.add_argument("--title"); p.add_argument("--origin")
    p.add_argument("--date"); p.add_argument("--summary"); p.add_argument("--note")
    p.add_argument("--pointer", action="store_true", help="record the path only; do not copy the content")
    p.add_argument("--status", choices=CITE_STATUSES,
                   help="default: confirm-before-print for a link, verified for a file in hand")
    p.add_argument("--how", help="how it was verified: fetched the source, PubMed, Crossref, DOI, book in hand...")
    p.add_argument("--via", help="for a secondhand source: the source that cites it")
    p.set_defaults(fn=cmd_add_source)

    p = sp.add_parser("cite-status"); p.add_argument("book"); p.add_argument("source_id")
    p.add_argument("--status", required=True, choices=CITE_STATUSES); p.add_argument("--how"); p.add_argument("--via")
    p.add_argument("--note"); p.set_defaults(fn=cmd_cite_status)

    p = sp.add_parser("phase"); p.add_argument("action", choices=("status", "advance", "require"))
    p.add_argument("book"); p.add_argument("phase", nargs="?", default="writing", help="for `require`")
    p.add_argument("--to", help="advance to this phase (proposal is optional; going back needs --reason)")
    p.add_argument("--reason", help="why (required to go back a phase)")
    p.add_argument("--override", help="move on with unmet exit criteria; the author's reason is logged")
    p.set_defaults(fn=cmd_phase)

    p = sp.add_parser("hypothesis"); p.add_argument("book"); p.add_argument("--set", help="the new working hypothesis")
    p.add_argument("--reason", help="why the old one is being replaced"); p.set_defaults(fn=cmd_hypothesis)
    p = sp.add_parser("supersede"); p.add_argument("book"); p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_supersede)

    p = sp.add_parser("voice-log"); p.add_argument("book"); p.add_argument("text", nargs="?")
    p.add_argument("--kind", default="quote", help=f"one of {', '.join(VOICE_KINDS)}")
    p.add_argument("--context", help="what prompted it"); p.add_argument("--chapter", help="chapter(s) it belongs to: ch03,ch05")
    p.add_argument("--list", action="store_true"); p.set_defaults(fn=cmd_voice_log)
    p = sp.add_parser("check-author-voice"); p.add_argument("book"); p.add_argument("draft")
    p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_check_author_voice)

    p = sp.add_parser("scaffold"); p.add_argument("book"); p.add_argument("kind", help="borrow, analogy, scorecard, theory, coverage")
    p.add_argument("--name", required=True); p.set_defaults(fn=cmd_scaffold)
    p = sp.add_parser("check-research"); p.add_argument("note"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_check_research)
    p = sp.add_parser("coverage"); p.add_argument("book"); p.add_argument("file", nargs="?")
    p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_coverage)
    p = sp.add_parser("ingest-research"); p.add_argument("book"); p.add_argument("note")
    p.add_argument("--kind", default="article", choices=SOURCE_KINDS); p.set_defaults(fn=cmd_ingest_research)

    p = sp.add_parser("interview-open"); p.add_argument("book"); p.set_defaults(fn=cmd_interview_open)
    p = sp.add_parser("interview-file"); p.add_argument("book"); p.add_argument("question_id")
    p.add_argument("--answer-file", help="file with the answer (default: stdin)"); p.set_defaults(fn=cmd_interview_file)

    p = sp.add_parser("voice-build"); p.add_argument("book"); p.set_defaults(fn=cmd_voice_build)

    for name, fn, needs_book in (("check-provenance", cmd_check_provenance, True),
                                 ("check-ai-tells", cmd_check_ai_tells, False),
                                 ("check-thesis", cmd_check_thesis, False)):
        p = sp.add_parser(name)
        if needs_book:
            p.add_argument("book")
        p.add_argument("draft"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=fn)

    ov = "run a drafting command before the writing phase; the reason is logged in ghostwriter.json"
    p = sp.add_parser("tournament"); p.add_argument("book"); p.add_argument("chapter")
    p.add_argument("--override-phase", metavar="WHY", help=ov); p.set_defaults(fn=cmd_tournament)
    p = sp.add_parser("promote"); p.add_argument("book"); p.add_argument("chapter"); p.add_argument("run")
    p.add_argument("--override-phase", metavar="WHY", help=ov); p.set_defaults(fn=cmd_promote)
    p = sp.add_parser("status"); p.add_argument("book"); p.set_defaults(fn=cmd_status)
    p = sp.add_parser("fund"); g = p.add_mutually_exclusive_group()
    g.add_argument("--off", action="store_true", help="never show the occasional sponsor line again")
    g.add_argument("--on", action="store_true", help="show it again (still capped)")
    p.set_defaults(fn=cmd_fund)
    for p in sp.choices.values():  # --quiet also works after the subcommand
        p.add_argument("--quiet", "-q", action="store_true", default=argparse.SUPPRESS,
                       help="never print the occasional sponsor line")
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
