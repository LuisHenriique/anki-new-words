#!/usr/bin/env python3
"""Local, authenticated web interface for the existing Anki pipeline."""

import argparse
import base64
import binascii
import hmac
import importlib.util
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
MAX_BODY = 1500000
MAX_FILE = 1000000
MAX_ITEMS = 500
SCRIPTS = ("run.py", "anki_words.py", "check_csv.py", "import_to_anki.py")


def read_upload(payload):
    name = payload.get("filename", "")
    if not isinstance(name, str) or not name.lower().endswith(".txt"):
        raise ValueError("Escolha um arquivo com extensão .txt.")
    try:
        raw = base64.b64decode(payload.get("data", ""), validate=True)
    except (ValueError, TypeError, binascii.Error):
        raise ValueError("O arquivo enviado é inválido.") from None
    if len(raw) > MAX_FILE:
        raise ValueError("O arquivo deve ter no máximo 1 MB.")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings = ("utf-16",)
    else:
        encodings = ("utf-8-sig", "cp1252")
    text = None
    for encoding in encodings:
        try:
            text = raw.decode(encoding)
            break
        except UnicodeError:
            continue
    if text is None or any(ord(c) < 32 and c not in "\n\r\t" for c in text):
        raise ValueError("Não foi possível ler o texto. Salve o arquivo como UTF-8.")
    items, seen, repeated = [], set(), 0
    for number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        match = re.search(r"\*(.+?)\*", line)
        word = (match.group(1) if match else line).replace("*", "").strip()
        if not word:
            continue
        if word.lower() in seen:
            repeated += 1
            continue
        seen.add(word.lower())
        items.append({"word": word, "context": line if match else "", "line": number})
    if not items:
        raise ValueError("O arquivo está vazio ou não contém palavras.")
    if len(items) > MAX_ITEMS:
        raise ValueError(f"Envie até {MAX_ITEMS} palavras diferentes por vez.")
    return text, {"filename": Path(name.replace("\\", "/")).name,
                  "items": items, "repeated": repeated, "count": len(items)}


