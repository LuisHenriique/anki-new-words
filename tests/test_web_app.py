import base64
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import web_app


def upload(text="stumble\ngive up\nShe *shrugged* and walked away.\n", filename="minha lista.txt"):
    return {"filename": filename, "data": base64.b64encode(text.encode()).decode()}


class UploadTests(unittest.TestCase):
    def test_preserves_context_and_ignores_duplicates(self):
        source = "\nstumble\nStumble\nShe *shrugged* and walked away.\n"
        text, result = web_app.read_upload(upload(source))
        self.assertEqual(text, source)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["repeated"], 1)
        self.assertEqual(result["items"][1]["word"], "shrugged")
        self.assertEqual(result["items"][1]["context"], "She *shrugged* and walked away.")

    def test_encodings(self):
        for encoding in ("utf-8-sig", "utf-16", "cp1252"):
            payload = {"filename": "palavras.TXT", "data": base64.b64encode("café".encode(encoding)).decode()}
            self.assertEqual(web_app.read_upload(payload)[0], "café")

    def test_invalid_files(self):
        for payload in (upload(""), upload("\x00abc"), upload(filename="bad.csv"),
                        {"filename": "a.txt", "data": "!bad"}, upload("x" * 1000001),
                        upload("\n".join(f"word{i}" for i in range(501)))):
            with self.subTest(payload=str(payload)[:50]), self.assertRaises(ValueError):
                web_app.read_upload(payload)

    def test_untrusted_filename_is_not_a_path(self):
        _, preview = web_app.read_upload(upload(filename="../../words.txt"))
        self.assertEqual(preview["filename"], "words.txt")

    def test_summary(self):
        result = web_app.summarize("Done! 3 note(s) added to 'English Vocabulary' (tag: import-20261117)\nAudio added to 2 of 3\nWARNING line 2")
        self.assertEqual(result["added"], "3")
        self.assertEqual(result["audio"], "2")
        self.assertEqual(result["tag"], "import-20261117")
        self.assertEqual(len(result["warnings"]), 1)


