#!/usr/bin/env python3
"""ghostwriter.py: the deterministic half of Ghost Writer.

The judgment steps (pick a thesis, write a chapter, judge a tournament) are prompts in
prompts/, run by an AI coding agent. This script does everything that should NOT be left
to a model's judgment: scaffolding, the source registry, filing interview answers,
measuring the author's voice, and the gates a chapter must pass before it is promoted.

Standard library only. Python 3.9+.

Commands (run `python3 scripts/ghostwriter.py <command> -h` for flags):
  init                 create a book workspace
  add-source           register a post, note, dataset, article or interview as a cited source
  interview-open       list interview questions that have no answer yet
  interview-file       file an answer to an interview question as a source
  voice-build          measure the author's voice from their own published writing
  check-provenance     every factual claim cites a source or is marked as opinion
  check-ai-tells       flag generic machine-sounding prose
  check-thesis         the chapter advances or tests the thesis and steelmans the other side
  tournament           run all gates on every draft of a chapter and write a scoreboard
  promote              copy a winning draft to chapters/, only if it passes every gate
  status               show where a book is in the pipeline
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "book-template"
AI_TELLS_FILE = ROOT / "data" / "ai-tells.txt"

SOURCE_KINDS = ("post", "note", "dataset", "article", "interview", "book", "talk", "other")
XREF_RX = re.compile(r"\b(chapters?|ch|part|section|stage|step|figure|table)\s*\d+\b", re.I)  # cross-references are not claims
THESIS_ROLES = ("advances", "tests", "complicates")
CITE_RX = re.compile(r"\[(S\d{3,})\]")
OPINION_RX = re.compile(r"\[(opinion|author)\]", re.I)
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


TRAILING_TAGS_RX = re.compile(r"([.!?])((?:\s*\[(?:S\d{3,}|opinion|author)\])+)", re.I)


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
    (book / "ghostwriter.json").write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"created book workspace at {book}")
    print("next: put thesis options in input/thesis/, then follow prompts/01-thesis-options.md")
    return 0


# ---------------------------------------------------------------- sources
def register_source(book: Path, kind: str, title: str, origin: str, when: str,
                    body: str | None, pointer: str | None, note: str = "") -> str:
    idx = load_index(book)
    sid = next_source_id(idx)
    rec = {"id": sid, "kind": kind, "title": title, "origin": origin, "date": when,
           "file": f"sources/{sid}.md"}
    if pointer:
        rec["pointer"] = pointer
    if note:
        rec["note"] = note
    idx["sources"].append(rec)
    save_index(book, idx)
    head = "\n".join(f"{k}: {v}" for k, v in rec.items() if k != "file")
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
    origin = a.origin or (src if src.startswith(("http://", "https://")) else Path(src).name)
    sid = register_source(book, a.kind, a.title or Path(src).name, origin,
                          a.date or date.today().isoformat(), body, pointer, a.note or "")
    print(f"{sid}  {a.kind}  {a.title or src}")
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
                          date.today().isoformat(), body, None)
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
    known = {s["id"] for s in load_index(book)["sources"]}
    _, body = split_front_matter(draft.read_text())
    unsupported, unknown, cited, opinions, claims = [], set(), 0, 0, 0
    for line in prose_lines(body):
        if line.startswith(">"):
            line = line.lstrip("> ")
        for s in sentences(line):
            ids = CITE_RX.findall(s)
            unknown.update(i for i in ids if i not in known)
            bare = XREF_RX.sub("", CITE_RX.sub("", s))
            if "[NEEDS SOURCE" in s.upper():
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
    return {"claims": claims, "cited": cited, "opinion": opinions,
            "unsupported": unsupported, "unknown_ids": sorted(unknown),
            "pass": not unsupported and not unknown}


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


def gate_all(book: Path, draft: Path) -> dict:
    p, t, h = provenance_report(book, draft), ai_tell_report(draft), thesis_report(draft)
    return {"provenance": p, "ai_tells": t, "thesis": h, "pass": p["pass"] and t["pass"] and h["pass"]}


def cmd_tournament(a) -> int:
    book = Path(a.book)
    load_config(book)
    d = book / "drafts" / a.chapter
    runs = sorted(d.glob("run-*.md"))
    if not runs:
        die(f"no drafts in {d} (expected run-1.md, run-2.md, ...)")
    rows = ["| run | words | claims cited/total | unsupported | AI tells (hard/soft per 1k) | thesis | all gates |",
            "|---|---|---|---|---|---|---|"]
    results = {}
    for r in runs:
        g = gate_all(book, r)
        results[r.stem] = g["pass"]
        p, t, h = g["provenance"], g["ai_tells"], g["thesis"]
        rows.append(f"| {r.stem} | {t['words']} | {p['cited'] + p['opinion']}/{p['claims']} | {len(p['unsupported'])} "
                    f"| {len(t['hard'])}/{t['soft_per_1000']} | {'ok' if h['pass'] else 'FAIL'} "
                    f"| {'PASS' if g['pass'] else 'fail'} |")
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
    return 0


def cmd_promote(a) -> int:
    book = Path(a.book)
    load_config(book)
    src = book / "drafts" / a.chapter / f"{a.run}.md"
    if not src.is_file():
        die(f"no such draft: {src}")
    g = gate_all(book, src)
    if not g["pass"]:
        for name in ("provenance", "ai_tells", "thesis"):
            if not g[name]["pass"]:
                print_report(name, g[name], False)
        die("draft fails a gate; not promoted", 1)
    (book / "chapters").mkdir(exist_ok=True)
    dest = book / "chapters" / f"{a.chapter}.md"
    shutil.copyfile(src, dest)
    print(f"promoted {src.name} -> {dest}")
    return 0


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
        ("1 thesis options", any((book / "input" / "thesis").glob("*.md"))),
        ("2 thesis picked", has("thesis.md")),
        ("3 book spine", has("spine.md")),
        ("4 interview", f"{sum(q[1] for q in qs)}/{len(qs)} answered"),
        ("5 sources", f"{len(load_index(book)['sources'])} registered"),
        ("6 voice profile", (book / "voice" / "profile.json").is_file()),
        ("7 chapter drafts", f"{len(drafts)} chapter(s) drafted"),
        ("8 chapters passed gates", f"{len(chapters)} promoted"),
        ("9 revision notes", f"{len(list((book / 'revision-notes').glob('*.md')))} written" if (book / 'revision-notes').is_dir() else "0 written"),
    ]
    print(f"{cfg.get('title')} by {cfg.get('author')}")
    for name, v in stages:
        mark = v if isinstance(v, str) else ("done" if v else "-")
        print(f"  {name:<26} {mark}")
    return 0


# ---------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ghostwriter.py", description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("init"); p.add_argument("dir"); p.add_argument("--title"); p.add_argument("--author")
    p.set_defaults(fn=cmd_init)

    p = sp.add_parser("add-source"); p.add_argument("book"); p.add_argument("path")
    p.add_argument("--kind", required=True); p.add_argument("--title"); p.add_argument("--origin")
    p.add_argument("--date"); p.add_argument("--summary"); p.add_argument("--note")
    p.add_argument("--pointer", action="store_true", help="record the path only; do not copy the content")
    p.set_defaults(fn=cmd_add_source)

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

    p = sp.add_parser("tournament"); p.add_argument("book"); p.add_argument("chapter"); p.set_defaults(fn=cmd_tournament)
    p = sp.add_parser("promote"); p.add_argument("book"); p.add_argument("chapter"); p.add_argument("run")
    p.set_defaults(fn=cmd_promote)
    p = sp.add_parser("status"); p.add_argument("book"); p.set_defaults(fn=cmd_status)
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
