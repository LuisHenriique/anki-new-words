# AGENTS.md

## File modification and permission policy (highest priority)

- **Before taking any action, always consult the current `AGENTS.md` and follow its instructions. Do not rely only on a previously loaded copy.**
- **Never rewrite, edit, overwrite, reformat, reorganize, truncate, or otherwise modify any existing project file unless I explicitly authorize that specific change.**
- This rule applies to `AGENTS.md` itself, source code, scripts, configuration files, data files, CSVs, caches, documentation, and every other project file.
- Suggestions, requests to inspect/debug/explain/review, requests to run a command, or requests to fix a problem do **not** by themselves authorize editing files. First explain the proposed change and ask for permission.
- Before making an authorized edit, state which file(s) will change and what will change. Make only the approved changes; do not bundle in unrelated cleanup, refactoring, formatting, or improvements.
- Do not treat permission to run the workflow or generate its normal output as permission to modify workflow scripts or other existing files beyond the exact changes explicitly allowed by the relevant task instructions.
- Do not change or replace this `AGENTS.md` unless I explicitly ask you to edit `AGENTS.md`. When I do ask, make only the changes I request and preserve all unrelated content.
- If an operation would overwrite or delete an existing file, stop and ask first unless I have explicitly authorized that exact overwrite or deletion in the current request or an applicable standing instruction below.
- If permission is unclear, do not edit. Ask me first.
- These restrictions apply to the agent's actions even if a tool, script, or task would normally make the change automatically. Do not bypass this policy by running another command or script.

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
- `iniciar.py`: beginner launcher; offers a private `.venv` setup, starts the local page, and opens the browser. Installation requires confirmation unless the user explicitly supplies `--yes`; `--check` only diagnoses prerequisites and never calls the AI or imports cards.
- `app_runtime.py`: shared native OpenCode discovery and cross-platform instance locking. On Windows, use the native `opencode.exe`, not a shell shim.
- `exemplo_palavras.txt`: generic downloadable example, never a copy of the user's private input. `words.txt` remains local and is not distributed through Git.

## Input format (`words.txt`)

One item per line. Two kinds of lines:

- A single word or phrase: `entreated`
- A sentence with the new word between stars: `*leapfrogs* the ability...`

The word between stars is the target word. The rest of the line is only context.
Ignore empty lines and repeated words (case-insensitive).

## Duplicate check

- Use the AnkiConnect add-on at `http://127.0.0.1:8765` (Anki must be open).
- By default, search ONLY `English Vocabulary` and `B2 First` (and their subdecks). The list is `CHECK_DECKS` at the top of `anki_words.py`. When the user explicitly chooses another destination in the website, also include that selected deck and its subdecks for that batch, through `ANKI_IMPORT_DECK`. Ignore every other deck; never silently search the entire collection.
- For single words, use the whole-word search `w:word`. For phrases, use a quoted search.
- If the word already exists in any deck, skip it and tell me.
- If Anki is not reachable, stop and tell me. Do not make cards without checking.
- In the website, let the user select an existing destination deck without editing source code. Keep the selection in the browser session and pass it only to the selected batch. Do not create decks, change existing notes, store AI credentials in the site, or test model authentication with a hidden AI call. The default destination remains `English Vocabulary` when no explicit selection is supplied.

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
- Part of speech must be one of: noun, verb, adjective, adverb, phrasal verb, idiom.
- If the word is informal or slang, put `(informal)` before the meaning.
- For ordinary verbs, write exactly ONE Meaning line in this shape: `Meaning (verb, imperative, base_form): definition`
  - `base_form` is the dictionary form: `nod` for `nodded`, `cling` for `cling`.
  - Write the definition normally, with no forced final punctuation. Example: `Meaning (verb, imperative, nod): to move your head up and down to show agreement`
  - Never add a second line like `Meaning (imperative form of the verb): nod!`.
  - This applies to every ordinary verb, regular or irregular, whatever tense or form appears on the Front.
- For phrasal verbs, write exactly ONE Meaning line in this shape: `Meaning (phrasal verb, imperative, base_form): definition`.
  - Include the complete phrasal verb in the base form: `give up` for `gave up`.
  - Keep the actual target form in bold on the Front. Do not add a second imperative line.
- For idioms, use `Meaning (expression, idiom): definition`, for example `Meaning (break the ice, idiom): to make people feel more comfortable together`.
  - Label established phrasal verbs as `phrasal verb`, even when their meaning is idiomatic. Use `idiom` for other established figurative expressions.
  - Do not label an expression as an idiom or phrasal verb merely because it has multiple words. For example, `be flanked by` is an ordinary passive verb construction.
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

