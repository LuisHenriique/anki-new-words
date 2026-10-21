#!/usr/bin/env python3
"""
Import anki_import.csv into Anki AND add audio to the Front of every card. Zero clicks.

What it does:
  1. tests every line with check_csv.py (lines with an ERROR are NOT imported)
  2. makes an mp3 of each Front sentence with Google text-to-speech (gTTS)
  3. sends the mp3 to Anki and writes "sentence [sound:file.mp3]" in the Front field
  4. adds the notes to your deck through AnkiConnect, with the tags "english" and "import-YYYYMMDD"

It only ADDS new notes. Anki's duplicate check stays on.

Requirements: Anki open, AnkiConnect installed, check_csv.py in this folder,
              and for audio:  pip install gTTS   (needs internet)

Usage:
  python import_to_anki.py                  # import + audio
  python import_to_anki.py --no-audio       # import without audio
  python import_to_anki.py --dry-run        # show what would happen, change nothing
  python import_to_anki.py other.csv

Add audio to notes that are already in Anki and have no [sound:] yet
(only notes in your DECK, only notes whose Front has no sound; close the Browser window first):
  python import_to_anki.py --audio-only                       # notes with today's import tag
  python import_to_anki.py --audio-only --search "added:2"    # cards added in the last 2 days
  python import_to_anki.py --audio-only --dry-run             # only count them
"""

import base64
import csv
import datetime
import hashlib
import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ANKI_URL = "http://127.0.0.1:8765"
DECK = "English Vocabulary"  # the deck that receives the new cards
NOTE_TYPE = "Basic"  # your note type name (the one with the fields Front and Back)
BASE_TAGS = ["english"]  # same tag as your other cards
TTS_LANG = "en"
TTS_TLD = "com"  # "com" = American voice, "co.uk" = British voice


def option_value(name):
    """Value after an option like --search "added:2"."""
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
            return sys.argv[i + 1]
    return None


SEARCH = option_value("--search")
ARGS = [a for a in sys.argv[1:] if not a.startswith("--") and a != SEARCH]
DRY_RUN = "--dry-run" in sys.argv
NO_AUDIO = "--no-audio" in sys.argv
AUDIO_ONLY = "--audio-only" in sys.argv
INPUT = Path(ARGS[0] if ARGS else "anki_import.csv")
BATCH_TAG = "import-" + datetime.date.today().strftime("%Y%m%d")

try:
    from check_csv import check_row  # the same tests as check_csv.py
except ImportError:
    sys.exit("check_csv.py must be in the same folder as import_to_anki.py.")


