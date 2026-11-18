#!/usr/bin/env python3
"""Prepare a private Python environment, then open the local Anki page."""

import argparse
import json
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def environment_python(directory):
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def has_audio(python):
    result = subprocess.run(
        [str(python), "-B", "-c", "import gtts"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.returncode == 0


def prepare_environment(assume_yes=False):
    directory = ROOT / ".venv"
    python = environment_python(directory)
    if python.is_file() and has_audio(python):
        return python
    if directory.exists() and not python.is_file():
        raise RuntimeError("A pasta .venv já existe, mas está incompleta. Nada foi sobrescrito. Confira essa pasta antes de continuar.")
    if not assume_yes:
        print("Vou preparar um ambiente privado em .venv e instalar as dependências de áudio.")
        print("Isso usa internet, não instala pacotes no Python global e não chama a IA.")
        try:
            answer = input("Deseja continuar? [s/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in {"s", "sim"}:
            raise RuntimeError("Preparação cancelada. Nenhuma instalação foi iniciada.")
    if not directory.exists():
        try:
            venv.EnvBuilder(with_pip=True).create(directory)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Não foi possível criar .venv. Confira se o Python inclui venv e pip (no Linux, pode ser necessário instalar python3-venv).") from exc
    pip = subprocess.run([str(python), "-m", "pip", "--version"], capture_output=True)
    if pip.returncode:
        repaired = subprocess.run([str(python), "-m", "ensurepip", "--upgrade"], cwd=ROOT)
        if repaired.returncode:
            raise RuntimeError("O ambiente privado não tem pip. Confira a instalação de Python/venv antes de tentar novamente.")
    result = subprocess.run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], cwd=ROOT)
    if result.returncode or not has_audio(python):
        raise RuntimeError("A instalação não terminou. Confira a internet e as mensagens acima; execute iniciar.py novamente para tentar concluir.")
    return python


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="autorizar a preparação do ambiente sem perguntar")
    parser.add_argument("--check", action="store_true", help="somente verificar requisitos; não instalar, abrir navegador ou chamar IA")
    parser.add_argument("--no-browser", action="store_true", help="mostrar o link sem abrir o navegador")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        print("Instale o Python 3.10 ou mais recente e tente novamente.")
        return 1
    if not 1 <= args.port <= 65535:
        parser.error("Escolha uma porta entre 1 e 65535.")
    if args.check:
        import web_app
        print(json.dumps(web_app.setup_status(), ensure_ascii=False, indent=2))
        print("O acesso à conta de IA não foi testado. Nenhum cartão foi gerado ou importado.")
        return 0
    try:
        python = prepare_environment(args.yes)
        command = [str(python), "-B", str(ROOT / "web_app.py"), "--host", "127.0.0.1", "--port", str(args.port)]
        if not args.no_browser:
            command.append("--open-browser")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        # The server receives Ctrl+C directly and waits safely for an active lot.
        process = subprocess.Popen(command, cwd=ROOT, env=env)
        while True:
            try:
                return process.wait()
            except KeyboardInterrupt:
                print("Aguardando a página encerrar com segurança…", flush=True)
    except KeyboardInterrupt:
        print("Preparação interrompida. Nenhum lote foi iniciado.")
        return 130
    except (OSError, RuntimeError) as exc:
        print(f"Não foi possível iniciar: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
