#!/usr/bin/env python3
"""Local, authenticated web interface for the existing Anki pipeline."""

import argparse
import base64
import binascii
import csv
import hmac
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from app_runtime import InstanceLock, find_opencode

ROOT = Path(__file__).resolve().parent
MAX_BODY = 1500000
MAX_FILE = 1000000
MAX_ITEMS = 500
SCRIPTS = ("run.py", "anki_words.py", "check_csv.py", "import_to_anki.py", "app_runtime.py")


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


def anki_request(action, **params):
    request = urllib.request.Request(
        "http://127.0.0.1:8765",
        json.dumps({"action": action, "version": 6, "params": params}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        data = json.load(response)
    if data.get("error"):
        raise ValueError("AnkiConnect refused the request")
    return data.get("result")


def check_anki():
    try:
        return bool(anki_request("version"))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def setup_status():
    result = {"anki": check_anki(), "audio": importlib.util.find_spec("gtts") is not None,
              "opencode": find_opencode() is not None, "decks": [], "basic": False,
              "ai_auth_checked": False}
    if result["anki"]:
        try:
            result["decks"] = sorted(name for name in anki_request("deckNames") if isinstance(name, str))
            result["basic"] = "Basic" in anki_request("modelNames")
            if result["basic"]:
                result["basic"] = anki_request("modelFieldNames", modelName="Basic")[:2] == ["Front", "Back"]
        except (OSError, ValueError, TypeError):
            result["anki"] = False
    return result


class FrontPreviewParser(HTMLParser):
    """Extract sentence text and bold spans, never executable card HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.segments = []
        self.bold_depth = 0
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden_depth += 1
        elif not self.hidden_depth:
            if tag in {"b", "strong"}:
                self.bold_depth += 1
            elif tag in {"br", "p", "div"}:
                self.handle_data(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        elif not self.hidden_depth:
            if tag in {"b", "strong"}:
                self.bold_depth = max(0, self.bold_depth - 1)
            elif tag in {"p", "div"}:
                self.handle_data(" ")

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.hidden_depth:
            self.handle_data(" ")

    def handle_data(self, data):
        if self.hidden_depth or not data:
            return
        bold = self.bold_depth > 0
        if self.segments and self.segments[-1]["bold"] == bold:
            self.segments[-1]["text"] += data
        else:
            self.segments.append({"text": data, "bold": bold})


def imported_fronts(directory, added, failed_rows):
    """Read the exact CSV used by the importer, but only expose confirmed rows.

    The importer reports every refusal by CSV row and its final successful count.
    If these do not account for the file exactly, show no speculative previews.
    This also works with older generators that did not emit dictionary metadata.
    """
    if directory is None or added is None or int(added) == 0:
        return []
    try:
        with (Path(directory) / "anki_import_fixed.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.reader(stream, delimiter=";", strict=True))
    except (OSError, UnicodeError, csv.Error):
        return []
    accepted = [row for number, row in enumerate(rows, 1) if number not in failed_rows]
    if len(accepted) != int(added) or any(len(row) != 2 for row in accepted):
        return []
    fronts = []
    for row in accepted:
        parser = FrontPreviewParser()
        parser.feed(re.sub(r"\[sound:[^\]]*\]", "", row[0], flags=re.I))
        parser.close()
        if "".join(segment["text"] for segment in parser.segments).strip():
            fronts.append({"segments": parser.segments})
    return fronts


def summarize(output, directory=None):
    def find(pattern):
        match = re.search(pattern, output)
        return match.group(1) if match else None

    dictionary, skipped = None, []
    for line in output.splitlines():
        if line.startswith("DICTIONARY_SUMMARY: "):
            try:
                candidate = json.loads(line.removeprefix("DICTIONARY_SUMMARY: "))
                if isinstance(candidate, dict):
                    dictionary = candidate
            except ValueError:
                pass
        elif line.startswith("VOCABULARY_SKIPPED: "):
            try:
                candidate = json.loads(line.removeprefix("VOCABULARY_SKIPPED: "))
                if isinstance(candidate, list):
                    skipped = [word for word in candidate if isinstance(word, str)]
            except ValueError:
                pass
    failed_rows = {}
    for number, word, error in re.findall(r"Not imported \| line (\d+) \| (.+?) \| ([^\n]+)", output):
        failed_rows[int(number)] = error.strip()
    for number, word in re.findall(r"Not added \(Anki says duplicate or invalid\) \| line (\d+) \| ([^\n]+)", output):
        failed_rows[int(number)] = "O Anki recusou o cartão como duplicado ou inválido."
    imported, imported_ai, failed, unconfirmed = [], [], [], []
    cards = dictionary.get("cards", []) if dictionary else []
    accepted = [card for card in cards if card.get("row") not in failed_rows]
    added = find(r"Done! (\d+) note\(s\) added")
    # Infer per-word success only when every CSV row is accounted for and the
    # importer's confirmed count matches. Never mistake a generated card for an import.
    confirmed = added is not None and int(added) == len(accepted)
    for card in cards:
        word = card["word"]
        if card.get("row") in failed_rows:
            failed.append({"word": word, "reason": failed_rows[card["row"]]})
        elif confirmed:
            if card.get("ai_completed"):
                imported_ai.append({"word": word, "parts": card["ai_completed"]})
            else:
                imported.append(word)
        else:
            unconfirmed.append(word)
    if dictionary:
        failed.extend({"word": word, "reason": "A IA não gerou um cartão para esta palavra."}
                      for word in dictionary.get("not_generated", []))
    return {
        "added": added,
        "audio": find(r"Audio added to (\d+) of \d+"),
        "audio_total": find(r"Audio added to \d+ of (\d+)"),
        "tag": find(r"Done! \d+ note\(s\) added to '[^']+' \(tag: ([^)]+)\)"),
        "nothing_new": "Nothing new to add" in output,
        "fronts": imported_fronts(directory, added, failed_rows),
        "dictionary": dictionary,
        "outcome": {"imported": imported, "imported_ai": imported_ai,
                    "skipped": skipped, "failed": failed, "unconfirmed": unconfirmed,
                    "available": bool(cards or skipped or (dictionary and dictionary.get("not_generated")))},
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

    def start(self, text, preview, deck="English Vocabulary"):
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
            job = {"id": job_id, "filename": preview["filename"], "count": preview["count"], "deck": deck,
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
            env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
                       PYTHONIOENCODING="utf-8", ANKI_IMPORT_DECK=self.jobs[job_id]["deck"])
            proc = subprocess.Popen(
                [sys.executable, "-u", str(directory / "run.py"), "uploaded_words.txt"],
                cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", env=env,
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
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
                            log="".join(output)[-200000:], summary=summarize("".join(output), directory))
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
        if path == "/exemplo_palavras.txt":
            self.reply(200, (ROOT / "exemplo_palavras.txt").read_bytes(),
                       "text/plain; charset=utf-8", "exemplo_palavras.txt")
            return
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
            self.reply(200, dict(setup_status(), active=active))
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
                deck = payload.get("deck", "English Vocabulary")
                if not isinstance(deck, str) or not deck.strip() or any(ord(c) < 32 for c in deck):
                    raise ValueError("Escolha um baralho válido.")
                setup = setup_status()
                if not setup["anki"]:
                    raise ValueError("Abra o Anki com o AnkiConnect instalado para continuar.")
                if deck not in setup["decks"]:
                    raise ValueError("O baralho escolhido não foi encontrado. Confira novamente a conexão e a seleção.")
                if not setup["basic"]:
                    raise ValueError("Crie no Anki um tipo de nota chamado Basic com os campos Front e Back. Veja o tutorial na página.")
                if not setup["audio"]:
                    raise ValueError("O áudio ainda não está preparado. Execute python iniciar.py para instalar as dependências.")
                if not setup["opencode"]:
                    raise ValueError("Instale e configure o OpenCode CLI. No Windows, use o executável nativo opencode.exe.")
                self.reply(202, {"id": self.server.app.start(text, preview, deck)})
        except (ValueError, UnicodeError) as exc:
            self.reply(400, {"error": str(exc)})
        except OSError:
            self.reply(500, {"error": "Não foi possível preparar os arquivos. Confira o terminal."})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args(argv)
    missing = [name for name in SCRIPTS if not (ROOT / name).is_file()]
    if missing:
        parser.error("Scripts ausentes: " + ", ".join(missing))
    base = Path("/tmp/opencode")
    if not base.is_dir():
        base = Path(tempfile.gettempdir())
    # One web server per project, even when different ports are requested.
    import hashlib
    key = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    instance = InstanceLock(base / f"anki-web-{key}.lock")
    try:
        instance.acquire()
    except OSError:
        parser.error("Já existe uma página Anki rodando para este projeto, ou a pasta temporária não está acessível. Use a página aberta ou confira a pasta antes de tentar novamente.")
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError:
        instance.release()
        parser.error("Não foi possível abrir a porta. Tente: python iniciar.py --port 8090")
    try:
        workspace = Path(tempfile.mkdtemp(prefix="anki-web-", dir=base))
    except OSError:
        server.server_close()
        instance.release()
        parser.error("Não foi possível preparar a pasta temporária. Confira as permissões e o espaço disponível.")
    token = secrets.token_urlsafe(32)
    app = App(token, workspace)
    server.app = app
    server.daemon_threads = True
    url = f"http://localhost:{args.port}/#key={token}"
    print(f"\nComputador: {url}")
    print(f"Arquivos dos lotes: {workspace}")
    print("Mantenha o Anki aberto. Não execute o fluxo pelo terminal ao mesmo tempo.")
    print("Acesso somente neste computador. Não compartilhe o link de acesso.")
    print("Ctrl+C encerra a página. Aguarde o processamento terminar antes de sair.\n", flush=True)
    if args.open_browser:
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
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
        instance.release()


if __name__ == "__main__":
    main()
