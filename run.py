#!/usr/bin/env python3
"""
Run the whole vocabulary pipeline with one command:

    python run.py

It does, in order:
  1. anki_words.py   words.txt        -> anki_import.csv   (cards, duplicates skipped)
  2. check_csv.py    --fix --anki                          (safe fixes + tests)
  3. import_to_anki.py anki_import_fixed.csv               (notes + audio + tags)
  4. cleans words.txt: words that reached Anki are removed, failed lines are kept

Usage:
  python run.py                     # uses words.txt
  python run.py my_words.txt        # uses another file
  python run.py --no-audio          # import without audio
  python run.py --dry-run           # make and test the CSV, import nothing, keep words.txt
  python run.py --keep              # do not clean words.txt
  python run.py --stop-on-error     # stop after the CSV step if it has ERRORs

Requirements: Anki open with AnkiConnect, opencode working, and (for audio) gTTS.
It uses no third-party modules itself.
"""

import importlib.util
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANKI_URL = "http://127.0.0.1:8765"


# ---------------------------------------------------------------- helpers
def anki_version():
    payload = json.dumps({"action": "version", "version": 6}).encode()
    req = urllib.request.Request(ANKI_URL, payload)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)["result"]


def preflight(no_audio):
    missing = [n for n in ("anki_words.py", "check_csv.py", "import_to_anki.py") if not (HERE / n).exists()]
    if missing:
        sys.exit(f"Missing file(s) in {HERE}: {', '.join(missing)}")
    try:
        anki_version()
    except (urllib.error.URLError, ConnectionError, OSError):
        sys.exit("Cannot reach Anki. Open Anki and check that AnkiConnect is installed.")
    if not no_audio and importlib.util.find_spec("gtts") is None:
        sys.exit(
            "gTTS is missing, so the audio cannot be made. Install it with:\n"
            "  python -m pip install gTTS\n"
            "or, if pip is not available:\n"
            "  uv pip install --target \"$(python -c 'import site; print(site.getusersitepackages())')\" gTTS\n"
            "Use --no-audio only if you really want cards without sound."
        )


