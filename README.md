# Adicionar novas palavras — vocabulário de inglês para o Anki

Transforme uma lista simples de palavras em inglês em cartões prontos para
estudar no Anki, cada um com uma frase de exemplo em nível B2, transcrição
fonética (IPA), tradução para português brasileiro e um áudio gerado pelo
Google Text-to-Speech.

Você adiciona as palavras em `words.txt`; os scripts fazem o resto:

```
words.txt  ->  anki_words.py  ->  anki_import.csv  ->  check_csv.py  ->  import_to_anki.py  ->  Anki
               (cartões)          (CSV dos cartões)    (conferência)        (notas + áudio)
```

---

## 1. Pré-requisitos

Instale isto uma única vez, antes da primeira execução.

| Requisito | Detalhes |
| --- | --- |
| **Python 3** | `python --version` precisa mostrar 3.x |
| **Anki** | Precisa estar **aberto** sempre que você rodar os scripts |
| **Add-on AnkiConnect** | No Anki: *Ferramentas → Complementos → Obter complementos…*, código **2055492159**, depois reinicie o Anki |
| **Baralhos** | `English Vocabulary` e `B2 First` (subbaralhos incluídos). A checagem de duplicados olha apenas esses |
| **opencode** | É quem escreve os cartões. Confira com `opencode --version` |
| **gTTS** | Para o áudio: `python -m pip install gTTS` |
| **Internet** | Necessária para os dicionários e para o Google Text-to-Speech |

Se `python -m pip` não estiver disponível (no Arch Linux, por exemplo), instale o
gTTS no site-packages do usuário:

```bash
uv pip install --target "$(python -c 'import site; print(site.getusersitepackages())')" gTTS
```

Confira a instalação:

```bash
python -c "import gtts; print(gtts.__version__)"
```

---

## 2. Adicione as palavras

Abra `words.txt` e coloque **um item por linha**. Dois formatos são aceitos:

```text
entreated
```

```text
*leapfrogs* the ability to attract top engineers
```

- Uma palavra ou expressão sozinha: escreva apenas ela.
- Uma frase com a palavra nova: coloque **somente a palavra-alvo** entre
  `*asteriscos*`. O resto da linha é o contexto que diz ao agente qual
  significado usar.
- Linhas vazias e palavras repetidas (sem diferenciar maiúsculas) são ignoradas.
- Erros de ortografia são corrigidos automaticamente (ex.: `acquaintence` → `acquaintance`).

---

## 3. Gere os cartões

Execute na pasta do projeto:

```bash
python anki_words.py --no-dict
```

O script:

1. verifica duplicados no Anki (apenas nos dois baralhos configurados);
2. pula as palavras que já existem e mostra a lista;
3. pede à IA a frase, o significado, a transcrição fonética e a tradução;
4. grava o arquivo `anki_import.csv`.

Para usar outro arquivo de entrada:

```bash
python anki_words.py other.txt --no-dict
```

> **Observação:** `--no-dict` é o modo normal aqui, porque as fontes de dicionário
> estão indisponíveis no momento. Se elas voltarem a funcionar, use
> `python anki_words.py --allow-unverified`.

---

## 4. Confira o CSV antes de importar

```bash
python check_csv.py --fix --anki
```

- `--fix` aplica apenas correções seguras (negrito duplicado, `(informal)`
  repetido, `*` perdido) e salva o resultado em **`anki_import_fixed.csv`**.
- `--anki` também confirma que as palavras ainda não estão nos seus baralhos.

Leia a saída linha por linha:

```
Line   1 | unclasping | WARNING | the meaning contains ';': give only one meaning
2 cards checked: 0 error(s) on 0 line(s), 1 warning(s).
```

- **ERROR** — o cartão está quebrado; essa linha será recusada na importação.
- **WARNING** — o cartão funciona, mas vale revisar no Anki depois.

Se o Anki estiver fechado, rode a conferência sem a parte do Anki:

```bash
python check_csv.py --fix
```

---

## 5. Importe para o Anki com áudio

```bash
python import_to_anki.py anki_import_fixed.csv
```