def check_anki():
    request = urllib.request.Request(
        "http://127.0.0.1:8765",
        json.dumps({"action": "version", "version": 6}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            data = json.load(response)
        return not data.get("error") and bool(data.get("result"))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def summarize(output):
    def find(pattern):
        match = re.search(pattern, output)
        return match.group(1) if match else None

    return {
        "added": find(r"Done! (\d+) note\(s\) added"),
        "audio": find(r"Audio added to (\d+) of \d+"),
        "audio_total": find(r"Audio added to \d+ of (\d+)"),
        "tag": find(r"Done! \d+ note\(s\) added to '[^']+' \(tag: ([^)]+)\)"),
        "nothing_new": "Nothing new to add" in output,
        "warnings": [line for line in output.splitlines()
                     if re.search(r"WARNING|ERROR|Not imported|Warning:|Spelling fixed:|Already in Anki|unverified", line)],
    }


class App:
    def __init__(self, token, work_root):
        self.token = token
        self.work_root = Path(work_root)
        self.lock = threading.Lock()
        self.jobs = {}
        self.active = None

    def start(self, text, preview):
        with self.lock:
            if self.active:
                raise ValueError("Já existe uma importação em andamento. Aguarde terminar.")
            job_id = secrets.token_hex(12)
            directory = self.work_root / job_id
            directory.mkdir()
            for script in SCRIPTS:
                shutil.copyfile(ROOT / script, directory / script)
            # Never reuse the upload's filename as a path or overwrite project inputs.
            (directory / "uploaded_words.txt").write_text(text, encoding="utf-8")
            job = {"id": job_id, "filename": preview["filename"], "count": preview["count"],
                   "state": "running", "phase": "Verificando os requisitos",
                   "log": "", "summary": {}, "downloads": [], "returncode": None}
            self.jobs[job_id] = job
            self.active = job_id
        threading.Thread(target=self.process, args=(job_id, directory), daemon=True).start()
        return job_id

    def process(self, job_id, directory):
        output = []
        state, code = "failed", None
        try:
            env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1")
            proc = subprocess.Popen(
                [sys.executable, "-u", str(directory / "run.py"), "uploaded_words.txt"],
                cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", env=env,
                start_new_session=True,
            )
            for line in proc.stdout:
                output.append(line)
                with self.lock:
                    job = self.jobs[job_id]
                    job["log"] = (job["log"] + line)[-200000:]
                    for marker, label in (
                        ("1/4", "Criando os cartões"),
                        ("2/4", "Validando os cartões"),
                        ("3/4", "Importando com áudio"),
                        ("4/4", "Conferindo palavras pendentes"),
                    ):
                        if marker in line and line.startswith("==="):
                            job["phase"] = label
            code = proc.wait()
            joined = "".join(output)
            failed = ("The import did not finish", "The card generation failed",
                      "Could not clean words.txt", "words.txt left untouched.")
            success = "Done!" in joined or "Nothing new to add" in joined
            state = "completed" if code == 0 and success and not any(s in joined for s in failed) else "failed"
        except Exception as exc:
            output.append(f"\nFalha ao executar o processo: {exc}\n")
        finally:
            with self.lock:
                job = self.jobs[job_id]
                job.update(state=state, returncode=code,
                           phase="Processo concluído" if state == "completed" else "O processo precisa de atenção",
                           log="".join(output)[-200000:], summary=summarize("".join(output)))
                job["downloads"] = [name for name in
                                    ("uploaded_words.txt", "anki_import.csv", "anki_import_fixed.csv")
                                    if (directory / name).is_file()]
                self.active = None

    def snapshot(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None


class Handler(BaseHTTPRequestHandler):
    server_version = "AnkiLocal/1.0"

    def log_message(self, format, *args):
        # Do not log access credentials or uploaded vocabulary.
        pass

    def reply(self, status, data, content_type="application/json; charset=utf-8", attachment=None):
        body = json.dumps(data, ensure_ascii=False).encode() if isinstance(data, dict) else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        expected = "Bearer " + self.server.app.token
        received = self.headers.get("Authorization", "")
        if not hmac.compare_digest(received.encode(), expected.encode()):
            self.reply(401, {"error": "Chave de acesso inválida. Abra o link mostrado no terminal."})
            return False
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            self.reply(403, {"error": "Origem não permitida."})
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8")}
        if path in assets:
            filename, mime = assets[path]
            self.reply(200, (ROOT / "web" / filename).read_bytes(), mime)
            return
        if not self.authorized():
            return
        if path == "/api/status":
            with self.server.app.lock:
                active = self.server.app.active
            self.reply(200, {"anki": check_anki(), "audio": importlib.util.find_spec("gtts") is not None,
                             "opencode": shutil.which("opencode") is not None, "active": active})
            return
        match = re.fullmatch(r"/api/jobs/([a-f0-9]{24})(?:/files/(uploaded_words\.txt|anki_import\.csv|anki_import_fixed\.csv))?", path)
        if match:
            job_id, filename = match.groups()
            job = self.server.app.snapshot(job_id)
            if job:
                if not filename:
                    self.reply(200, job)
                elif filename in job["downloads"]:
                    data = (self.server.app.work_root / job_id / filename).read_bytes()
                    download_name = "palavras_pendentes.txt" if filename == "uploaded_words.txt" else filename
                    self.reply(200, data, "text/plain; charset=utf-8", download_name)
                else:
                    self.reply(409, {"error": "Arquivo ainda não disponível."})
                return
        self.reply(404, {"error": "Não encontrado."})

    def do_POST(self):
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        if path not in ("/api/preview", "/api/jobs"):
            self.reply(404, {"error": "Não encontrado."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.reply(413, {"error": "Envie um arquivo de até 1 MB."})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Envio inválido.")
            text, preview = read_upload(payload)
            if path == "/api/preview":
                self.reply(200, preview)
            else:
                self.reply(202, {"id": self.server.app.start(text, preview)})
        except (ValueError, UnicodeError) as exc:
            self.reply(400, {"error": str(exc)})
        except OSError:
            self.reply(500, {"error": "Não foi possível preparar os arquivos. Confira o terminal."})


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 80))
            return sock.getsockname()[0]
    except OSError:
        return "IP-DO-COMPUTADOR"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    missing = [name for name in SCRIPTS if not (ROOT / name).is_file()]
    if missing:
        parser.error("Scripts ausentes: " + ", ".join(missing))
    base = Path("/tmp/opencode")
    if not base.is_dir():
        base = Path(tempfile.gettempdir())
    # One web server per project, even when different ports are requested.
    import fcntl
    import hashlib
    key = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    lockfile = open(base / f"anki-web-{key}.lock", "a")
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("Já existe uma página Anki rodando para este projeto.")
    workspace = Path(tempfile.mkdtemp(prefix="anki-web-", dir=base))
    token = secrets.token_urlsafe(32)
    app = App(token, workspace)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.app = app
    server.daemon_threads = True
    print(f"\nComputador: http://localhost:{args.port}/#key={token}")
    if args.host != "127.0.0.1":
        print(f"Celular (mesma rede Wi-Fi): http://{local_ip()}:{args.port}/#key={token}")
    print(f"Arquivos dos lotes: {workspace}")
    print("Mantenha o Anki aberto. Não execute o fluxo pelo terminal ao mesmo tempo.")
    print("Use apenas em uma rede confiável; não exponha esta porta à internet.")
    print("Ctrl+C encerra a página. Aguarde o processamento terminar antes de sair.\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if app.active:
            print("\nAguardando o lote terminar com segurança…", flush=True)
            while True:
                with app.lock:
                    active = app.active
                if not active:
                    break
                threading.Event().wait(1)
    finally:
        server.server_close()
        lockfile.close()


if __name__ == "__main__":
    main()