# ---------------------------------------------------------------- Anki
def anki(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(ANKI_URL, payload)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data["result"]


def connect():
    """Check Anki, deck and note type. Return the names of the Front and Back fields."""
    try:
        anki("version")
    except (urllib.error.URLError, ConnectionError, OSError):
        sys.exit(
            "Cannot reach Anki. Open Anki and check that AnkiConnect is installed."
        )
    decks = anki("deckNames")
    if DECK not in decks:
        sys.exit(
            f"Deck '{DECK}' not found. Your decks: {', '.join(decks)}\n"
            "Change DECK at the top of import_to_anki.py."
        )
    models = anki("modelNames")
    if NOTE_TYPE not in models:
        sys.exit(
            f"Note type '{NOTE_TYPE}' not found. Your note types: {', '.join(models)}\n"
            "Change NOTE_TYPE at the top of import_to_anki.py."
        )
    fields = anki("modelFieldNames", modelName=NOTE_TYPE)
    if len(fields) < 2:
        sys.exit(
            f"The note type '{NOTE_TYPE}' needs at least 2 fields, it has: {fields}"
        )
    return fields[0], fields[1]


# ---------------------------------------------------------------- audio
def need_gtts():
    try:
        import gtts  # noqa: F401
    except ImportError:
        sys.exit(
            "Audio needs the gTTS package. Run:  pip install gTTS\n"
            "(or use --no-audio to import without audio)"
        )


def spoken_text(front):
    """The sentence as plain text: no HTML, no old [sound:] tags."""
    text = re.sub(r"\[sound:[^\]]*\]", "", front)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\s+", " ", text).strip()


def audio_name(text):
    """File name in the same style as your old cards: google-xxxxxxxx-xxxxxxxx-...mp3"""
    h = hashlib.sha1(f"{TTS_LANG}-{TTS_TLD}-{text}".encode()).hexdigest()
    return "google-" + "-".join(h[i : i + 8] for i in range(0, 40, 8)) + ".mp3"


def make_mp3(text):
    from gtts import gTTS

    last = None
    for attempt in range(3):
        buf = io.BytesIO()
        try:
            gTTS(text=text, lang=TTS_LANG, tld=TTS_TLD).write_to_fp(buf)
            return buf.getvalue()
        except Exception as e:  # noqa: BLE001  (network, rate limit...)
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Google text-to-speech failed: {last}")


def attach_audio(front):
    """Make the mp3, send it to Anki, return the Front with [sound:...] at the end."""
    text = spoken_text(front)
    name = audio_name(text)
    anki(
        "storeMediaFile", filename=name, data=base64.b64encode(make_mp3(text)).decode()
    )
    return f"{text_with_html(front)} [sound:{name}]"


def text_with_html(front):
    """Keep the bold word, remove only old sound tags."""
    return re.sub(r"\s*\[sound:[^\]]*\]", "", front).strip()


def safe_audio(front, state):
    """Return (new_front, error). After 3 failures in a row, stop trying (Google is not answering)."""
    if state["fails"] >= 3:
        return None, "skipped"
    try:
        new = attach_audio(front)
        state["fails"] = 0
        time.sleep(0.2)  # be kind to the free Google service
        return new, None
    except Exception as e:  # noqa: BLE001
        state["fails"] += 1
        return None, str(e)


def audio_summary(state, failed):
    if failed:
        print(
            f"\nNo audio for {len(failed)} card(s): {', '.join(failed[:10])}"
            f"{'...' if len(failed) > 10 else ''}"
        )
        if state["fails"] >= 3:
            print("Google text-to-speech stopped answering. Check your internet.")
        print("Try again later with:  python import_to_anki.py --audio-only")


# ---------------------------------------------------------------- modes
def run_audio_only(front_field):
    need_gtts()
    query = f'deck:"{DECK}" ({SEARCH or "tag:" + BATCH_TAG})'
    ids = anki("findNotes", query=query)
    infos = anki("notesInfo", notes=ids) if ids else []
    todo = [i for i in infos if "[sound:" not in i["fields"][front_field]["value"]]
    print(f"Search: {query}")
    print(f"{len(infos)} note(s) found, {len(todo)} without audio.")
    if DRY_RUN or not todo:
        return
    state, failed, done = {"fails": 0}, [], 0
    for n, info in enumerate(todo, start=1):
        value = info["fields"][front_field]["value"]
        new, err = safe_audio(value, state)
        print(f"  audio {n}/{len(todo)}", end="\r", flush=True)
        if err:
            failed.append(spoken_text(value)[:30])
            continue
        anki(
            "updateNoteFields",
            note={"id": info["noteId"], "fields": {front_field: new}},
        )
        done += 1
    print(f"\nDone! Audio added to {done} note(s).")
    audio_summary(state, failed)


def run_import(front_field, back_field):
    if not INPUT.exists():
        sys.exit(f"File not found: {INPUT}")
    with INPUT.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))

    good, refused = [], []
    for n, row in enumerate(rows, start=1):
        target, problems = check_row(row)
        errors = [msg for level, msg in problems if level == "ERROR"]
        if errors:
            refused.append((n, target, errors[0]))
        else:
            good.append((n, target, row))

    for n, target, msg in refused:
        print(f"Not imported | line {n} | {target} | {msg}")
    print(f"{len(good)} card(s) ready, {len(refused)} refused because of errors.")

    if DRY_RUN:
        audio = "without audio" if NO_AUDIO else "with audio (Google voice)"
        print(
            f"--dry-run: nothing was added. It would add {len(good)} note(s) {audio} to "
            f"'{DECK}' ({NOTE_TYPE}: {front_field}/{back_field}) with tags {BASE_TAGS + [BATCH_TAG]}."
        )
        return
    if not good:
        sys.exit("Nothing to import.")

    state, failed = {"fails": 0}, []
    if not NO_AUDIO:
        print("Making the audio...")
        for i, (n, target, row) in enumerate(good, start=1):
            new, err = safe_audio(row[0], state)
            print(f"  audio {i}/{len(good)}", end="\r", flush=True)
            if err:
                failed.append(target)
            else:
                row[0] = new
        print()

    notes = [
        {
            "deckName": DECK,
            "modelName": NOTE_TYPE,
            "fields": {front_field: row[0], back_field: row[1]},
            "tags": BASE_TAGS + [BATCH_TAG],
            "options": {"allowDuplicate": False},
        }
        for _, _, row in good
    ]
    try:
        results = anki("addNotes", notes=notes)
    except RuntimeError as e:
        sys.exit(f"Anki refused the import: {e}")

    added = sum(1 for r in results if r)
    for (n, target, _), r in zip(good, results):
        if not r:
            print(f"Not added (Anki says duplicate or invalid) | line {n} | {target}")
    print(f"\nDone! {added} note(s) added to '{DECK}' (tag: {BATCH_TAG}).")
    if not NO_AUDIO:
        print(f"Audio added to {len(good) - len(failed)} of {len(good)} card(s).")
        audio_summary(state, failed)


def main():
    front_field, back_field = connect()
    if not NO_AUDIO:
        need_gtts()
    if AUDIO_ONLY:
        run_audio_only(front_field)
    else:
        run_import(front_field, back_field)


if __name__ == "__main__":
    main()