class PipelineTests(unittest.TestCase):
    def outcome_output(self, cards, extra="", skipped=None, not_generated=None):
        dictionary = {"cards": cards, "not_generated": not_generated or [],
                      "meaning_checked": 0, "ipa_checked": 0, "sources": [], "ai_completed": []}
        output = "DICTIONARY_SUMMARY: " + json.dumps(dictionary) + "\n"
        if skipped is not None:
            output += "VOCABULARY_SKIPPED: " + json.dumps(skipped) + "\n"
        return output + extra

    def test_outcome_separates_confirmed_imports_ai_fallback_and_skipped(self):
        cards = [{"word": "bathtub", "row": 1, "ai_completed": []},
                 {"word": "messed up", "row": 2, "ai_completed": ["pronunciation"]}]
        output = self.outcome_output(cards, "Done! 2 note(s) added to 'English Vocabulary' (tag: import-20261118)\n",
                                     skipped=["adamant"])
        outcome = web_app.summarize(output)["outcome"]
        self.assertEqual(outcome["imported"], ["bathtub"])
        self.assertEqual(outcome["imported_ai"], [{"word": "messed up", "parts": ["pronunciation"]}])
        self.assertEqual(outcome["skipped"], ["adamant"])
        self.assertEqual(outcome["failed"], [])
        self.assertEqual(outcome["unconfirmed"], [])

    def test_refused_unverified_card_is_not_reported_as_imported(self):
        cards = [{"word": "bathtub", "row": 1, "ai_completed": []},
                 {"word": "enlarged", "row": 2, "ai_completed": ["meaning"]}]
        output = self.outcome_output(cards,
            "Not imported | line 2 | enlarge | sentence too short\n"
            "Done! 1 note(s) added to 'English Vocabulary' (tag: import-20261118)\n")
        outcome = web_app.summarize(output)["outcome"]
        self.assertEqual(outcome["imported"], ["bathtub"])
        self.assertEqual(outcome["imported_ai"], [])
        self.assertEqual(outcome["failed"], [{"word": "enlarged", "reason": "sentence too short"}])

    def test_anki_rejection_is_separate_from_preexisting_skipped_words(self):
        cards = [{"word": "bathtub", "row": 1, "ai_completed": []}]
        output = self.outcome_output(cards,
            "Not added (Anki says duplicate or invalid) | line 1 | bathtub\n"
            "Done! 0 note(s) added to 'English Vocabulary' (tag: import-20261118)\n")
        outcome = web_app.summarize(output)["outcome"]
        self.assertEqual(outcome["imported"], [])
        self.assertEqual(outcome["skipped"], [])
        self.assertEqual(outcome["failed"][0]["word"], "bathtub")

    def test_generation_is_not_mistaken_for_successful_import(self):
        cards = [{"word": "bathtub", "row": 1, "ai_completed": []},
                 {"word": "adamant", "row": 2, "ai_completed": ["meaning"]}]
        for ending in ("Done! 2 cards saved\nThe import did not finish\n",
                       "Done! 1 note(s) added to 'English Vocabulary' (tag: import-20261118)\n"):
            outcome = web_app.summarize(self.outcome_output(cards, ending))["outcome"]
            self.assertEqual(outcome["imported"], [])
            self.assertEqual(outcome["imported_ai"], [])
            self.assertEqual(outcome["unconfirmed"], ["bathtub", "adamant"])

    def test_all_skipped_and_missing_cards_are_reported(self):
        outcome = web_app.summarize('VOCABULARY_SKIPPED: ["bathtub", "adamant"]\nNothing new to add\n')["outcome"]
        self.assertEqual(outcome["skipped"], ["bathtub", "adamant"])
        self.assertTrue(outcome["available"])
        outcome = web_app.summarize(self.outcome_output([], not_generated=["hit the books"]))["outcome"]
        self.assertEqual(outcome["failed"][0]["word"], "hit the books")

    def test_execution_is_isolated_and_failed_import_is_not_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = web_app.App("secret", temporary)
            text, preview = web_app.read_upload(upload())
            with patch("web_app.threading.Thread"):
                job_id = app.start(text, preview)
            directory = Path(temporary) / job_id
            self.assertEqual((directory / "uploaded_words.txt").read_text(), text)
            self.assertTrue(all((directory / script).is_file() for script in web_app.SCRIPTS))
            with self.assertRaises(ValueError):
                app.start(text, preview)
            process = type("Process", (), {"stdout": io.StringIO("Done! 3 cards saved\nThe import did not finish, so words.txt was not changed.\n"), "wait": lambda self: 0})()
            with patch("web_app.subprocess.Popen", return_value=process) as popen:
                app.process(job_id, directory)
            self.assertEqual(popen.call_args.kwargs["cwd"], directory)
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            self.assertNotIn(str(web_app.ROOT / "words.txt"), popen.call_args.args[0])
            self.assertEqual(app.snapshot(job_id)["state"], "failed")
            self.assertIsNone(app.active)

    def test_nothing_new_is_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = web_app.App("secret", temporary)
            text, preview = web_app.read_upload(upload())
            with patch("web_app.threading.Thread"):
                job_id = app.start(text, preview)
            process = type("Process", (), {"stdout": io.StringIO("Nothing new to add\n"), "wait": lambda self: 0})()
            with patch("web_app.subprocess.Popen", return_value=process):
                app.process(job_id, Path(temporary) / job_id)
            self.assertEqual(app.snapshot(job_id)["state"], "completed")
            self.assertTrue(app.snapshot(job_id)["summary"]["nothing_new"])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.server = web_app.ThreadingHTTPServer(("127.0.0.1", 0), web_app.Handler)
        self.server.app = web_app.App("test-key", self.temporary.name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def request(self, path, payload=None, token="test-key", origin=None):
        headers = {"Authorization": f"Bearer {token}"}
        if origin:
            headers["Origin"] = origin
        request = urllib.request.Request(self.base + path,
                                         json.dumps(payload).encode() if payload is not None else None,
                                         headers=headers)
        return urllib.request.urlopen(request, timeout=3)

    def test_static_page_and_security_headers(self):
        with self.request("/") as response:
            self.assertIn(b'lang="pt-BR"', response.read())
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_authenticated_preview(self):
        with self.request("/api/preview", upload()) as response:
            self.assertEqual(json.load(response)["count"], 3)

    def test_missing_key_and_foreign_origin_refused(self):
        for token, origin, code in (("wrong", None, 401), ("test-key", "http://evil.example", 403)):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.request("/api/preview", upload(), token, origin)
            self.assertEqual(caught.exception.code, code)
            caught.exception.close()

    def test_input_errors_and_path_traversal(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/preview", [])
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/../words.txt")
        self.assertEqual(caught.exception.code, 404)
        caught.exception.close()

    def test_job_start_and_download_allowlist(self):
        with patch.object(web_app.App, "process"):
            with self.request("/api/jobs", upload()) as response:
                self.assertEqual(response.status, 202)
                job_id = json.load(response)["id"]
        with self.request(f"/api/jobs/{job_id}") as response:
            self.assertEqual(json.load(response)["state"], "running")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request(f"/api/jobs/{job_id}/files/uploaded_words.txt")
        self.assertEqual(caught.exception.code, 409)
        caught.exception.close()
        self.server.app.jobs[job_id]["downloads"] = ["uploaded_words.txt"]
        with self.request(f"/api/jobs/{job_id}/files/uploaded_words.txt") as response:
            self.assertIn("palavras_pendentes.txt", response.headers["Content-Disposition"])
            self.assertIn(b"stumble", response.read())


if __name__ == "__main__":
    unittest.main()
