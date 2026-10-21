#!/usr/bin/env python3
"""
words.txt
  -> look each word up in an English dictionary (code, no AI tokens)
       1st: dictionaryapi.dev   2nd (backup): Wiktionary
       answers are saved in dict_cache.json, so a stopped run does not start from zero
  -> words not found: the AI fixes the spelling, then we look them up again
  -> skip words already in Anki (checked with the corrected spelling)
  -> the AI only chooses the right meaning, writes the sentence and translates
  -> anki_import.csv

Words that no dictionary confirms are listed as "not verified" and get NO card,
unless you run with --allow-unverified.

Requirements:
  - Anki is open, with the AnkiConnect add-on installed (code 2055492159)
  - opencode is installed and works in your terminal
  - internet (dictionary sources)
Usage:
  python anki_words.py                       # uses words.txt
  python anki_words.py my_words.txt
  python anki_words.py --allow-unverified    # also make cards for unverified words
  python anki_words.py --no-dict             # skip dictionaries: the AI writes everything
To reset the dictionary memory, delete dict_cache.json.
"""

import csv
import difflib
import html
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ANKI_URL = "http://127.0.0.1:8765"
# Only these decks are checked for duplicates (subdecks are included automatically).
# Use the exact deck names from Anki. Empty list [] = check all decks.
CHECK_DECKS = ["English Vocabulary", "B2 First"]
DICT_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
WIKI_REST = "https://en.wiktionary.org/api/rest_v1/page/definition/"
WIKI_API = "https://en.wiktionary.org/w/api.php"
# dictionaryapi.dev sits behind Cloudflare, which blocks Python's default User-Agent
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
WIKI_UA = (
    "AnkiWordsScript/1.0 (personal vocabulary tool)"  # Wikimedia asks for a clear name
)
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
ALLOW_UNVERIFIED = "--allow-unverified" in sys.argv
NO_DICT = "--no-dict" in sys.argv  # skip dictionaries: the AI writes everything
INPUT = Path(ARGS[0] if ARGS else "words.txt")
OUTPUT = Path("anki_import.csv")
CACHE_FILE = Path(__file__).with_name("dict_cache.json")
BATCH_SIZE = 30  # words sent to the AI at once
POS_WANTED = {"noun", "verb", "adjective", "adverb"}

SPELL_RULES = """You fix English spelling for a vocabulary list.
Each item has a "word" (a word or short phrase) and an optional "context".
These items were NOT found in a dictionary, so they may have a typo.
For each item return {"word": <as given>, "corrected": <fixed spelling>}.
- Fix only clear spelling mistakes (example: "acquaintence" -> "acquaintance").
- Keep the same word form. Do not change tense, plural, or replace it with another word.
- If it is not a typo, or you are not sure what the word is, use "" for "corrected".
Reply with ONLY a JSON array, no other text."""

CARD_RULES = """You help a Brazilian learner of English make Anki cards.
For EACH item below return one JSON object with these keys:
  "word": the word exactly as given
  "sense": the "i" number of the dictionary sense that best fits the "context"
           (use the most common sense if there is no context).
           If the item has no senses (empty list), use null.
  "informal": true only if the chosen meaning is informal or slang, otherwise false
  "sentence": a natural B2-level English sentence that uses the word exactly as given
              and shows the chosen sense. Plain text: no HTML, no bold, no asterisks.
              For a phrase, keep every word of the phrase, in the same order and the same form.
  "translation": Brazilian Portuguese translation(s) of the chosen sense, separated by commas.
                 The Portuguese must be clear, natural and coherent, with correct grammar,
                 spelling and accents (example: "agarrar-se, apegar-se, grudar").
                 Use the right form for the part of speech: verbs in the infinitive
                 ("agarrar-se"), nouns in the singular, adjectives in the masculine singular.
                 The translation must match the meaning used in the sentence, not another meaning.
                 Give 1 to 3 options, from the most common to the least common. No explanations.
Only when "senses" is empty, ALSO fill these keys yourself:
  "pos": "noun", "verb", "adjective" or "adverb"
  "meaning": a short, simple English definition
             For a verb, write it in the base form.
  "phonetic": IPA between slashes, example "/klɪŋ/"
  "base": the dictionary form of the word, example "entreat" for "entreated"
Never invent anything else. Reply with ONLY a JSON array, no other text."""


