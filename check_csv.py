#!/usr/bin/env python3
"""
Test every line of anki_import.csv before you import it into Anki.

Usage:
  python check_csv.py                    # checks anki_import.csv
  python check_csv.py other.csv
  python check_csv.py --fix              # fixes safe problems, saves anki_import_fixed.csv
  python check_csv.py --anki             # also checks the words are NOT already in your two decks
                                         # (Anki must be open; decks come from CHECK_DECKS in anki_words.py)

Levels:
  ERROR   = the card is wrong or Anki would show something broken. Fix it.
  WARNING = the card works, but look at it.
"""

import csv
import re
import sys
from pathlib import Path

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
FIX = "--fix" in sys.argv
CHECK_ANKI = "--anki" in sys.argv
INPUT = Path(ARGS[0] if ARGS else "anki_import.csv")
FIXED = INPUT.with_name(INPUT.stem + "_fixed.csv")

POS = ("noun", "verb", "adjective", "adverb")
MEANING_RE = re.compile(r"^Meaning \((.+?), (\w+)\): (.*)$")
IMPERATIVE_RE = re.compile(r"^Meaning \(imperative form of the verb\): (\S.*)!$")
JUNK_RE = re.compile(r"\b(undefined|null|None|NaN)\b|```|\[\{|\}\]")


# ---------------------------------------------------------------- safe fixes
def auto_fix(row):
    """Only fixes that cannot change the meaning of a card."""
    front, back = row
    for _ in range(3):  # <b><b>word</b></b> -> <b>word</b>
        front = front.replace("<b><b>", "<b>").replace("</b></b>", "</b>")
    front = front.replace("*", "")
    back = back.replace("*", "")
    parts = [re.sub(r"\s+", " ", p).strip() for p in back.split("<br>")]
    front = re.sub(r"\s+", " ", front).strip()
    if (
        parts and parts[0].lower().count("(informal)") > 1
    ):  # label twice -> once, at the start
        m = MEANING_RE.match(parts[0])
        if m:
            text = re.sub(r"\s*\(informal\)\s*", " ", m.group(3)).strip()
            parts[0] = f"Meaning ({m.group(1)}, {m.group(2)}): (informal) {text}"
    return [front, "<br>".join(parts)]


