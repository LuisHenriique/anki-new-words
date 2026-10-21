# AGENTS.md

## Project goal

Help me (a Brazilian Portuguese speaker learning English) turn new English words into Anki cards.
I collect words in `words.txt`. The agent checks Anki for duplicates, makes the cards, and saves a CSV that I import into Anki.

## Files

- `words.txt`: my raw word list (input). Never rewrite it except for the cleanup of imported words in step 5 of the "Default task". Everything else stays untouched.
- `anki_words.py`: the main script. It reads `words.txt`, checks Anki with AnkiConnect, asks the AI for cards, and writes `anki_import.csv`.
- `anki_import.csv`: the output file (semicolon separated, UTF-8).
- `check_csv.py`: tests every line of the CSV (errors and warnings).
- `import_to_anki.py`: adds the good lines of the CSV to Anki through AnkiConnect, only when I ask.
- `run.py`: one command for the whole pipeline (generate, check, import with audio, clean `words.txt`).

## Input format (`words.txt`)

One item per line. Two kinds of lines:

- A single word or phrase: `entreated`
- A sentence with the new word between stars: `*leapfrogs* the ability...`

The word between stars is the target word. The rest of the line is only context.
Ignore empty lines and repeated words (case-insensitive).

## Duplicate check

- Use the AnkiConnect add-on at `http://127.0.0.1:8765` (Anki must be open).
- Search ONLY these two decks (and their subdecks): `English Vocabulary` and `B2 First`. Ignore all other decks. The list is `CHECK_DECKS` at the top of `anki_words.py`.
- For single words, use the whole-word search `w:word`. For phrases, use a quoted search.
- If the word already exists in any deck, skip it and tell me.
- If Anki is not reachable, stop and tell me. Do not make cards without checking.

## Card format

Each CSV row has two fields, separated by `;`:

```
Front;Back
```

Example:

```
They <b>cling</b> to hope.;Meaning (verb, imperative, cling): to hold tightly<br>Phonetic: /klɪŋ/<br>Tradução: agarrar-se, apegar-se, grudar
```

### Front

- One natural, grammatically correct English sentence at B2 level (Cambridge B2 First).
- Length: aim for 6–10 words. Every sentence must have at least 5 words, and stay at about 12–15 words or fewer unless extra context is really needed to show the meaning.
- The sentence must clearly show how the target word or expression is used in that meaning. Avoid vague, unnatural or overly complicated examples.
- The target word is wrapped in `<b>...</b>`.
- If the line had a context phrase, make the sentence fit that meaning.
- Vary sentence structures and verb tenses across cards; do not repeat the same pattern for every card.
- These rules apply to every card: single words, phrasal verbs, idioms and expressions.

### Quality check (Front sentences)

Before delivering a deck, verify each card:

- The example sentence has at least 5 words.
- Most sentences have 6–10 words.
- Sentences over 15 words exist only when the extra context is genuinely helpful.
- The target vocabulary is in `<b>...</b>` in the sentence, in the form that appears on the Front.
- The sentence is natural, clear, B2-level and shows the meaning used on the back.

### Back

- `Meaning (word, part of speech): short and simple English definition`
  - Give exactly ONE meaning. Never put a second definition after a `;` or a comma: it reads as two cards' worth of meaning and forces the CSV to quote the line.
  - If the word has several senses, keep only the one that fits the context phrase (or the most common one when there is no context).
- Part of speech must be one of: noun, verb, adjective, adverb.
- If the word is informal or slang, put `(informal)` before the meaning.
- For verbs, write exactly ONE Meaning line in this shape: `Meaning (verb, imperative, base_form): definition`
  - `base_form` is the dictionary form: `nod` for `nodded`, `cling` for `cling`.
  - Write the definition normally, with no forced final punctuation. Example: `Meaning (verb, imperative, nod): to move your head up and down to show agreement`
  - Never add a second line like `Meaning (imperative form of the verb): nod!`.
  - This applies to every verb, regular or irregular, whatever tense or form appears on the Front.
