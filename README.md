# Palavras em inglês para o Anki

Envie um arquivo `.txt` pela página local, confira as palavras e adicione cartões ao Anki com:

- Uma frase de exemplo em inglês no nível B2, com a palavra em negrito.
- Um significado curto em inglês e pronúncia em IPA.
- Tradução para português brasileiro.
- Áudio da frase, gerado com Google Text-to-Speech (gTTS).

O tutorial abaixo considera o uso **somente no computador**, com acesso pelo navegador. O conteúdo é escrito pela IA, sem consulta a dicionários; revise os cartões quando necessário.

## 1. Prepare o ambiente

Execute os comandos deste tutorial em um terminal aberto na pasta do projeto.

Você precisa de:

| Requisito | Como conferir |
| --- | --- |
| Python 3 | Execute `python --version`. |
| Anki | Instale o aplicativo e mantenha-o aberto durante o processamento. |
| AnkiConnect | Instale o complemento conforme as instruções abaixo. |
| OpenCode | Instale, configure o acesso ao provedor de IA e confira `opencode --version`. |
| gTTS | Instale com o comando abaixo, no mesmo ambiente Python usado pelo projeto. |
| Internet | Necessária para a IA e a geração de áudio. |

A página usa a biblioteca padrão do Python, sem precisar de um framework web. O servidor atual requer Linux ou macOS por utilizar `fcntl` para impedir duas instâncias simultâneas.

### Instale o AnkiConnect

1. No Anki, abra **Ferramentas → Complementos → Obter complementos…**.
2. Informe o código público do complemento: `2055492159`.
3. Reinicie o Anki.

Mantenha o AnkiConnect acessível apenas localmente. Não é necessário disponibilizá-lo na rede.

### Instale a dependência de áudio

```bash
python -m pip install -r requirements.txt
```

Se o sistema impedir a instalação global de pacotes, crie um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Nesse caso, ative o ambiente com `source .venv/bin/activate` sempre que abrir outro terminal para usar o projeto. Não adicione a pasta `.venv` ao controle de versão.

## 2. Prepare seu arquivo de palavras

Crie um arquivo com qualquer nome terminado em `.txt`, por exemplo `minha_lista.txt`. Use **um item por linha**:

```text
stumble
give up
She *shrugged* and walked away.
```

- **Palavra ou expressão:** escreva apenas o que deseja aprender.
- **Frase com contexto:** coloque o alvo entre `*estrelas*`. O restante da frase ajuda a escolher o significado.
- Linhas vazias e palavras repetidas são ignoradas, sem diferenciar maiúsculas de minúsculas.
- Erros claros de ortografia são corrigidos durante a geração, não na prévia.
- Textos corridos não têm seleção automática de vocabulário: separe os itens antes de enviar.

**Limites por envio:** até 1 MB e 500 palavras diferentes. Prefira salvar em UTF-8. A página também aceita UTF-16 com BOM e Windows-1252.

O arquivo enviado não precisa ser o `words.txt` do projeto.

## 3. Abra a página no computador

Com o Anki aberto, execute:

```bash
python web_app.py --host 127.0.0.1
```

**Use esse comando completo:** a opção `--host 127.0.0.1` restringe o servidor ao próprio computador. Sem essa opção, o servidor também aceita conexões pela rede local.

O terminal exibirá um link na linha **Computador**. Abra esse link completo no navegador, incluindo a chave após `#key=`.

- A chave é gerada a cada inicialização; use o novo link ao reiniciar o servidor.
- Mantenha o terminal e o Anki abertos enquanto usa a página.
- Não compartilhe o link nem publique capturas de tela que mostrem a chave.

Se a porta padrão estiver ocupada, escolha outra:

```bash
python web_app.py --host 127.0.0.1 --port 8090
```

## 4. Envie e confira a lista

1. Clique em **Escolha seu arquivo .txt** ou arraste o arquivo para a área de envio.
2. Confira a lista em **Conferir e importar**.
3. Verifique se as palavras e os contextos foram identificados corretamente.
4. Clique em **Gerar e adicionar ao Anki**.

A prévia apenas lê o arquivo e identifica repetições internas. A verificação de palavras já existentes no Anki acontece durante o processamento.

Cada envio é um lote iniciado pelo botão. Não há processamento automático ao atingir uma quantidade de palavras.

## 5. Acompanhe a geração e a importação

A página executa o fluxo existente, nesta ordem:

1. Corrige grafia, verifica duplicatas no Anki e gera os cartões com IA.
2. Valida o CSV e aplica as correções seguras disponíveis.
3. Importa as linhas válidas com áudio.
4. Confere quais palavras ficaram pendentes.

A geração pode levar alguns minutos. Apenas um lote é processado por vez. **Não execute os scripts de geração ou importação pelo terminal simultaneamente à página.**

As notas são adicionadas ao baralho **English Vocabulary**, com o tipo de nota **Basic** e as etiquetas `english` e `import-AAAAMMDD`. A verificação de vocabulário duplicado considera **English Vocabulary** e **B2 First**, incluindo seus subbaralhos.

## 6. Confira o resultado e baixe os arquivos

Ao terminar, confira o resumo e abra **Ver relatório completo e mensagens do processo**. O relatório contém as mensagens dos scripts, incluindo correções, duplicatas, recusas e avisos.