# ---------------------------------------------------------------- tests
def check_row(row):
    """Return (target_word, [(level, message), ...])."""
    problems = []
    add = lambda level, msg: problems.append((level, msg))

    if len(row) != 2:
        add("ERROR", f"has {len(row)} fields, it must have exactly 2 (Front;Back)")
        return "?", problems
    front, back = row

    # ---- back: first line decides the target word
    parts = back.split("<br>")
    m = MEANING_RE.match(parts[0])
    target = "?"
    if not m:
        add(
            "ERROR",
            "first line of the back must be: Meaning (word, part of speech): ...",
        )
        pos, meaning = "", ""
    else:
        target, pos, meaning = m.group(1), m.group(2).lower(), m.group(3)
        if pos not in POS:
            add(
                "ERROR",
                f"part of speech '{pos}' must be noun, verb, adjective or adverb",
            )
        body = re.sub(r"\((informal|unverified)\)", "", meaning, flags=re.I).strip()
        if len(body) < 3:
            add("ERROR", "the meaning is empty")
        if ";" in meaning:
            add(
                "WARNING",
                "the meaning contains ';': give only one meaning, not a second definition",
            )
        if meaning.lower().count("(informal)") > 1:
            add("ERROR", "the (informal) label appears more than once")
        if re.search(r"\(informal\)", meaning, re.I) and not re.match(
            r"^(\(unverified\) )?\(informal\)", meaning, re.I
        ):
            add("WARNING", "(informal) is not at the start of the meaning")
        if "(unverified)" in meaning.lower():
            add(
                "WARNING", "marked (unverified): check the meaning and the IPA yourself"
            )

    # ---- back: other lines
    rest = parts[1:]
    imperative = [p for p in rest if p.startswith("Meaning (imperative")]
    phonetic = [p for p in rest if p.startswith("Phonetic:")]
    trad = [p for p in rest if p.startswith("Tradução:")]
    other = [p for p in rest if p not in imperative + phonetic + trad]
    if pos == "verb":
        if not imperative:
            add(
                "ERROR",
                "verb without the 'Meaning (imperative form of the verb): ...!' line",
            )
        elif not IMPERATIVE_RE.match(imperative[0]):
            add(
                "ERROR",
                "imperative line must look like: Meaning (imperative form of the verb): cling!",
            )
    elif imperative:
        add("ERROR", "only verbs should have the imperative line")
    if not phonetic:
        add("WARNING", "no Phonetic line")
    elif not re.match(r"^Phonetic: /[^/]+/$", phonetic[0]):
        add("ERROR", "Phonetic must be IPA between slashes, like: Phonetic: /klɪŋ/")
    if not trad:
        add("ERROR", "no Tradução line")
    elif len(trad[0].replace("Tradução:", "").strip()) < 2:
        add("ERROR", "Tradução is empty")
    for p in other:
        add("ERROR", f"unexpected line in the back: '{p[:40]}'")
    order = [p.split(":")[0].split("(")[0].strip() for p in parts]
    if "Tradução" in order and order[-1] != "Tradução":
        add("WARNING", "Tradução should be the last line")

    # ---- front
    if "<b><b>" in front or "</b></b>" in front:
        add("ERROR", "double bold <b><b>...</b></b> in the sentence")
    elif front.count("<b>") != front.count("</b>"):
        add("ERROR", "bold tags <b> and </b> do not match")
    else:
        bolds = re.findall(r"<b>(.*?)</b>", front)
        if not bolds:
            add("ERROR", "the target word is not in bold in the sentence")
        else:
            if len(bolds) > 1:
                add("WARNING", "more than one bold part in the sentence")
            if target != "?" and bolds[0].strip().lower() != target.lower():
                add(
                    "WARNING",
                    f"bold word '{bolds[0]}' is different from the card word '{target}'",
                )
    plain = re.sub(r"<[^>]+>", "", front).strip()
    n_words = len(plain.split())
    if n_words < 4:
        add("WARNING", f"very short sentence ({n_words} words)")
    elif n_words > 25:
        add("WARNING", f"very long sentence ({n_words} words)")
    if plain and not re.search(r"[.!?\"”']$", plain):
        add("WARNING", "the sentence does not end with . ! or ?")
    if "<" in plain or ">" in plain:
        add("ERROR", "strange HTML in the sentence")

    # ---- whole row
    if "*" in front or "*" in back:
        add("ERROR", "stray * (markdown) in the card")
    if JUNK_RE.search(front + " " + back):
        add("ERROR", "junk text found (null, None, undefined, code marks...)")
    return target, problems


def main():
    if not INPUT.exists():
        sys.exit(f"File not found: {INPUT}")
    with INPUT.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    if not rows:
        sys.exit("The CSV is empty.")

    if FIX:
        before = rows
        rows = [auto_fix(r) if len(r) == 2 else r for r in rows]
        changed = sum(1 for a, b in zip(before, rows) if a != b)
        with FIXED.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f, delimiter=";").writerows(rows)
        print(f"--fix: {changed} line(s) fixed. Saved as {FIXED}\n")

    in_anki = None
    if CHECK_ANKI:
        try:
            sys.argv = [sys.argv[0]]  # anki_words reads sys.argv when imported
            from anki_words import in_anki  # same two-deck search as the main script

            in_anki("test")
        except Exception as e:  # noqa: BLE001
            sys.exit(
                f"--anki needs Anki open with AnkiConnect, and anki_words.py in this folder ({e})"
            )

    seen, results = {}, []
    for n, row in enumerate(rows, start=1):
        target, problems = check_row(row)
        key = target.lower()
        if target != "?":
            if key in seen:
                problems.append(
                    ("ERROR", f"duplicate: '{target}' is also on line {seen[key]}")
                )
            else:
                seen[key] = n
            if in_anki and in_anki(target):
                problems.append(("ERROR", "this word is already in your Anki decks"))
        results.append((n, target, problems))

    errors = warnings = 0
    for n, target, problems in results:
        for level, msg in problems:
            print(f"Line {n:>3} | {target:<18} | {level:<7} | {msg}")
            errors += level == "ERROR"
            warnings += level == "WARNING"
    bad_lines = sum(1 for _, _, p in results if any(l == "ERROR" for l, _ in p))
    print(
        f"\n{len(rows)} cards checked: {errors} error(s) on {bad_lines} line(s), {warnings} warning(s)."
    )
    if errors == 0:
        print("No errors. You can import it into Anki.")
    elif not FIX:
        print(
            "Tip: python check_csv.py --fix  fixes the safe ones (double bold, double (informal), stray *)."
        )
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