# ---------------------------------------------------------------- Anki
def anki(action, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(ANKI_URL, payload)
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.load(r)
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data["result"]


def in_anki(word):
    clean = re.sub(r'["*:\\]', " ", word).strip()
    query = f"w:{clean}" if " " not in clean else f'"{clean}"'
    if CHECK_DECKS:
        decks = " or ".join(f'deck:"{d}"' for d in CHECK_DECKS)
        query = f"({decks}) {query}"
    return len(anki("findNotes", query=query)) > 0


# ---------------------------------------------------------------- input
def parse_lines(path):
    """Each line is a word, or a phrase with the new word between *stars*."""
    items = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.search(r"\*(.+?)\*", line)
        if m:
            word, context = m.group(1), line
        else:
            word, context = line, ""
        # remove stray stars (example: "backyard*" with no closing star)
        word = word.replace("*", "").strip()
        context = context.replace("*", "").strip()
        if word:
            items.append({"word": word, "context": context, "dict": None})
    return items


def dedupe(items):
    seen, out = set(), []
    for it in items:
        key = it["word"].lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


# ---------------------------------------------------------------- dictionary
class SourceDown(Exception):
    """One dictionary source is not answering."""


class AllDictsDown(Exception):
    """No dictionary source is answering."""


def load_cache():
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


CACHE = load_cache()
DOWN = set()  # sources that stopped answering during this run


def save_cache():
    try:
        CACHE_FILE.write_text(json.dumps(CACHE, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # the cache is only a speed-up


def fetch_json(url, user_agent, tries=3):
    """Return parsed JSON, None if the page does not exist (404), or raise SourceDown."""
    err = "unknown error"
    for attempt in range(tries):
        req = urllib.request.Request(
            url, headers={"User-Agent": user_agent, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:  # must come before URLError
            if e.code == 404:
                return None
            err = f"HTTP {e.code}"
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            OSError,
        ) as e:
            err = str(e)
        time.sleep(1.5 * (attempt + 1))  # wait a little longer each time
    raise SourceDown(err)


def clean_html(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def keep_wanted(senses):
    preferred = [s for s in senses if s["pos"] in POS_WANTED]
    return (preferred or senses)[:6]


def from_dictionaryapi(term):
    entries = fetch_json(DICT_URL + urllib.parse.quote(term.lower()), BROWSER_UA)
    if not isinstance(entries, list) or not entries:
        return None
    phonetic = ""
    for e in entries:
        candidates = [e.get("phonetic")] + [
            p.get("text") for p in e.get("phonetics", [])
        ]
        phonetic = next((c for c in candidates if c), "")
        if phonetic:
            break
    senses = []
    for e in entries:
        for m in e.get("meanings", []):
            for d in m.get("definitions", [])[:2]:
                senses.append(
                    {
                        "pos": m.get("partOfSpeech", "").lower(),
                        "definition": d["definition"],
                    }
                )
    senses = keep_wanted(senses)
    if not senses:
        return None
    return {
        "headword": entries[0].get("word", term),
        "phonetic": phonetic,
        "senses": senses,
    }


def wiktionary_ipa(term):
    """Best effort: read the first English IPA from the page source. Empty text if not found."""
    url = (
        f"{WIKI_API}?action=parse&prop=wikitext&format=json&redirects=1&page="
        + urllib.parse.quote(term.lower())
    )
    try:
        data = fetch_json(url, WIKI_UA, tries=2)
    except SourceDown:
        return ""
    text = ((data or {}).get("parse", {}).get("wikitext", {}) or {}).get("*", "")
    m = re.search(r"==English==(.*?)(?:\n==[^=]|\Z)", text, re.S)
    section = m.group(1) if m else text
    m = re.search(r"\{\{IPA\|en\|(/[^|}]+/)", section)
    return m.group(1) if m else ""


def from_wiktionary(term):
    url = WIKI_REST + urllib.parse.quote(term.lower().replace(" ", "_"))
    data = fetch_json(url, WIKI_UA)
    if not isinstance(data, dict):
        return None
    senses = []
    for block in data.get("en", []):  # "en" = the English section only
        pos = block.get("partOfSpeech", "").lower()
        for d in block.get("definitions", [])[:2]:
            text = clean_html(d.get("definition", ""))
            if text:
                senses.append({"pos": pos, "definition": text})
    senses = keep_wanted(senses)
    if not senses:
        return None
    return {
        "headword": term.lower(),
        "phonetic": wiktionary_ipa(term),
        "senses": senses,
    }


SOURCES = [("dictionaryapi.dev", from_dictionaryapi), ("Wiktionary", from_wiktionary)]


def dict_lookup(term):
    """Return {headword, phonetic, senses} or None. Uses the cache and the backup source."""
    key = term.lower()
    if key in CACHE:
        return CACHE[key]
    down = []
    for name, fetch in SOURCES:
        if name in DOWN:
            down.append(name)
            continue
        try:
            found = fetch(term)
        except SourceDown as err:
            DOWN.add(name)
            down.append(name)
            print(f"Warning: {name} is not answering ({err}).")
            continue
        if found:
            CACHE[key] = found
            save_cache()
            return found
    if len(down) == len(SOURCES):
        raise AllDictsDown()
    if not down:  # every source answered "not found": remember it
        CACHE[key] = None
        save_cache()
    return None


INFLECTION = re.compile(
    r"^(simple past|past tense|past participle|present participle|plural|third-person|"
    r"inflection|gerund|comparative|superlative)\b[^.]{0,80}\bof\b",
    re.I,
)


def only_inflections(entry):
    """True if every meaning only says 'past tense of X', 'plural of X', ..."""
    return all(INFLECTION.search(s["definition"]) for s in entry["senses"])


def base_forms(word):
    """Simple guesses for the dictionary form: entreated -> entreat, leapfrogs -> leapfrog."""
    w = word.lower()
    out = []

    def add(x):
        if len(x) > 2 and x != w and x not in out:
            out.append(x)

    if w.endswith("ies"):
        add(w[:-3] + "y")
    if w.endswith("ied"):
        add(w[:-3] + "y")
    if w.endswith("es"):
        add(w[:-2])
    if w.endswith("s"):
        add(w[:-1])
    if w.endswith("ed"):
        add(w[:-2])
        add(w[:-1])
    if w.endswith("ing"):
        add(w[:-3])
        add(w[:-3] + "e")
    for suf in ("ed", "ing"):  # doubled consonant: stopped -> stop
        stem = w[: -len(suf)]
        if w.endswith(suf) and len(stem) > 2 and stem[-1] == stem[-2]:
            add(stem[:-1])
    return out


def lookup_with_forms(term):
    found = dict_lookup(term)
    if found and not only_inflections(found):
        return found
    if " " not in term:
        for form in base_forms(term):
            alt = dict_lookup(form)
            if alt and not only_inflections(alt):
                return alt
    return found


# ---------------------------------------------------------------- AI
def ask_ai(prompt):
    for _ in range(2):  # one retry
        res = subprocess.run(
            ["opencode", "run", prompt], capture_output=True, text=True
        )
        out = res.stdout
        start, end = out.find("["), out.rfind("]")
        if start != -1 and end > start:
            try:
                return json.loads(out[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise RuntimeError("The AI did not return valid JSON.")


def fix_spelling(items):
    """For words the dictionary did not find: ask the AI for a spelling fix, then check again."""
    missing = (
        items
        if NO_DICT
        else [it for it in items if it["dict"] is None and not it.get("offline")]
    )
    if not missing:
        return []
    if NO_DICT:
        print("Checking spelling with the AI...")
    else:
        print(
            f"{len(missing)} word(s) not found in the dictionary. Checking spelling..."
        )
    payload = [{"word": it["word"], "context": it["context"]} for it in missing]
    try:
        answers = ask_ai(
            SPELL_RULES + "\n\nItems:\n" + json.dumps(payload, ensure_ascii=False)
        )
    except RuntimeError:
        print("Warning: spelling check failed. Those words will stay unverified.")
        return []

    fixes = {
        str(a.get("word", "")).lower(): str(a.get("corrected", "")).strip()
        for a in answers
    }
    corrections = []
    for it in missing:
        new = fixes.get(it["word"].lower(), "")
        if not new or new.lower() == it["word"].lower():
            continue
        # safety: the "correction" must look very similar to the original word
        if difflib.SequenceMatcher(None, it["word"].lower(), new.lower()).ratio() < 0.7:
            continue
        found = None
        if not NO_DICT:
            try:
                found = lookup_with_forms(new)
            except AllDictsDown:
                break  # dictionaries went down: keep the remaining words as they are
            if not found:
                continue
        corrections.append((it["word"], new))
        if it["context"]:
            it["context"] = re.sub(
                re.escape(it["word"]), new, it["context"], flags=re.I
            )
        it["word"], it["dict"] = new, found
    return corrections


STRICT_NOTE = (
    "\n\nYour previous sentence did NOT contain the word. Now each sentence MUST contain "
    'the "word" EXACTLY as given: same letters, same tense, same form. Do not change '
    'it (for example do not change "bulked up" into "bulking up").'
)


def generate_cards(items, strict=False):
    cards = {}
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i : i + BATCH_SIZE]
        payload = []
        for it in batch:
            d = it["dict"]
            senses = (
                [
                    {"i": n, "pos": s["pos"], "definition": s["definition"]}
                    for n, s in enumerate(d["senses"])
                ]
                if d
                else []
            )
            payload.append(
                {"word": it["word"], "context": it["context"], "senses": senses}
            )
        print(f"Asking the AI about {len(batch)} words...")
        answers = ask_ai(
            CARD_RULES
            + (STRICT_NOTE if strict else "")
            + "\n\nItems:\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        for a in answers:
            cards[str(a.get("word", "")).lower()] = a
    return cards


def find_match(word, sentence):
    """Find the word or phrase in the sentence.
    Return (pattern, exact): pattern is a regex for the text found; exact is False when the AI
    changed the form (example: 'bulked up' -> 'bulking up'). Return (None, False) if not found.
    """
    if re.search(re.escape(word), sentence, re.I):
        return re.escape(word), True
    n = len(word.split())
    tokens = re.findall(r"[A-Za-z'’-]+", sentence)
    best, best_ratio = None, 0.0
    for i in range(len(tokens) - n + 1):  # compare with every group of n words
        cand = tokens[i : i + n]
        ratio = difflib.SequenceMatcher(
            None, word.lower(), " ".join(cand).lower()
        ).ratio()
        if ratio > best_ratio:
            best, best_ratio = cand, ratio
    if best and best_ratio >= 0.7:
        return r"\b" + r"[^A-Za-z'’-]+".join(re.escape(x) for x in best) + r"\b", False
    return None, False


def bold_word(word, sentence):
    """Return the sentence with the word in <b>...</b>, or None if the word is not in it."""
    pattern, exact = find_match(word, sentence)
    if pattern is None:
        return None
    if not exact:
        print(
            f"Note: the sentence for '{word}' uses a different form of it. Check this card."
        )
    return re.sub(
        pattern, lambda m: f"<b>{m.group(0)}</b>", sentence, count=1, flags=re.I
    )


# ---------------------------------------------------------------- card
def to_row(item, card):
    w = item["word"]
    d = item["dict"]
    verified = d is not None
    if verified:
        try:
            sense = d["senses"][int(card.get("sense"))]
        except (TypeError, ValueError, IndexError):
            sense = d["senses"][0]
        pos, meaning, phonetic = sense["pos"], sense["definition"], d["phonetic"]
        base = d["headword"]
    else:
        pos = card.get("pos", "")
        meaning = card.get("meaning", "")
        phonetic = card.get("phonetic", "")
        base = card.get("base") or w

    sentence = re.sub(r"</?b>|\*\*", "", card.get("sentence", ""))
    front = bold_word(w, sentence)
    if front is None:
        front = sentence
        print(
            f"Warning: '{w}' is not in its sentence, so it is not bold. Check this card."
        )

    tag = "" if (verified or NO_DICT) else "(unverified) "
    is_informal = bool(card.get("informal")) or "(informal)" in meaning.lower()
    meaning = re.sub(
        r"\(informal\)\s*", "", meaning, flags=re.I
    ).strip()  # avoid a double label
    informal = "(informal) " if is_informal else ""
    if pos == "verb":
        # One single Meaning line: (verb, imperative, base_form): definition
        back = (
            f"Meaning (verb, imperative, {base.lower()}): "
            f"{tag}{informal}{meaning.strip()}"
        )
    else:
        back = f"Meaning ({w}, {pos}): {tag}{informal}{meaning}"
    if phonetic:
        back += f"<br>Phonetic: {phonetic}"
    back += f"<br>Tradução: {card.get('translation', '')}"
    return [front, back]


# ---------------------------------------------------------------- main
def report(corrections, skipped, not_verified, offline=()):
    if offline:
        print(
            "Written by the AI from memory (dictionaries were down, marked unverified):",
            ", ".join(offline),
        )
    if corrections:
        print("Spelling fixed:", ", ".join(f"{a} -> {b}" for a, b in corrections))
    if skipped:
        print("Already in Anki (skipped):", ", ".join(skipped))
    if not_verified:
        print("Not verified in the dictionary:", ", ".join(not_verified))


def main():
    try:
        anki("version")
    except (urllib.error.URLError, ConnectionError, OSError):
        sys.exit(
            "Cannot reach Anki. Open Anki and check that AnkiConnect is installed."
        )

    items = dedupe(parse_lines(INPUT))
    print(f"{len(items)} unique words in {INPUT}")

    if NO_DICT:
        print("Dictionaries skipped (--no-dict): the AI writes everything.")
    else:
        print("Checking the dictionary...")
    for it in items:
        if NO_DICT:
            break
        try:
            it["dict"] = lookup_with_forms(it["word"])
        except (
            AllDictsDown
        ):  # no dictionary answers: the AI will write this card itself
            it["dict"], it["offline"] = None, True
    if any(it.get("offline") for it in items):
        print(
            "Warning: the dictionaries are not answering. The AI will write those cards "
            "from memory and mark them (unverified)."
        )

    corrections = fix_spelling(items)
    items = dedupe(items)  # two typos can become the same word

    skipped, new_items = [], []  # skipped: words (text), new_items: full items
    for it in items:
        if in_anki(it["word"]):
            skipped.append(it["word"])
        else:
            new_items.append(it)

    offline = [it["word"] for it in new_items if it.get("offline")]
    not_verified = [
        it["word"]
        for it in new_items
        if it["dict"] is None and not it.get("offline") and not NO_DICT
    ]
    if not_verified and not ALLOW_UNVERIFIED:
        # words skipped because of an outage are always kept: the AI writes them
        new_items = [
            it for it in new_items if it["dict"] is not None or it.get("offline")
        ]
        print(
            "No card for unverified words (use --allow-unverified to make them anyway)."
        )

    if not new_items:
        report(corrections, skipped, not_verified, offline)
        sys.exit("Nothing new to add.")

    cards = generate_cards(new_items)
    # if a sentence does not contain its word at all, ask the AI once more for those cards
    bad = [
        it
        for it in new_items
        if it["word"].lower() in cards
        and find_match(it["word"], cards[it["word"].lower()].get("sentence", ""))[0]
        is None
    ]
    if bad:
        print(
            f"{len(bad)} sentence(s) do not contain their word. Asking the AI again..."
        )
        cards.update(generate_cards(bad, strict=True))
    rows = []
    for it in new_items:
        card = cards.get(it["word"].lower())
        if card is None:
            print(f"Warning: the AI gave no card for '{it['word']}'.")
            continue
        rows.append(to_row(it, card))

    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter=";").writerows(rows)
    print(f"Done! {len(rows)} cards saved in {OUTPUT}")
    report(corrections, skipped, not_verified, offline)


if __name__ == "__main__":
    try:
        main()
    except AllDictsDown:
        sys.exit(
            "Both dictionaries (dictionaryapi.dev and Wiktionary) are not answering.\n"
            "Nothing was lost: the words already checked are saved in dict_cache.json.\n"
            "Check your internet connection, or run the same command again later."
        )
