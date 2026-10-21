# Vocabulário de inglês para o Anki

## O que este projeto faz?

Transforma uma lista de palavras em inglês em cartões do Anki com:

- Frase de exemplo em nível B2, com o vocabulário-alvo em negrito.
- Um significado em inglês e transcrição fonética (IPA).
- Tradução para português brasileiro.
- Áudio da frase gerado pelo Google Text-to-Speech, via gTTS.

O fluxo completo é coordenado por `run.py`:

```text
words.txt
    |
    v
anki_words.py          Gera os cartões e verifica duplicatas no Anki
    |
    v
anki_import.csv
    |
    v
check_csv.py            Valida o CSV e aplica correções seguras
    |
    v
anki_import_fixed.csv
    |
    v
import_to_anki.py       Importa as notas com áudio
    |
    v
Anki                   Baralho English Vocabulary
    |
    v
run.py                 Limpa a lista de entrada e exibe o resumo
```

---

## Pré-requisitos

Configure os itens abaixo antes da primeira execução. Execute os comandos deste guia **na pasta do projeto**.

| Requisito | Configuração necessária |
| --- | --- |
| Python 3 | O comando de verificação abaixo deve informar uma versão 3.x. |
| Anki | Mantenha o aplicativo aberto durante a geração e a importação. |
| AnkiConnect | Instale o complemento de código **2055492159** e reinicie o Anki. |
| Baralhos | A busca de duplicatas usa apenas **English Vocabulary** e **B2 First**, incluindo subbaralhos. |
| OpenCode | Disponível no terminal; é chamado pelo script para gerar os cartões com IA. |
| gTTS | Instalado no mesmo ambiente Python usado para executar os scripts. |
| Internet | Necessária para a IA, o Google Text-to-Speech e os dicionários, quando habilitados. |

### 1. Configure o AnkiConnect

No Anki, acesse **Ferramentas → Complementos → Obter complementos…**, informe o código **2055492159** e reinicie o aplicativo.

O AnkiConnect deve estar acessível neste endereço local:

```text
http://127.0.0.1:8765
```

### 2. Verifique Python e OpenCode

```bash
python --version
opencode --version
```

### 3. Instale e verifique o gTTS

```bash
python -m pip install gTTS
python -c "import gtts; print(gtts.__version__)"
```

Se o módulo `pip` não estiver disponível, como pode ocorrer no Arch Linux, use a alternativa abaixo. Ela exige o `uv` instalado e grava o pacote no diretório de pacotes do usuário:

```bash
uv pip install --target "$(python -c 'import site; print(site.getusersitepackages())')" gTTS
python -c "import gtts; print(gtts.__version__)"
```

---

## Formato da lista de palavras

Use **um item por linha** em `words.txt`. Você pode misturar palavras, expressões e frases com contexto:

```text
entreated
give up
*leapfrogs* the ability to attract top engineers
```

- **Sem contexto:** escreva somente a palavra ou expressão.
- **Com contexto:** coloque apenas o vocabulário-alvo entre asteriscos. O restante da linha orienta a escolha do significado.
- Linhas vazias e itens repetidos são ignorados, sem diferenciar maiúsculas de minúsculas.
- Erros claros de ortografia são corrigidos automaticamente, como `acquaintence` → `acquaintance`.

---

## Como usar

Escolha **um dos modos** abaixo. Não execute os dois para o mesmo lote de palavras.

### Modo Rápido (Recomendado)

#### 1. Prepare a entrada

Adicione os itens a `words.txt`, seguindo o formato acima. Abra o Anki e confirme que os pré-requisitos estão configurados.

#### 2. Execute o fluxo completo

```bash
python run.py
```

O comando executa, nesta ordem:

1. Gera os cartões sem consultar dicionários, usando a opção `--no-dict`.
2. Valida o CSV, verifica duplicatas no Anki e salva as correções seguras.
3. Importa as linhas válidas com áudio.
4. Remove da lista os itens importados ou já existentes no Anki.
5. Exibe o resumo com correções de ortografia, duplicatas, linhas recusadas, notas importadas e áudio.

#### 3. Confira o resultado