- Use FreeDictionaryAPI.com as the dictionary source for meaning, part of speech, pronunciation (IPA), and informal labels: `https://freedictionaryapi.com/api/v1/entries/en/<word>`. Its data comes from the English Wiktionary. Do not confuse it with dictionaryapi.dev.
- Consult the corrected target word or expression. When needed, also consult its dictionary/base form, preserving the complete expression (for example `mess up` for `messed up`). Keep the original target form on the Front and never substitute the base form's IPA for the pronunciation of an inflected target.
- Use dictionary data when available. Do not use blogs, forums, or AI-written sites as dictionary sources. The AI may complete missing data only as the fallback described below.
- Write the definition in simple words, based on the dictionary entry. Do not copy it word by word.
- Choose the dictionary meaning that fits the context phrase (the text around the `*word*`). If there is no context, use the most common meaning.
- Example sentences must be natural B2 English that show the same meaning as the dictionary entry. If the dictionary has a good example, use it as a model, but write a new sentence.
- When a dictionary sense is used, take the `informal` label from its labels (for example "informal", "slang", or "colloquial").
- If a word or expression cannot be found, the API is unavailable or rate-limited, no returned sense fits the context, or any required data such as IPA is missing, STILL make the card. The AI completes the missing data using the existing generation process; do not skip the word or ask me. Preserve usable dictionary data rather than replacing it unnecessarily.
  - Track separately whether the meaning and target pronunciation have dictionary support. Finding a word does not verify the entire card: sentences and translations are still generated by the AI.
  - Report words with AI-completed meaning or pronunciation as "Not verified" / "unverified", identifying which data was completed by the AI.
  - **Verification labels belong only in the report integrated at the bottom of the website page, never in a popup. Never add `(unverified)` or another verification marker to the Front, Back, or other Anki note fields.** Do not modify existing notes to remove old labels without my explicit authorization.
- Keep dictionary attribution only in the website interface: credit FreeDictionaryAPI.com and Wiktionary, show the applicable license and links to the original consulted Wiktionary entries. Do not add attribution, source names, or source links to the cards.
- After a website import finishes, display a clear, visually organized report integrated at the bottom of the page. Do not use popups or modal dialogs, including when restoring a previous result after a page refresh (F5). Separately list words imported with dictionary-supported data, words already in Anki, words actually imported with AI-completed data (unverified), and failures or unconfirmed imports. Keep technical messages collapsed by default. Do not report a card as imported merely because it was generated; use the import results.

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
   python anki_words.py
   ```
   Use `python anki_words.py other.txt` if I name another file. The script fixes spelling, checks Anki for duplicates, consults FreeDictionaryAPI.com, and asks the AI to generate the cards using the available references and complete missing data. Verification status appears only in the report/interface, never on the cards. Legacy `--no-dict` and `--allow-unverified` flags are accepted for compatibility but do not change this behavior.
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
   It makes an mp3 of each Front sentence with Google text-to-speech (gTTS), writes `sentence [sound:file.mp3]` in the Front field, and adds the notes to the explicitly selected destination deck, or `English Vocabulary` by default (note type `Basic`, fields `Front` and `Back`), with the tags `english` and a batch tag like `import-20261020`. Lines that still have an ERROR are refused automatically. Do not stop because of ERRORs or WARNINGs: import the good lines and report the rest. Never use AwesomeTTS.
4. **Final report.** Show me one short report with:
   - **Spelling fixed**, for example `acquaintence -> acquaintance`
   - **Already in Anki (skipped)**
   - **Not verified** (words with meaning or pronunciation completed by the AI, marked only in the report/interface) and **Written by the AI from memory (dictionary data missing or unavailable)**, if any; identify the missing parts
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

If FreeDictionaryAPI.com is unavailable or lacks data, the script continues with AI fallback for the missing parts. The cards remain free of verification labels; the report/interface identifies the affected words and data.

The script uses FreeDictionaryAPI.com, not dictionaryapi.dev or a separate Wiktionary backup. Lookups are cached in memory during each run. The current workflow does not read or write the legacy `dict_cache.json`; do not delete or modify existing cache files without authorization.

## Import only (when I ask)

If I say only "import" (for example after I fixed the CSV by hand), skip steps 1 and 2 and run `python import_to_anki.py` on the CSV I name (default `anki_import.csv`), then give the report of step 4. `python import_to_anki.py --dry-run` shows what would be imported without changing anything. Use `--no-audio` only if I ask.

## How to run

```bash
python anki_words.py                     # words.txt, dictionary API + AI fallback
python anki_words.py other.txt           # another file, same dictionary + AI workflow
python anki_words.py --allow-unverified  # legacy alias; same behavior, no labels on cards
```

Manual import, only if I ask: in Anki, File > Import > choose the CSV, set the separator to **semicolon**, and turn on **Allow HTML in fields**.

## Requirements

- Python 3.10 or newer
- Anki open, with the AnkiConnect add-on (code `2055492159`)
- `opencode` working in the terminal (the script calls `opencode run`)
- For audio: `pip install gTTS` (internet needed). If the import says gTTS is missing, tell me the command and do not skip the audio on your own.
- For beginners, prefer `python iniciar.py`: offer dependency preparation in the private `.venv`, open the local page automatically, and show clear prerequisite guidance. Bind the page only to this computer. Do not terminate or restart an already running instance without authorization; wait for any active batch before shutdown. Keep setup/compatibility tests isolated from real Anki imports and AI calls.

## Audio for notes that are already in Anki

Only when I ask (for example "add audio to the cards I imported today"):

```bash
python import_to_anki.py --audio-only                     # notes with today's import tag
python import_to_anki.py --audio-only --search "added:2"  # for example: cards added in the last 2 days
python import_to_anki.py --audio-only --dry-run           # only count them
```

It touches only notes in the explicitly selected destination deck, or `English Vocabulary` by default, whose Front has no `[sound:]`, and it only adds the sound tag. The standalone command does not inherit a browser selection; another destination requires an explicit `ANKI_IMPORT_DECK` value in that terminal. It never changes anything else. Ask me to close the Anki Browser window first.