| Resultado | O que fazer |
| --- | --- |
| Cartões adicionados | Confira as novas notas no Anki. |
| Palavras já existentes | Foram ignoradas; não precisam ser importadas novamente. |
| `ERROR` ou linha recusada | Leia o número da linha e o motivo. Corrija a causa antes de reenviar o item. |
| `WARNING` | Revise o cartão no Anki; um aviso não impede necessariamente a importação. |
| Falha no processo | Consulte o relatório antes de repetir. Uma parte do lote pode já ter sido importada. |
| Nenhuma palavra nova | Nenhum cartão novo foi criado. |

Os botões de download disponibilizam, quando existentes:

- **Baixar palavras pendentes:** lista após a limpeza normal do fluxo. Itens importados ou já existentes são removidos quando essa limpeza é concluída.
- **Baixar anki_import.csv:** cartões gerados, antes das correções seguras.
- **Baixar anki_import_fixed.csv:** cartões após as correções seguras da validação.

**Atenção:** se a geração ou importação falhar, ou se todas as palavras já estiverem no Anki, a lista para download pode continuar completa. Confira o relatório antes de reenviá-la. Baixar um CSV não significa que todas as suas linhas foram importadas.

### Se algum cartão ficar sem áudio

Confira a conexão com a internet. Para tentar adicionar o áudio às notas com a etiqueta de importação de hoje, feche a janela do **Navegador do Anki**, mantenha o aplicativo aberto e execute, sem outro lote em andamento:

```bash
python import_to_anki.py --audio-only
```

Esse comando atua nas notas de **English Vocabulary** que ainda não têm áudio no campo Front. Para apenas contar as notas que receberiam áudio:

```bash
python import_to_anki.py --audio-only --dry-run
```

## 7. Encerre com segurança

1. Aguarde o lote terminar e confira o resultado.
2. Baixe os arquivos que deseja guardar.
3. No terminal do servidor, pressione **Ctrl+C**.

Se houver um lote ativo, o servidor aguardará sua conclusão antes de encerrar. Não force o encerramento nem desligue o computador durante a importação.

## Onde ficam os dados

- A página cria uma pasta temporária isolada para cada lote e executa cópias dos scripts nessa pasta.
- O arquivo original enviado, o `words.txt` do projeto e os CSVs existentes na pasta do projeto não são alterados pela página.
- A limpeza da lista ocorre apenas na cópia enviada para o lote.
- O terminal informa onde os arquivos temporários foram guardados. Eles não são armazenamento permanente: baixe os resultados importantes.
- O histórico exibido pela página e a chave de acesso valem apenas enquanto aquela instância do servidor estiver ligada.

### Privacidade

A página é local, mas **o processamento não é totalmente offline**:

- As palavras e seus contextos são enviados ao provedor de IA configurado no OpenCode para gerar os cartões.
- As frases dos cartões são enviadas ao serviço de voz do Google para gerar áudio.

Não envie senhas, tokens, documentos privados ou frases com dados pessoais sensíveis. Não versione listas pessoais, CSVs com conteúdo privado, credenciais, links de acesso ou configurações secretas. Os exemplos deste tutorial são genéricos e não contêm chaves reais ou caminhos pessoais.

## Solução de problemas

| Problema | Solução |
| --- | --- |
| A página pede uma chave de acesso | Abra o link completo mostrado no terminal, incluindo `#key=`. |
| O link antigo deixou de funcionar | O servidor foi reiniciado; abra o novo link. |
| A página não abre | Confira se o servidor continua rodando e se está usando a porta indicada no terminal. |
| Porta ocupada | Inicie com `--host 127.0.0.1 --port 8090`. |
| Já existe uma página rodando | Use a instância aberta ou encerre-a antes de iniciar outra. |
| Anki desconectado ou `Cannot reach Anki` | Abra o Anki, confira o AnkiConnect e reinicie o Anki se acabou de instalar o complemento. |
| gTTS ausente | Execute `python -m pip install -r requirements.txt` no mesmo ambiente Python. |
| OpenCode não encontrado | Confira a instalação e se `opencode --version` funciona no terminal do servidor. |
| Falha de autenticação ou geração na IA | Confira o provedor configurado no OpenCode e leia o relatório completo. |
| Arquivo recusado | Use `.txt`, respeite os limites e salve como UTF-8. |
| A página perdeu conexão | Mantenha o servidor ligado e abra novamente o link; o lote pode continuar no computador. |
| Dúvida sobre significado ou IPA | Revise o conteúdo: os cartões são escritos pela IA sem verificação em dicionários. |

## Alternativa: usar somente o terminal

Sem o servidor web processando outro lote, você também pode preparar `words.txt` e executar:

```bash
python run.py
```

Ou usar outro arquivo:

```bash
python run.py minha_lista.txt
```

**Diferentemente do upload pela página, esse comando pode limpar o próprio arquivo informado:** após uma importação concluída, remove as palavras importadas ou já presentes no Anki e mantém as pendentes. Para preservar a lista, use:

```bash
python run.py minha_lista.txt --keep
```

Para gerar e validar sem importar nem limpar a lista:

```bash
python run.py minha_lista.txt --dry-run
```

Essa simulação ainda usa a IA e grava os CSVs de saída. Não execute novamente o fluxo para um lote já importado sem conferir o resultado anterior.

## Testes da interface local

Os testes abaixo não fazem importações reais no Anki:

```bash
python -B -m unittest discover -s tests -p 'test_web_app.py' -v
```