- For nouns, adjectives and adverbs keep `Meaning (word, part of speech): definition`.
- `Phonetic: /IPA/`
- `Tradução:` Brazilian Portuguese, one to three options separated by commas, from the most common to the least common.
  - The Portuguese must be clear, natural and coherent, with correct grammar, spelling and accents.
  - Use the right form: verbs in the infinitive (`agarrar-se`), nouns in the singular, adjectives in the masculine singular.
  - The translation must match the meaning used in the sentence, not another meaning of the word.
  - No explanations, no English words, no brackets. Do not translate word by word if the result sounds strange in Portuguese.
- Lines are joined with `<br>` (Anki imports with HTML enabled).

## Spelling

- If a word in `words.txt` has a spelling mistake (for example `acquaintence`), correct it automatically. Do not ask me.
- Use the corrected spelling everywhere: in the duplicate check, in the sentence, and on the card.
- Only correct clear typos. If the typo could be two different words, choose the one that fits the context phrase. If there is no context and it is still unclear, skip the word and list it in the final message as "could not identify".
- At the end, always show me a short list of corrections, for example: `acquaintence -> acquaintance`.
- Check the duplicate in Anki with the corrected word, not the typo.

## Sources (avoid hallucination)

- Use only English dictionaries as sources for meaning, part of speech, pronunciation (IPA), and informal labels. Preferred order:
  1. Cambridge Dictionary (dictionary.cambridge.org)
  2. Oxford Learner's Dictionaries
  3. Merriam-Webster Learner's Dictionary
  4. Longman or Collins
- Do not use memory, blogs, forums, or AI-written sites for definitions or IPA.
- Write the definition in simple words, based on the dictionary entry. Do not copy it word by word.
- Choose the dictionary meaning that fits the context phrase (the text around the `*word*`). If there is no context, use the most common meaning.
- Example sentences must be natural B2 English that show the same meaning as the dictionary entry. If the dictionary has a good example, use it as a model, but write a new sentence.
- The `informal` label comes from the dictionary label (for example "informal" or "slang"). Do not guess it.
- If a word cannot be checked in a dictionary (not found, or no access), STILL make a card for it. Do not skip it and do not ask me.
  - Put `(unverified)` before the meaning on the back of that card, so I know to check it.
  - List all unverified words in the final message under "Not verified". That is the only place where I want to be told about them.

## Rules for the agent

- Keep the card style exactly as above. Do not add extra fields or emojis.
- Keep definitions short and easy to understand.
- Use Brazilian Portuguese (not European) for translations.
- Do not invent words, meanings, pronunciations, or examples. Follow the "Spelling" and "Sources" sections above.
- Make the CSV with Python's `csv` module (delimiter `;`, UTF-8) so quotes and special characters stay correct.
- The only way to add notes to my Anki collection is `python import_to_anki.py`, as part of the "Default task" below. Never edit or delete my existing notes.
- If `anki_import.csv` already exists, overwrite it without asking.
- Do not edit the CSV by hand. The only automatic changes allowed are the safe fixes of `python check_csv.py --fix`.

## Default task: one command does everything

When I say "add new words" (or "add the new words", "run it", "make the cards"), do ALL of the steps below, in order, without asking me anything and without waiting for my approval between steps:

**One command:** `python run.py` performs steps 1–5 in order and prints a summary with the numbers for the report. Prefer it; the numbered steps below describe exactly what it must do and remain the fallback if it fails. Do not run `run.py` and the single steps again for the same words.

1. **Make the cards.** Run in the project folder:
   ```bash
   python anki_words.py --no-dict
   ```
   Use `python anki_words.py other.txt --no-dict` if I name another file. The dictionaries are not working, so in this mode the AI fixes the spelling and writes the meaning, IPA, B2 sentence and translation. The cards do NOT get `(unverified)`. When I say the dictionaries work again, use `python anki_words.py --allow-unverified` instead.
   Do not make cards by hand. If the script says "Nothing new to add", stop and tell me. If it fails, stop, show me the full error and suggest a fix (do not change `anki_words.py` without my permission).
