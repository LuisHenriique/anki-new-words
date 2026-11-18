"""Clone only distributable files, then smoke-test without real Anki or AI."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("git"), "Git is needed for the clean-clone test")
class CleanInstallTests(unittest.TestCase):
    def test_clean_clone_and_fresh_environment_do_not_need_private_files(self):
        base = Path("/tmp/opencode") if Path("/tmp/opencode").is_dir() else None
        with tempfile.TemporaryDirectory(prefix="anki-install-test-", dir=base) as temporary:
            directory = Path(temporary)
            source, clone = directory / "source", directory / "clone"
            source.mkdir()
            files = [*ROOT.glob("*.py"), ROOT / "README.md", ROOT / "AGENTS.md",
                     ROOT / ".gitignore", ROOT / "requirements.txt", ROOT / "exemplo_palavras.txt",
                     *ROOT.glob("web/*.html"), *ROOT.glob("web/*.css"), *ROOT.glob("web/*.js"),
                     *ROOT.glob("tests/test_*.py"), *ROOT.glob("tests/test_*.js")]
            for path in files:
                target = source / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
            hooks = directory / "empty-hooks"
            hooks.mkdir()
            env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                       PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            env.pop("ANKI_IMPORT_DECK", None)

            def run(command, cwd):
                result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                        text=True, encoding="utf-8", errors="replace", timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout

            run(["git", "init", "--quiet"], source)
            run(["git", "add", "."], source)
            run(["git", "-c", "user.name=Installation Test", "-c", "user.email=installation@example.invalid",
                 "-c", "commit.gpgsign=false", "-c", f"core.hooksPath={hooks}",
                 "commit", "--quiet", "-m", "Temporary installation fixture"], source)
            run(["git", "clone", "--quiet", "--no-hardlinks", str(source), str(clone)], directory)
            for name in ("words.txt", ".env", ".venv", "anki_import.csv", "Project_Step_by_Step.docx"):
                self.assertFalse((clone / name).exists(), f"Private file distributed: {name}")
            run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_web_app.py", "-q"], clone)
            if shutil.which("node"):
                run(["node", "--test", "tests/test_web_ui.js"], clone)
            # An empty environment validates standard-library-only startup and
            # missing-dependency guidance. Do not install or call a model here.
            run([sys.executable, "-m", "venv", "--without-pip", str(clone / ".venv")], clone)
            python = clone / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            output = run([str(python), "-B", "-c",
                          "import web_app; web_app.check_anki=lambda:False; "
                          "import iniciar; raise SystemExit(iniciar.main(['--check']))"], clone)
            status, _ = json.JSONDecoder().raw_decode(output)
            self.assertFalse(status["anki"])
            self.assertFalse(status["audio"])
            self.assertFalse(status["ai_auth_checked"])
            self.assertFalse((clone / "words.txt").exists())


if __name__ == "__main__":
    unittest.main()
