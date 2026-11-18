import contextlib
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

with patch.object(sys, "argv", ["anki_words.py"]):
    import anki_words as vocabulary

import web_app


def response(data):
    return io.BytesIO(json.dumps(data).encode())


def entry(word="adamant", pos="adjective", definition="Firm and determined.", ipa="/ˈæd.ə.mənt/", tags=None):
    return {"entries": [{"partOfSpeech": pos,
                         "pronunciations": [{"type": "ipa", "text": ipa, "tags": ["General American"]}] if ipa else [],
                         "senses": [{"definition": definition, "tags": tags or []}]}],
            "source": {"url": "https://en.wiktionary.org/wiki/" + word}}


def card(word="adamant", **kwargs):
    result = {"word": word, "sentence": f"She remained {word} despite all our objections.",
              "meaning": "determined not to change your decision", "pos": "adjective",
              "base": word, "phonetic": "/ai/", "translation": "inflexível", "informal": False,
              "dictionary_sense": "sense-0"}
    result.update(kwargs)
    return result


class DictionaryTests(unittest.TestCase):
    def test_lookup_is_encoded_cached_and_has_timeout(self):
        client = vocabulary.DictionaryClient()
        with patch("anki_words.urllib.request.urlopen", return_value=response(entry(word="hit the books"))) as request:
            first = client.lookup("hit the books")
            self.assertIs(first, client.lookup("HIT THE BOOKS"))
        self.assertEqual(request.call_count, 1)
        self.assertTrue(request.call_args.args[0].full_url.endswith("hit%20the%20books"))
        self.assertEqual(request.call_args.kwargs["timeout"], 8)
        self.assertEqual(first["status"], "found")

    def test_empty_and_404_do_not_disable_next_lookup(self):
        client = vocabulary.DictionaryClient()
        missing = urllib.error.HTTPError("https://example.invalid", 404, "missing", {}, None)
        with patch("anki_words.urllib.request.urlopen", side_effect=[response({"entries": []}), missing, response(entry())]):
            self.assertEqual(client.lookup("unknown")["status"], "not_found")
            self.assertEqual(client.lookup("other")["status"], "not_found")
            self.assertEqual(client.lookup("adamant")["status"], "found")

    def test_rate_limit_and_outage_fall_back_without_repeated_requests(self):
        for error in (TimeoutError("timeout"), urllib.error.HTTPError("https://example.invalid", 429, "limit", {}, None)):
            client = vocabulary.DictionaryClient()
            with patch("anki_words.urllib.request.urlopen", side_effect=error) as request:
                self.assertEqual(client.lookup("adamant")["status"], "unavailable")
                self.assertEqual(client.lookup("bathtub")["status"], "unavailable")
            self.assertEqual(request.call_count, 1)

    def test_malformed_response_falls_back(self):
        client = vocabulary.DictionaryClient()
        with patch("anki_words.urllib.request.urlopen", return_value=response([])):
            self.assertEqual(client.lookup("adamant")["status"], "unavailable")

    def test_base_form_is_used_for_meaning_but_not_for_target_ipa(self):
        item = {"word": "enlarged", "context": "", "lookup_base": "enlarge"}
        surface = entry("enlarged", "verb", "simple past and past participle of enlarge", "/ɪnˈlɑɹd͡ʒd/", ["form of"])
        lemma = entry("enlarge", "verb", "To make something larger.", "/ɪnˈlɑɹd͡ʒ/")
        with patch("anki_words.urllib.request.urlopen", side_effect=[response(surface), response(lemma)]):
            vocabulary.prepare_dictionary([item], vocabulary.DictionaryClient())
        self.assertEqual(len(item["dictionary"]), 1)
        result = vocabulary.apply_dictionary(item, card("enlarged", pos="verb"))
        self.assertEqual(result["phonetic"], "/ɪnˈlɑɹd͡ʒd/")
        self.assertEqual(result["_ai_completed"], [])
        self.assertEqual(item["word"], "enlarged")

    def test_missing_target_ipa_keeps_ai_pronunciation(self):
        item = {"word": "messed up", "context": "", "lookup_base": "mess up"}
        with patch("anki_words.urllib.request.urlopen", side_effect=[response({"entries": []}), response(entry("mess up", "verb", ipa="/mes ʌp/"))]):
            vocabulary.prepare_dictionary([item], vocabulary.DictionaryClient())
        result = vocabulary.apply_dictionary(item, card("messed up", pos="phrasal verb"))
        self.assertEqual(result["phonetic"], "/ai/")
        self.assertEqual(result["_ai_completed"], ["pronunciation"])

    def test_dictionary_controls_ipa_and_informal_label(self):
        item = {"word": "adamant", "context": ""}
        with patch("anki_words.urllib.request.urlopen", return_value=response(entry())):
            vocabulary.prepare_dictionary([item], vocabulary.DictionaryClient())
        result = vocabulary.apply_dictionary(item, card(informal=True, meaning="(informal) determined"))
        self.assertEqual(result["phonetic"], "/ˈæd.ə.mənt/")
        self.assertFalse(result["informal"])
        self.assertNotIn("informal", result["meaning"])
        self.assertEqual(result["_ai_completed"], [])

    def test_colloquial_source_sets_informal(self):
        item = {"word": "adamant", "context": ""}
        with patch("anki_words.urllib.request.urlopen", return_value=response(entry(tags=["colloquial"]))):
            vocabulary.prepare_dictionary([item], vocabulary.DictionaryClient())
        self.assertTrue(vocabulary.apply_dictionary(item, card())["informal"])

    def test_unknown_sense_never_counts_as_verified_meaning(self):
        item = {"word": "adamant", "context": ""}
        with patch("anki_words.urllib.request.urlopen", return_value=response(entry())):
            vocabulary.prepare_dictionary([item], vocabulary.DictionaryClient())
        result = vocabulary.apply_dictionary(item, card(dictionary_sense="made-up-id"))
        self.assertIn("meaning", result["_ai_completed"])

    def test_full_fallback_makes_card_without_attribution_links(self):
        result = vocabulary.apply_dictionary({"word": "adamant"}, card())
        row = vocabulary.to_row({"word": "adamant"}, result)
        self.assertNotIn("(unverified)", row[1])
        self.assertIn("Phonetic: /ai/", row[1])
        self.assertNotIn("wiktionary", row[1])
        self.assertNotIn("freedictionaryapi", row[1])
        self.assertNotIn("https://", row[1])

    def test_verification_label_is_removed_even_if_ai_puts_it_in_meaning(self):
        result = card(meaning="(unverified) determined", _ai_completed=["meaning"])
        row = vocabulary.to_row({"word": "adamant"}, result)
        self.assertNotIn("unverified", row[1])

    def test_ipa_selection_and_source_safety(self):
        self.assertEqual(vocabulary.choose_ipa([
            {"type": "ipa", "text": "/british/", "tags": ["Received Pronunciation"]},
            {"type": "ipa", "text": "/american/", "tags": ["General American"]},
        ]), "/american/")
        self.assertEqual(vocabulary.choose_ipa([{"type": "ipa", "text": "/<script>/"}]), "")
        self.assertEqual(vocabulary.safe_source_url("https://evil.example/wiki/test"), "")
        self.assertEqual(vocabulary.safe_source_url("javascript:alert(1)"), "")

    def test_spelling_metadata_keeps_target_form(self):
        items = [{"word": "messed up", "context": "I messed up so much"}]
        with patch("anki_words.ask_ai", return_value=[{"word": "messed up", "corrected": "", "lookup_base": "mess up"}]):
            self.assertEqual(vocabulary.fix_spelling(items), [])
        self.assertEqual(items[0]["word"], "messed up")
        self.assertEqual(items[0]["lookup_base"], "mess up")

    def test_prompt_contains_dictionary_and_selected_sense_contract(self):
        item = {"word": "adamant", "context": "", "dictionary": [{"id": "sense-0", "definition": "Firm."}]}
        with patch("anki_words.ask_ai", return_value=[card()]) as ask:
            vocabulary.generate_cards([item])
        prompt = ask.call_args.args[0]
        self.assertIn('"dictionary_sense"', prompt)
        self.assertIn('"definition": "Firm."', prompt)

    def test_end_to_end_generation_and_interface_summary_without_anki_import(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "input.txt").write_text("adamant\n", encoding="utf-8")
            output = io.StringIO()
            with (patch.object(vocabulary, "INPUT", path / "input.txt"),
                  patch.object(vocabulary, "OUTPUT", path / "cards.csv"),
                  patch("anki_words.anki", return_value=6),
                  patch("anki_words.in_anki", return_value=False),
                  patch("anki_words.ask_ai", side_effect=[[{"word": "adamant", "corrected": "", "lookup_base": ""}], [card()]]),
                  patch("anki_words.urllib.request.urlopen", return_value=response(entry())),
                  contextlib.redirect_stdout(output)):
                vocabulary.main()
            csv = (path / "cards.csv").read_text()
            self.assertIn("/ˈæd.ə.mənt/", csv)
            self.assertNotIn("unverified", csv)
            self.assertNotIn("wiktionary", csv)
            summary = web_app.summarize(output.getvalue())["dictionary"]
            self.assertEqual(summary["meaning_checked"], 1)
            self.assertEqual(summary["ipa_checked"], 1)
            self.assertEqual(summary["ai_completed"], [])
            self.assertEqual(summary["sources"][0]["url"], "https://en.wiktionary.org/wiki/adamant")
            self.assertEqual(summary["cards"], [{"word": "adamant", "row": 1, "ai_completed": []}])

    def test_outage_still_writes_ai_card_and_reports_partial_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "input.txt").write_text("adamant\n", encoding="utf-8")
            output = io.StringIO()
            with (patch.object(vocabulary, "INPUT", path / "input.txt"),
                  patch.object(vocabulary, "OUTPUT", path / "cards.csv"),
                  patch("anki_words.anki", return_value=6),
                  patch("anki_words.in_anki", return_value=False),
                  patch("anki_words.ask_ai", side_effect=[[{"word": "adamant", "corrected": ""}], [card()]]),
                  patch("anki_words.urllib.request.urlopen", side_effect=TimeoutError()),
                  contextlib.redirect_stdout(output)):
                vocabulary.main()
            self.assertNotIn("(unverified)", (path / "cards.csv").read_text())
            self.assertIn("Not verified: adamant", output.getvalue())
            summary = web_app.summarize(output.getvalue())["dictionary"]
            self.assertEqual(summary["ai_completed"][0]["parts"], ["meaning", "pronunciation"])


if __name__ == "__main__":
    unittest.main()