2. **Test and fix the CSV.** Run:
   ```bash
   python check_csv.py --fix --anki
   ```
   This applies only the safe fixes (double bold, double `(informal)`, stray `*`) and saves `anki_import_fixed.csv`. Keep its list of ERRORs and WARNINGs with line numbers.
3. **Import with audio.** Run:
   ```bash
   python import_to_anki.py anki_import_fixed.csv
   ```
   It makes an mp3 of each Front sentence with Google text-to-speech (gTTS), writes `sentence [sound:file.mp3]` in the Front field, and adds the notes to the deck `English Vocabulary` (note type `Basic`) with the tags `english` and a batch tag like `import-20261020`. Lines that still have an ERROR are refused automatically. Do not stop because of ERRORs or WARNINGs: import the good lines and report the rest. Never use AwesomeTTS.
4. **Final report.** Show me one short report with:
   - **Spelling fixed**, for example `acquaintence -> acquaintance`
   - **Already in Anki (skipped)**
   - **Not verified** (cards with `(unverified)`) and **Written by the AI from memory (dictionaries were down)**, if any
   - **Refused lines**: line number, word, and the error
   - **Warnings left**: line number, word, and the message (I will check these cards in Anki)
   - **Import**: how many notes were added, how many have audio, and the batch tag
   - If some cards have no audio (Google did not answer), say so and offer `python import_to_anki.py --audio-only` for later
5. **Clean `words.txt`.** Rewrite `words.txt` keeping only the words that did NOT reach Anki:
   - remove every line whose word was added to Anki, and every line whose word was skipped because it is already in Anki (a duplicate is already there);
   - keep, exactly as written (with the `*stars*` and the context), every line that was refused with an ERROR, that got no card from the AI, or that failed for any other reason;
   - keep the original order; if every word was imported, leave `words.txt` empty (the file stays, just with no content);
   - never prune if step 1 said "Nothing new to add" or if step 3 failed to run: in that case `words.txt` stays untouched, so nothing is lost;
   - add one line to the report: **Removed from `words.txt`** (the words removed, or "all of them — the file is now empty").
   This cleanup is the only edit allowed to `words.txt`.

If both dictionaries are not answering and I am not using `--no-dict`, the script does not stop: the AI writes those cards from memory and marks them `(unverified)`. Words already checked keep their dictionary data and are saved in `dict_cache.json`.

The script looks words up in dictionaryapi.dev first and uses Wiktionary as a backup. `dict_cache.json` stores the answers; deleting it only makes the next run slower.

## Import only (when I ask)

If I say only "import" (for example after I fixed the CSV by hand), skip steps 1 and 2 and run `python import_to_anki.py` on the CSV I name (default `anki_import.csv`), then give the report of step 4. `python import_to_anki.py --dry-run` shows what would be imported without changing anything. Use `--no-audio` only if I ask.

## How to run

```bash
python anki_words.py                     # uses words.txt, no cards for unverified words
python anki_words.py --allow-unverified  # also makes cards for unverified words (my default)
python anki_words.py other.txt           # uses another file
```

Manual import, only if I ask: in Anki, File > Import > choose the CSV, set the separator to **semicolon**, and turn on **Allow HTML in fields**.

## Requirements

- Python 3
- Anki open, with the AnkiConnect add-on (code `2055492159`)
- `opencode` working in the terminal (the script calls `opencode run`)
- For audio: `pip install gTTS` (internet needed). If the import says gTTS is missing, tell me the command and do not skip the audio on your own.

## Audio for notes that are already in Anki

Only when I ask (for example "add audio to the cards I imported today"):

```bash
python import_to_anki.py --audio-only                     # notes with today's import tag
python import_to_anki.py --audio-only --search "added:2"  # for example: cards added in the last 2 days
python import_to_anki.py --audio-only --dry-run           # only count them
```

It touches only notes in the deck `English Vocabulary` whose Front has no `[sound:]`, and it only adds the sound tag. It never changes anything else. Ask me to close the Anki Browser window first.