O script cria um MP3 da frase do campo Front com o Google TTS, adiciona
`[sound:arquivo.mp3]` ao Front e insere as notas no baralho **English Vocabulary**
(tipo de nota `Basic`) com as etiquetas:

- `english`
- `import-AAAAMMDD` — uma etiqueta de lote por dia, ex.: `import-20261020`

Linhas com ERROR são puladas automaticamente; as boas continuam sendo importadas.

---

## 6. O que acontece com o `words.txt`

Depois de uma importação bem-sucedida, as palavras que chegaram ao Anki
(importadas **ou** já existentes) são removidas do `words.txt`. Só ficam as
linhas que falharam, exatamente como você escreveu, para a próxima execução
tentar de novo. Veja o passo 5 do `AGENTS.md`.

---

## Formato do cartão

Cada linha do CSV é `Front;Back`:

```text
They <b>cling</b> to hope.;Meaning (cling, verb): hold tightly<br>Meaning (imperative form of the verb): cling!<br>Phonetic: /klɪŋ/<br>Tradução: agarrar-se, apegar-se, grudar
```

- **Front** — uma frase natural em B2, com 6 a 10 palavras, palavra-alvo em
  `<b>...</b>`.
- **Back** — um único significado curto, classe gramatical, linha do imperativo
  para verbos, `Phonetic: /IPA/` e `Tradução:` em português brasileiro
  (1 a 3 opções).

---

## Comandos úteis

| Comando | O que faz |
| --- | --- |
| `python anki_words.py --no-dict` | Cria cartões a partir do `words.txt` |
| `python anki_words.py `*`arquivo`*` --no-dict` | Cria cartões a partir de outra lista |
| `python check_csv.py --fix --anki` | Testa e corrige o CSV com segurança |
| `python import_to_anki.py anki_import_fixed.csv` | Importa as notas com áudio |
| `python import_to_anki.py --dry-run` | Mostra o que seria importado, sem alterar nada |
| `python import_to_anki.py --no-audio` | Importa sem áudio |
| `python import_to_anki.py --audio-only` | Adiciona áudio às notas do lote de hoje |
| `python import_to_anki.py --audio-only --search "added:2"` | Adiciona áudio às notas dos últimos 2 dias |

Para `--audio-only`, feche antes a janela do **Navegador** do Anki.

---

## Importação manual (só se precisar)

No Anki: **Arquivo → Importar**, escolha o CSV, defina o separador como
**ponto e vírgula** e ative **Permitir HTML nos campos**.

---

## Solução de problemas

| Problema | Solução |
| --- | --- |
| `Cannot reach Anki` | Abra o Anki e confirme que o AnkiConnect está instalado e ativo |
| `No module named gtts` | Rode o comando de instalação do gTTS acima e tente de novo |
| Uma linha foi recusada | Leia o ERROR do `check_csv.py`; o cartão não foi importado |
| `bulked up` sem negrito | A frase usou outra forma da palavra; reescreva na mesma forma |
| Alguns cartões sem áudio | O Google não respondeu; rode `python import_to_anki.py --audio-only` depois |
| As palavras voltam sempre | Elas falharam na importação, então continuam no `words.txt` de propósito |
| O CSV aparece entre aspas | Algum campo contém `;` (ex.: dois significados); escreva um único significado |

---

## Estrutura do projeto

```text
Learning Language/
├── README.md                # este guia
├── AGENTS.md                # regras que o agente segue
├── words.txt                # entrada: palavras esperando virar cartões
├── anki_words.py            # passo 1: words.txt  -> anki_import.csv
├── check_csv.py             # passo 2: valida / corrige o CSV
├── import_to_anki.py        # passo 3: CSV -> notas no Anki + áudio
├── anki_import.csv          # gerado (não versionado)
├── anki_import_fixed.csv    # gerado (não versionado)
└── dict_cache.json          # cache dos dicionários (não versionado)
```

Organização opcional: adicione um `.gitignore` para manter os arquivos gerados
fora do git:

```gitignore
__pycache__/
*.pyc
anki_import*.csv
dict_cache.json
```
