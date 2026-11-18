import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app_runtime
import iniciar
import web_app


class LauncherTests(unittest.TestCase):
    def test_declining_setup_does_not_create_an_environment_or_install_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            with (patch.object(iniciar, "ROOT", Path(directory)), patch("builtins.input", return_value="n"),
                  patch("iniciar.venv.EnvBuilder") as builder, patch("iniciar.subprocess.run") as run):
                with self.assertRaises(RuntimeError):
                    iniciar.prepare_environment()
            self.assertFalse((Path(directory) / ".venv").exists())
            builder.assert_not_called()
            run.assert_not_called()

    def test_existing_complete_environment_is_reused_without_pip_or_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = iniciar.environment_python(root / ".venv")
            python.parent.mkdir(parents=True)
            python.touch()
            with (patch.object(iniciar, "ROOT", root), patch("iniciar.has_audio", return_value=True),
                  patch("builtins.input") as prompt, patch("iniciar.subprocess.run") as run):
                self.assertEqual(iniciar.prepare_environment(), python)
            prompt.assert_not_called()
            run.assert_not_called()

    def test_incomplete_preexisting_folder_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / ".venv"
            folder.mkdir()
            (folder / "keep.txt").write_text("user data", encoding="utf-8")
            with patch.object(iniciar, "ROOT", Path(directory)):
                with self.assertRaisesRegex(RuntimeError, "Nada foi sobrescrito"):
                    iniciar.prepare_environment(True)
            self.assertEqual((folder / "keep.txt").read_text(), "user data")

    def test_approved_installation_targets_only_the_private_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = iniciar.environment_python(root / ".venv")
            with (patch.object(iniciar, "ROOT", root), patch("builtins.input", return_value="sim"),
                  patch("iniciar.venv.EnvBuilder") as builder, patch("iniciar.has_audio", return_value=True),
                  patch("iniciar.subprocess.run", return_value=Mock(returncode=0)) as run):
                self.assertEqual(iniciar.prepare_environment(), python)
            builder.assert_called_once_with(with_pip=True)
            builder.return_value.create.assert_called_once_with(root / ".venv")
            self.assertEqual(run.call_args.args[0], [str(python), "-m", "pip", "install", "-r", str(root / "requirements.txt")])

    def test_windows_environment_path(self):
        with patch("iniciar.os", types.SimpleNamespace(name="nt")):
            self.assertEqual(iniciar.environment_python(Path("test-env")), Path("test-env/Scripts/python.exe"))

    def test_approved_retry_can_restore_pip_in_an_existing_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = iniciar.environment_python(root / ".venv")
            python.parent.mkdir(parents=True)
            python.touch()
            with (patch.object(iniciar, "ROOT", root), patch("iniciar.has_audio", side_effect=[False, True]),
                  patch("iniciar.subprocess.run", side_effect=[Mock(returncode=1), Mock(returncode=0), Mock(returncode=0)]) as run):
                self.assertEqual(iniciar.prepare_environment(True), python)
            self.assertEqual(run.call_args_list[1].args[0], [str(python), "-m", "ensurepip", "--upgrade"])

    def test_failed_installation_is_reported_without_starting_the_server(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = iniciar.environment_python(root / ".venv")
            python.parent.mkdir(parents=True)
            python.touch()
            with (patch.object(iniciar, "ROOT", root), patch("iniciar.has_audio", return_value=False),
                  patch("iniciar.subprocess.run", side_effect=[Mock(returncode=0), Mock(returncode=1)]),
                  patch("iniciar.subprocess.Popen") as popen, contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(iniciar.main(["--yes"]), 1)
            popen.assert_not_called()

    def test_check_is_diagnostic_only(self):
        with (patch("web_app.setup_status", return_value={"anki": False, "ai_auth_checked": False}),
              patch("iniciar.prepare_environment") as prepare, patch("iniciar.subprocess.Popen") as popen,
              contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertEqual(iniciar.main(["--check"]), 0)
        prepare.assert_not_called()
        popen.assert_not_called()
        self.assertIn('"ai_auth_checked": false', output.getvalue())

    def test_launcher_opens_page_by_default_and_can_disable_browser(self):
        for options, browser in (([], True), (["--no-browser"], False)):
            with (patch("iniciar.prepare_environment", return_value=Path("private-python")),
                  patch("iniciar.subprocess.Popen") as popen):
                popen.return_value.wait.return_value = 0
                self.assertEqual(iniciar.main(options), 0)
            command = popen.call_args.args[0]
            self.assertEqual("--open-browser" in command, browser)
            self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")


class RuntimeTests(unittest.TestCase):
    def test_lock_excludes_second_process_and_is_released(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instance.lock"
            with app_runtime.InstanceLock(path):
                with self.assertRaises(OSError):
                    app_runtime.InstanceLock(path).acquire()
            with app_runtime.InstanceLock(path):
                self.assertTrue(path.exists())

    def test_windows_lock_uses_msvcrt_and_unlocks_the_same_byte(self):
        fake = types.SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0, locking=Mock())
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {"msvcrt": fake}):
            with app_runtime.InstanceLock(Path(directory) / "test.lock", windows=True):
                self.assertEqual(fake.locking.call_args.args[1:], (2, 1))
            self.assertEqual(fake.locking.call_args.args[1:], (0, 1))

    def test_windows_uses_native_opencode_without_a_shell(self):
        with patch("app_runtime.sys.platform", "win32"), patch("app_runtime.shutil.which", return_value="opencode.exe") as which:
            self.assertEqual(app_runtime.find_opencode(), "opencode.exe")
            which.assert_called_once_with("opencode.exe")

    def test_web_main_opens_the_browser_only_after_binding_to_loopback(self):
        with tempfile.TemporaryDirectory() as directory:
            with (patch("web_app.InstanceLock") as lock, patch("web_app.ThreadingHTTPServer") as server,
                  patch("web_app.tempfile.mkdtemp", return_value=directory),
                  patch("web_app.threading.Thread") as thread, contextlib.redirect_stdout(io.StringIO())):
                server.return_value.serve_forever.side_effect = KeyboardInterrupt
                web_app.main(["--open-browser"])
            self.assertEqual(server.call_args.args[0], ("127.0.0.1", 8080))
            self.assertEqual(thread.call_args.kwargs["target"], web_app.webbrowser.open)
            self.assertTrue(thread.call_args.kwargs["args"][0].startswith("http://localhost:8080/#key="))
            lock.return_value.release.assert_called_once()

    def test_port_collision_releases_the_instance_lock(self):
        with (patch("web_app.InstanceLock") as lock,
              patch("web_app.ThreadingHTTPServer", side_effect=OSError("in use")),
              contextlib.redirect_stderr(io.StringIO())):
            with self.assertRaises(SystemExit):
                web_app.main([])
        lock.return_value.release.assert_called_once()


class SetupAndDeckTests(unittest.TestCase):
    def test_setup_checks_only_read_only_anki_actions_and_never_the_ai(self):
        answers = {"version": 6, "deckNames": ["Meu Inglês"], "modelNames": ["Basic"],
                   "modelFieldNames": ["Front", "Back"]}
        with (patch("web_app.anki_request", side_effect=lambda action, **kw: answers[action]) as anki,
              patch("web_app.find_opencode", return_value="opencode"),
              patch("web_app.importlib.util.find_spec", return_value=object())):
            result = web_app.setup_status()
        self.assertEqual(result["decks"], ["Meu Inglês"])
        self.assertTrue(result["basic"])
        self.assertFalse(result["ai_auth_checked"])
        self.assertEqual([call.args[0] for call in anki.call_args_list], ["version", "deckNames", "modelNames", "modelFieldNames"])

    def test_setup_does_not_claim_translated_fields_are_compatible(self):
        answers = {"version": 6, "deckNames": ["Meu Inglês"], "modelNames": ["Basic"],
                   "modelFieldNames": ["Frente", "Verso"]}
        with patch("web_app.anki_request", side_effect=lambda action, **kw: answers[action]):
            self.assertFalse(web_app.setup_status()["basic"])

    def load_script(self, filename):
        spec = importlib.util.spec_from_file_location("isolated_test_module", web_app.ROOT / filename)
        module = importlib.util.module_from_spec(spec)
        with patch.object(sys, "argv", [filename]):
            spec.loader.exec_module(module)
        return module

    def test_deck_selection_does_not_replace_the_original_duplicate_scope(self):
        with patch.dict(os.environ, {"ANKI_IMPORT_DECK": 'Meu "Inglês"'}):
            generator = self.load_script("anki_words.py")
            importer = self.load_script("import_to_anki.py")
        self.assertEqual(generator.CHECK_DECKS, ["English Vocabulary", "B2 First", 'Meu "Inglês"'])
        self.assertEqual(importer.DECK, 'Meu "Inglês"')
        with patch.object(generator, "anki", return_value=[]) as anki:
            self.assertFalse(generator.in_anki("bathtub"))
        self.assertIn('deck:"Meu \\"Inglês\\""', anki.call_args.kwargs["query"])

    def test_default_decks_are_preserved_without_a_web_selection(self):
        with patch.dict(os.environ):
            os.environ.pop("ANKI_IMPORT_DECK", None)
            generator = self.load_script("anki_words.py")
            importer = self.load_script("import_to_anki.py")
        self.assertEqual(generator.CHECK_DECKS, ["English Vocabulary", "B2 First"])
        self.assertEqual(importer.DECK, "English Vocabulary")

    def test_large_windows_prompt_is_rejected_without_running_a_shell(self):
        generator = self.load_script("anki_words.py")
        with (patch.object(generator, "find_opencode", return_value="opencode.exe"),
              patch.object(generator.sys, "platform", "win32"),
              patch.object(generator.subprocess, "run") as run):
            with self.assertRaisesRegex(RuntimeError, "too long"):
                generator.ask_ai("x" * 31000)
        run.assert_not_called()

    def test_private_deck_is_passed_only_to_the_selected_job_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            app = web_app.App("secret", directory)
            from test_web_app import upload
            text, preview = web_app.read_upload(upload())
            with patch("web_app.threading.Thread"):
                job_id = app.start(text, preview, "Meu Inglês")
            process = types.SimpleNamespace(stdout=io.StringIO("Nothing new to add\n"), wait=lambda: 0)
            before = os.environ.get("ANKI_IMPORT_DECK")
            with patch("web_app.subprocess.Popen", return_value=process) as popen:
                app.process(job_id, Path(directory) / job_id)
            self.assertEqual(popen.call_args.kwargs["env"]["ANKI_IMPORT_DECK"], "Meu Inglês")
            self.assertEqual(os.environ.get("ANKI_IMPORT_DECK"), before)


if __name__ == "__main__":
    unittest.main()