def run_step(title, args):
    """Run one script, print its output live and return (exit code, output)."""
    print(f"\n=== {title} ===", flush=True)
    proc = subprocess.Popen(
        [sys.executable, *args],
        cwd=HERE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines = []
    for line in proc.stdout:
        print(line, end="", flush=True)
        lines.append(line)
    return proc.wait(), "".join(lines)


def parse_list(pattern, text):
    m = re.search(pattern, text)
    if not m:
        return []
    return [w.strip() for w in m.group(1).split(",") if w.strip()]


def parse_fixes(text):
    m = re.search(r"Spelling fixed: (.+)", text)
    if not m:
        return {}
    return {
        a.lower(): b
        for a, b in re.findall(r"(\S+) -> (\S+)", m.group(1))
    }


def prune_words(words_path, fixes):
    """Remove the lines whose word is already in Anki. Keep everything else.
    Returns (removed_words, kept_words). On an Anki error returns (None, None)
    so the caller knows the file was not touched."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    saved_argv = sys.argv
    sys.argv = [saved_argv[0]]
    try:
        import anki_words  # the same Anki search as the generator
    finally:
        sys.argv = saved_argv

    lines = words_path.read_text(encoding="utf-8").splitlines()
    kept, removed = [], []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = re.search(r"\*(.+?)\*", line)
        word = (m.group(1) if m else line).replace("*", "").strip()
        fixed = fixes.get(word.lower(), word)
        try:
            found = anki_words.in_anki(fixed)
        except Exception:  # noqa: BLE001 - Anki went away: never risk the file
            print("Warning: could not check Anki; words.txt left untouched.")
            return None, None
        if found:
            removed.append(fixed)
        else:
            kept.append(raw)

    content = "\n".join(kept)
    words_path.write_text(content + ("\n" if kept else ""), encoding="utf-8")
    return removed, [ln.strip() for ln in kept]


# ---------------------------------------------------------------- main
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_audio = "--no-audio" in sys.argv
    dry_run = "--dry-run" in sys.argv
    keep = "--keep" in sys.argv or dry_run
    stop_on_error = "--stop-on-error" in sys.argv

    words = Path(args[0]) if args else HERE / "words.txt"
    if not words.is_absolute():
        words = HERE / words
    if not words.exists():
        sys.exit(f"File not found: {words}")
    if not words.read_text(encoding="utf-8").strip():
        sys.exit(f"{words.name} is empty. Put the new words there first.")

    preflight(no_audio)

    # 1. cards
    code, out = run_step("1/4 Making the cards", ["anki_words.py", str(words), "--no-dict"])
    if "Nothing new to add" in out:
        print("\nNothing new to add: every word is already in Anki. words.txt was not changed.")
        return 0
    if code != 0:
        print("\nThe card generation failed. Nothing was imported and words.txt was not changed.")
        return code
    fixes = parse_fixes(out)
    skipped = parse_list(r"Already in Anki \(skipped\): (.+)", out)

    # 2. check + safe fixes
    code_check, out_check = run_step(
        "2/4 Checking and fixing the CSV", ["check_csv.py", "--fix", "--anki"]
    )
    m = re.search(r"(\d+) error\(s\)", out_check)
    errors = int(m.group(1)) if m else 0
    if stop_on_error and errors:
        print("\n--stop-on-error: the CSV has ERRORs. Nothing was imported.")
        return 1

    # 3. import with audio
    import_args = ["import_to_anki.py", "anki_import_fixed.csv"]
    if no_audio:
        import_args.append("--no-audio")
    if dry_run:
        import_args.append("--dry-run")
    code_import, out_import = run_step("3/4 Importing into Anki", import_args)

    imported_ok = "Done!" in out_import or "dry-run" in out_import
    refused = [
        (int(n), w, err)
        for n, w, err in re.findall(
            r"Not imported \| line (\d+) \| (.+?) \| (.+)", out_import
        )
    ]

    # 4. clean words.txt
    removed = []
    kept_words = []
    if dry_run:
        print("\n=== 4/4 Cleaning words.txt ===")
        print("Dry run: words.txt was not changed.")
    elif not code_import == 0 or not imported_ok:
        print("\n=== 4/4 Cleaning words.txt ===")
        print("The import did not finish, so words.txt was not changed.")
    elif keep:
        print("\n=== 4/4 Cleaning words.txt ===")
        print("--keep: words.txt was not changed.")
    else:
        print("\n=== 4/4 Cleaning words.txt ===")
        removed, kept_words = prune_words(words, fixes)
        if removed is None:
            print("Could not clean words.txt (see the warning above).")
        elif not kept_words:
            print(f"Removed {len(removed)} word(s); words.txt is now empty.")
        else:
            print(f"Removed {len(removed)} word(s). Kept {len(kept_words)}: {', '.join(kept_words)}")

    # final summary
    m = re.search(r"Done! (\d+) cards saved", out)
    cards = int(m.group(1)) if m else 0
    m = re.search(r"Done! (\d+) note\(s\) added to '([^']+)' \(tag: ([^)]+)\)", out_import)
    added, deck, tag = (int(m.group(1)), m.group(2), m.group(3)) if m else (0, "", "")
    m = re.search(r"Audio added to (\d+) of (\d+)", out_import)
    audio_done, audio_total = (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    print("\n================ SUMMARY ================")
    if fixes:
        print("Spelling fixed:", ", ".join(f"{a} -> {b}" for a, b in fixes.items()))
    if skipped:
        print("Already in Anki (skipped):", ", ".join(skipped))
    if refused:
        print("Refused lines:")
        for n, w, err in refused:
            print(f"  line {n}: {w} - {err}")
    print(f"Cards written: {cards}")
    if dry_run:
        print("Import: dry run, nothing added")
    else:
        print(f"Import: {added} note(s) into '{deck}' (tag: {tag})")
        if audio_total:
            print(f"Audio: {audio_done} of {audio_total} card(s)")
    if removed:
        print(f"Removed from words.txt: {len(removed)}")
    if kept_words:
        print(f"Kept in words.txt (not imported): {', '.join(kept_words)}")
    print("=========================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