- **ERROR:** consulte a linha indicada; cartões estruturalmente inválidos são recusados pelo importador.
- **WARNING:** revise o cartão no Anki; o aviso, por si só, não impede a importação.
- **Sem áudio:** use os comandos da seção [Áudio em notas já importadas](#áudio-em-notas-já-importadas).
- **Itens mantidos na lista:** precisam de revisão ou de uma nova tentativa.

Por padrão, o fluxo continua mesmo se a validação apontar erros. Para interromper antes da importação, use `--stop-on-error`.

#### Opções do modo rápido

| Opção | Comportamento |
| --- | --- |
| Sem opções | Usa `words.txt`, importa com áudio e limpa a lista. |
| Outro arquivo | Usa e, após a importação, limpa a lista informada. |
| `--dry-run` | Gera e valida os CSVs, mas não importa nem limpa a lista. |
| `--keep` | Importa normalmente, mas preserva a lista de entrada. |
| `--stop-on-error` | Interrompe antes da importação se a validação registrar ERROR. |
| `--no-audio` | Importa sem áudio; use somente se esse for o resultado desejado. |

Copie apenas o comando correspondente ao que deseja fazer:

```bash
# Fluxo completo com a lista padrão
python run.py

# Fluxo completo com outra lista
python run.py minha_lista.txt

# Gerar e conferir sem importar; os CSVs ainda são gravados
python run.py --dry-run

# Importar sem limpar a lista
python run.py --keep

# Interromper antes da importação se houver ERROR
python run.py --stop-on-error

# Importar sem áudio
python run.py --no-audio
```

### Modo Passo a Passo (Manual/Avançado)

Use este modo para controlar cada etapa ou retomar um fluxo que falhou. **Não refaça etapas já concluídas para o mesmo lote.**

#### 1. Prepare a entrada

Adicione os itens a `words.txt`, seguindo o formato da lista. Abra o Anki e execute os comandos na pasta do projeto.

#### 2. Gere os cartões

```bash
python anki_words.py --no-dict
```

O script corrige a ortografia, consulta duplicatas nos dois baralhos configurados, lista os itens ignorados e pede à IA a frase, o significado, o IPA e a tradução. O resultado é salvo em `anki_import.csv`.

Para usar outra lista:

```bash
python anki_words.py other.txt --no-dict
```

**Modo atual:** os dicionários estão indisponíveis. Com `--no-dict`, a IA escreve o conteúdo sem consultar essas fontes; os cartões não recebem a marca `(unverified)`.

Quando os dicionários voltarem a funcionar, use:

```bash
python anki_words.py --allow-unverified
```

Nesse modo, o script também permite cartões sem confirmação em dicionário, marcados como `(unverified)`. O modo rápido continua usando `--no-dict`.

Se a geração falhar, resolva o erro antes de continuar. Se aparecer `Nothing new to add`, não há cartões novos para importar.

#### 3. Valide e corrija o CSV

```bash
python check_csv.py --fix --anki
```

- `--fix` corrige apenas negrito duplicado, `(informal)` repetido e asteriscos soltos. O resultado é salvo em **`anki_import_fixed.csv`**.
- `--anki` verifica novamente se o vocabulário já existe nos baralhos configurados.

Exemplo de saída:

```text
Line   1 | unclasping | WARNING | the meaning contains ';': give only one meaning
2 cards checked: 0 error(s) on 0 line(s), 1 warning(s).
```

| Resultado | O que fazer |
| --- | --- |
| ERROR | Leia a mensagem e identifique a linha inválida. O importador recusa erros estruturais detectados em sua própria validação. |
| WARNING | Revise o conteúdo. A linha pode ser importada se não tiver ERROR. |
| Sem erros | Prossiga para a importação. |

**Atenção:** o importador revalida a estrutura do cartão, mas não repete a busca de vocabulário da opção `--anki`. Ele mantém a proteção nativa do Anki contra notas duplicadas.

Para conferir apenas o arquivo, mesmo com o Anki fechado:

```bash
python check_csv.py --fix
```

Essa alternativa **não verifica duplicatas no Anki**. Reabra o Anki antes de importar.

#### 4. Importe as notas com áudio

```bash
python import_to_anki.py anki_import_fixed.csv
```

O importador:

1. Revalida as linhas e recusa as que ainda têm erros estruturais.
2. Gera um MP3 da frase do Front com o Google TTS.
3. Acrescenta a referência de áudio ao Front.
4. Adiciona as notas válidas ao baralho **English Vocabulary**, com o tipo de nota **Basic**.

Formato da referência de áudio:

```text
[sound:arquivo.mp3]
```

Cada nota recebe as etiquetas:

- `english`.
- `import-AAAAMMDD`, correspondente ao dia da importação; por exemplo, `import-20261020`.

Uma linha recusada não impede a importação das demais. Se o Google não responder, algumas notas podem ser importadas sem áudio; confira o resumo.

#### 5. Confira a lista de entrada

**Os comandos manuais acima não limpam `words.txt`.** A limpeza automática pertence ao fluxo de `run.py`. Não presuma que a importação isolada removeu os itens da lista.

As regras de limpeza estão na seção [Limpeza da lista de entrada](#limpeza-da-lista-de-entrada) e no passo 5 da tarefa padrão em `AGENTS.md`.

#### Alternativa: importação pela interface do Anki

Se precisar importar o CSV pela interface, em vez de usar o importador Python:

1. No Anki, acesse **Arquivo → Importar**.
2. Selecione o CSV validado.
3. Defina o separador como **ponto e vírgula**.
4. Ative **Permitir HTML nos campos**.

Essa alternativa não executa a geração de áudio do script Python.

---

## Verificação de duplicatas

A configuração `CHECK_DECKS`, no início de `anki_words.py`, limita a busca a:

- **English Vocabulary** e seus subbaralhos.
- **B2 First** e seus subbaralhos.

Uma palavra é considerada existente quando corresponde ao **vocabulário-alvo** do cartão:

- Texto em negrito no **Front**, marcado com `<b>` ou `<strong>`.
- Vocabulário identificado no cabeçalho **Meaning (...)** do **Back**, incluindo a forma base dos verbos no formato usado pelo projeto.

Ocorrências soltas na frase, na definição ou na tradução **não bastam** para bloquear um novo cartão. Por exemplo, `haste` na tradução de *rod* e `courage` na definição de *guts* não são duplicatas desses vocabulários.

Cartões antigos sem essas marcações podem não ser reconhecidos como duplicatas. A comparação não diferencia maiúsculas de minúsculas.

---

## Limpeza da lista de entrada

Após uma importação concluída pelo modo rápido:

- Itens importados e itens já existentes no Anki são removidos da lista.
- Linhas que falharam são mantidas com o texto original, os asteriscos e o contexto, na mesma ordem.
- Se todos os itens forem removidos, o arquivo permanece no projeto, vazio.
- Ao usar outra lista, a limpeza se aplica ao arquivo informado.

A lista **não é limpa** quando não há palavras novas, a geração falha, a importação não termina com sucesso ou são usadas as opções `--dry-run` ou `--keep`. Se o Anki ficar inacessível durante a conferência da limpeza, o arquivo também é preservado.

---

## Formato dos cartões e do CSV

O CSV usa **UTF-8**, separador **ponto e vírgula** e dois campos por linha:

```text
Front;Back
```

Exemplo de linha:

```text
They still <b>cling</b> to hope today.;Meaning (verb, imperative, cling): to hold tightly<br>Phonetic: /klɪŋ/<br>Tradução: agarrar-se, apegar-se, grudar
```

| Campo | Conteúdo esperado |
| --- | --- |
| Front | Frase natural em nível B2. Busque 6 a 10 palavras, com no mínimo 5, e destaque o vocabulário-alvo em negrito. |
| Back | Um significado curto em inglês, classe gramatical, IPA e 1 a 3 traduções em português brasileiro. |

- Para verbos, o cabeçalho inclui a forma base, como no exemplo acima.
- As partes do Back são separadas por `<br>` para exibição com HTML no Anki.
- Aspas em campos do CSV podem ser necessárias para representar caracteres especiais; não são, por si só, um erro.

Consulte `AGENTS.md` para as regras completas de conteúdo, tradução e validação.

---

## Comandos úteis de importação

Os comandos de geração e validação estão nos dois modos de uso. As opções abaixo servem para trabalhar com um CSV já existente:

| Opção | Resultado |
| --- | --- |
| CSV informado | Importa o arquivo escolhido com áudio. |
| Sem nome de arquivo | Usa `anki_import.csv`. |
| `--dry-run` | Mostra o que seria importado, sem adicionar notas ou gerar áudio. |
| `--no-audio` | Importa sem gerar áudio. |

Copie apenas o comando necessário:

```bash
# Importar o CSV validado
python import_to_anki.py anki_import_fixed.csv

# Importar o CSV padrão: anki_import.csv
python import_to_anki.py

# Simular a importação do CSV padrão
python import_to_anki.py --dry-run

# Importar o CSV padrão sem áudio
python import_to_anki.py --no-audio
```

### Áudio em notas já importadas

**Feche a janela do Navegador do Anki antes de executar. Mantenha o aplicativo Anki aberto.**

O modo `--audio-only` atua apenas em notas do baralho **English Vocabulary** cujo Front ainda não contém áudio. Ele acrescenta o áudio sem alterar o restante do conteúdo.

```bash
# Adicionar áudio às notas com a etiqueta de importação de hoje
python import_to_anki.py --audio-only

# Adicionar áudio às notas dos últimos dois dias
python import_to_anki.py --audio-only --search "added:2"

# Apenas contar as notas que receberiam áudio
python import_to_anki.py --audio-only --dry-run
```

---

## Solução de problemas

| Mensagem ou sintoma | O que fazer |
| --- | --- |
| `Cannot reach Anki` | Abra o Anki. Confirme a instalação do AnkiConnect e reinicie o aplicativo. |
| `No module named gtts` ou `gTTS is missing` | Instale o gTTS no mesmo ambiente Python. Use os comandos de [Pré-requisitos](#pré-requisitos). |
| `words.txt is empty` | Adicione pelo menos um item à lista antes de executar. |
| `Nothing new to add` | Todos os itens identificados já existem no Anki. A lista permanece intacta. |
| Linha recusada com ERROR | Consulte o número da linha e a mensagem da validação. Corrija a causa antes de tentar importar essa linha novamente. |
| `bulked up` sem negrito | Confira se a frase usa exatamente a forma-alvo e se ela está entre as tags de negrito. |
| Cartões sem áudio | Confira a conexão e tente o modo `--audio-only` mais tarde. Feche antes o Navegador do Anki. |
| Palavras permanecem na lista | Confira as falhas no resumo. O modo manual e a opção `--keep` não limpam a entrada. |
| CSV com campos entre aspas | Não remova as aspas automaticamente. Se houver dois significados separados por ponto e vírgula, mantenha apenas um significado. |
| Dicionários indisponíveis | Use o modo atual com `--no-dict`. A IA gera o conteúdo sem consulta aos dicionários. |

Se o modo rápido falhar, identifique a última etapa concluída e use o modo manual para retomar a partir da etapa pendente. Não execute novamente todo o fluxo sem conferir o que já foi importado.

---

## Estrutura do projeto

```text
Learning Language/
├── README.md                # Guia de uso
├── AGENTS.md                # Regras operacionais do agente
├── words.txt                # Lista de entrada
├── run.py                   # Fluxo completo e limpeza da entrada
├── anki_words.py            # Geração dos cartões e busca de duplicatas
├── check_csv.py             # Validação e correções seguras
├── import_to_anki.py        # Importação das notas e geração de áudio
├── anki_import.csv          # CSV gerado
├── anki_import_fixed.csv    # CSV com correções seguras
└── dict_cache.json          # Cache das consultas aos dicionários
```

Os CSVs e o cache são arquivos gerados e não precisam ser versionados. Para mantê-los fora do Git, use as regras abaixo em `.gitignore`, caso ainda não estejam configuradas:

```gitignore
__pycache__/
*.pyc
anki_import*.csv
dict_cache.json
```
