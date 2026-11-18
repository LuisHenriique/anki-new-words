# Palavras em inglês para o Anki

Envie um `.txt` pela página local e adicione cartões com frase B2, significado, pronúncia, tradução para português brasileiro e áudio. A página mostra as frases importadas e o resultado de cada palavra, sem popups.

## Comece aqui

### 1. Baixe o projeto

**Sem Git:** nesta página do GitHub, clique em **Code → Download ZIP** e extraia a pasta.

**Com Git:**

```bash
git clone https://github.com/LuisHenriique/anki-new-words.git
cd anki-new-words
```

Os comandos seguintes devem ser executados em um terminal aberto nessa pasta.

### 2. Prepare os requisitos uma única vez

Você instalará **Python, Anki, o complemento AnkiConnect e OpenCode CLI**. Depois disso, o comando `iniciar.py` prepara as bibliotecas Python do projeto. Baixe os programas apenas dos sites oficiais abaixo.

Para executar os comandos, abra o **Terminal/PowerShell** pelo menu Iniciar no Windows, o **Terminal** pelo Spotlight no macOS ou o aplicativo **Terminal** no Linux. Não digite os comandos de sistema dentro do console Python, identificado por `>>>`.

#### A. Instale o Python

**Site oficial:** [python.org/downloads](https://www.python.org/downloads/).

O requisito técnico é **Python 3.10 ou mais recente**, não exatamente 3.10. Para uma instalação nova, escolha uma versão estável ainda com suporte; a série 3.10 já encerrou seu suporte oficial. Evite versões de teste com nomes como alpha, beta ou release candidate.

<details>
<summary>Windows: baixar, instalar e conferir</summary>

1. Abra [Downloads do Python para Windows](https://www.python.org/downloads/windows/).
2. Escolha uma versão estável compatível com o projeto e baixe o instalador oficial ou siga as instruções do Python install manager oferecido no site.
3. Execute o instalador e siga as etapas. Se aparecer a opção **Add python.exe to PATH**, marque-a; ela permite executar Python pelo terminal.
4. Feche e abra novamente o terminal.
5. Confira a instalação com `python --version`. Se esse comando não funcionar, tente `py --version`. O resultado deve indicar uma versão 3.10 ou superior.
6. Use o nome que funcionou nos próximos passos: por exemplo, `py iniciar.py` em vez de `python iniciar.py`.

</details>

<details>
<summary>macOS: baixar, instalar e conferir</summary>

1. Abra [Downloads do Python para macOS](https://www.python.org/downloads/macos/).
2. Baixe o instalador `.pkg` de uma versão estável com suporte e abra o arquivo.
3. Siga as etapas do instalador e abra um novo Terminal.
4. Execute `python3 --version`. O resultado deve indicar uma versão 3.10 ou superior.
5. Nos próximos passos, use `python3 iniciar.py` se o comando `python` não estiver disponível. Não remova nem substitua manualmente o Python fornecido pelo sistema.

</details>

<details>
<summary>Linux: verificar ou instalar pelo gerenciador da distribuição</summary>

1. Abra o Terminal e execute `python3 --version`. Se já houver uma versão compatível, não é necessário reinstalá-la.
2. Se faltar Python ou o suporte a ambientes virtuais, use os pacotes da sua distribuição. Execute **somente o grupo correspondente ao seu sistema**:

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

**Fedora:**

```bash
sudo dnf install python3 python3-pip
```

**Arch Linux:**

```bash
sudo pacman -S python python-pip
```

3. Confira novamente com `python3 --version` ou `python --version`, conforme a distribuição. Se a versão for anterior a 3.10, siga a documentação da sua distribuição para obter uma versão suportada; não substitua manualmente o Python do sistema.
4. Use o nome que funcionou para iniciar o projeto, por exemplo `python3 iniciar.py`.

Referência oficial: [Usando Python em sistemas Unix](https://docs.python.org/3/using/unix.html).

</details>

#### B. Instale o Anki no computador

**Site oficial:** [apps.ankiweb.net](https://apps.ankiweb.net/).

1. Acesse o site e vá até **Download Anki → Desktop**.
2. Escolha seu sistema operacional e o tipo de processador. Em geral, computadores Intel/AMD usam **x64**; computadores ARM precisam da versão **ARM/ARM64**. No macOS, escolha **Apple Silicon** ou **Intel** conforme seu Mac.
3. Instale a versão correspondente:
   - **Windows:** abra o instalador baixado e siga as instruções.
   - **macOS:** abra o `.dmg` e coloque o Anki em **Aplicativos**, conforme indicado.
   - **Linux:** baixe o pacote adequado e siga o [guia oficial de instalação do Anki](https://docs.ankiweb.net/manual/getting-started#installing-&-upgrading), que informa os comandos e requisitos do sistema.
4. Abra o Anki e conclua a configuração inicial, se solicitada.
5. Crie um baralho para receber seu vocabulário, ou use um já existente. Ele será escolhido pela página do projeto.

Para esta integração, use o **Anki Desktop**, não apenas o AnkiWeb ou o aplicativo de celular. O Anki precisa permanecer aberto durante a geração e a importação.

#### C. Instale o AnkiConnect dentro do Anki

**Página do complemento:** [AnkiConnect no AnkiWeb](https://ankiweb.net/shared/info/2055492159).

1. Com o Anki aberto, acesse **Ferramentas → Complementos**.
2. Clique em **Obter complementos…**.
3. Cole o código público do complemento: `2055492159`.
4. Confirme e aguarde a instalação.
5. Feche e abra novamente o Anki para ativar o complemento.
6. Mantenha o aplicativo aberto. Na página do projeto, use **Conferir novamente** e confirme que aparece **Anki conectado**.

O AnkiConnect permite que este projeto converse com o Anki no mesmo computador. **Não abra portas no roteador nem disponibilize o AnkiConnect na rede.** Esse código público de instalação não é uma senha.

#### D. Instale o OpenCode CLI

**Site oficial:** [opencode.ai](https://opencode.ai/). **Instalação do CLI e downloads por sistema:** [documentação oficial do OpenCode](https://opencode.ai/v2/docs/).

O projeto precisa do **CLI**, a versão executável pelo terminal. Instalar somente o aplicativo **Desktop** pode não disponibilizar esse comando. Não é necessário instalar Node.js para usar o binário nativo.

<details>
<summary>Windows: instalar o executável nativo</summary>

1. Na seção **CLI** da documentação oficial, procure os downloads de binários para **Windows**.
2. Escolha o pacote para seu processador: [Windows x64](https://opencode.ai/update/api/latest/cli/opencode/opencode-windows-x64.zip) ou [Windows ARM64](https://opencode.ai/update/api/latest/cli/opencode/opencode-windows-arm64.zip). Confira o tipo em **Configurações → Sistema → Sobre → Tipo de sistema** se tiver dúvida.
3. Extraia o ZIP e guarde `opencode.exe` em uma pasta permanente, fora da pasta deste projeto. Não tente executar o programa de dentro do ZIP.
4. Adicione **a pasta que contém `opencode.exe`**, não o arquivo em si, ao PATH do seu usuário:
   - No menu Iniciar, pesquise **Editar as variáveis de ambiente da sua conta**.
   - Em **Variáveis de usuário**, selecione **Path → Editar → Novo**.
   - Cole o caminho da pasta escolhida e confirme as janelas.
5. Feche e abra novamente o terminal e execute `opencode --version`.

Use o executável nativo **`opencode.exe`**. Este projeto não usa shims `.cmd` e não exige instalar OpenCode por npm no Windows. Se o download padrão não for compatível com seu processador, confira as alternativas na documentação oficial.

</details>

<details>
<summary>macOS e Linux: instalar o CLI</summary>

1. Abra a [seção CLI da documentação oficial](https://opencode.ai/v2/docs/).
2. Escolha um método de instalação indicado para seu sistema. A documentação oferece um instalador oficial por terminal:

```bash
curl -fsSL https://opencode.ai/v2/install | bash
```

Esse comando baixa e executa o instalador do site oficial. Confira a origem e as instruções antes de usá-lo. Como alternativa, baixe o binário nativo correspondente ao sistema e processador, também disponível na documentação.

3. Siga as mensagens do instalador, inclusive as instruções sobre PATH, se houver.
4. Feche e abra novamente o Terminal.
5. Execute `opencode --version`. Se aparecer **comando não encontrado**, confira a instalação e o PATH antes de continuar.

</details>

#### E. Conecte seu próprio acesso à IA no OpenCode

**Guia oficial:** [Conectar provedores no OpenCode CLI](https://opencode.ai/v2/docs/cli/providers).

1. No terminal, execute `opencode` para abrir a interface do OpenCode.
2. Dentro dessa interface, digite `/connect`.
3. Escolha o provedor que deseja usar e siga as instruções de autenticação. Dependendo do provedor, pode ser necessário entrar pelo navegador ou informar uma chave de API **no próprio OpenCode**.
4. Depois, use `/models` na interface para escolher um modelo disponível para sua conta.
5. Encerre a interface do OpenCode quando terminar a configuração e volte ao terminal para iniciar este projeto. Não é necessário manter essa interface aberta.

Não é necessário baixar um modelo para o computador quando você usa um provedor pela internet. Ter acesso a um aplicativo de chat não garante automaticamente acesso à API ou ao método de autenticação escolhido no OpenCode.

Cada pessoa usa seu próprio acesso à IA. Não copie configurações ou credenciais de outra pessoa. O consumo e a cobrança dependem do provedor, modelo e plano escolhidos.

**Não coloque chaves de API, tokens ou senhas no site deste projeto, no `.txt`, no README ou no GitHub.** A configuração do provedor pertence ao OpenCode de cada pessoa. A verificação inicial do projeto detecta o comando instalado, mas não faz uma chamada escondida ao modelo para testar a conta.

#### F. Deixe as bibliotecas Python para o iniciador

Com os programas acima preparados, vá para o próximo passo e execute `python iniciar.py` (ou `python3`/`py`, conforme seu sistema). Ele pergunta antes de criar `.venv` e instalar o gTTS e suas dependências.

**Você não precisa instalar manualmente gTTS nem um framework web.** O iniciador não instala Python, Anki, AnkiConnect ou OpenCode por você e não configura sua conta de IA.

### 3. Abra a página

```bash
python iniciar.py
```

Se seu sistema usa outro nome para o Python, tente `python3 iniciar.py` (Linux/macOS) ou `py iniciar.py` (Windows).

Na primeira execução, o iniciador **pergunta antes** de criar o ambiente privado `.venv` e instalar as dependências de áudio. Isso precisa de internet, mas não instala pacotes no Python global nem chama a IA. Se a preparação já estiver concluída, não a repete.

O navegador abre automaticamente. Se isso não acontecer, use o link completo mostrado no terminal. **O link contém uma chave temporária: não o compartilhe.**

Deixe esse terminal aberto enquanto usa a página. O acesso fica restrito ao próprio computador.

### 4. Confira a preparação e escolha o baralho

Na seção **Antes de começar**, confira os itens e escolha um baralho existente no seu Anki. Não é necessário editar código. A escolha fica somente na sessão da aba; a página não cria baralhos.

O importador usa um tipo de nota chamado **Basic**, com os campos **Front** e **Back**. Se ele não existir, em **Ferramentas → Gerenciar tipos de nota**, adicione uma cópia do tipo básico, nomeie essa cópia como `Basic` e ajuste os nomes dos campos nela. Não precisa alterar notas existentes. O guia da própria página lembra esses passos.

**OpenCode encontrado não significa conta autenticada:** a verificação inicial não faz chamadas ao modelo. Configure seu provedor antes de gerar o primeiro lote.

### 5. Envie as palavras

Use **Baixar um arquivo de exemplo** na página ou prepare qualquer `.txt`, com um item por linha:

```text
stumble
give up
She *shrugged* and walked away.
```

Em frases, marque apenas a palavra ou expressão que quer aprender entre `*estrelas*`. O restante é contexto. Textos corridos não têm seleção automática de vocabulário.

1. Escolha ou arraste o arquivo.
2. Confira a prévia.
3. Clique em **Gerar e adicionar ao Anki**.
4. Aguarde e confira o relatório no final da página.

Até **1 MB e 500 palavras diferentes por lote**. Prefira UTF-8; UTF-16 com BOM e Windows-1252 também são aceitos. Linhas vazias e repetições são ignoradas. Cada lote começa pelo botão, não automaticamente ao atingir uma quantidade de palavras.

## O que acontece durante o processamento?

1. A IA confere grafia e formas básicas.
2. O sistema busca duplicatas em **English Vocabulary**, **B2 First** e, quando diferente, no baralho escolhido; inclui os subbaralhos e ignora os demais.
3. Consulta a **FreeDictionaryAPI.com**, baseada no Wiktionary, para obter referências de significado e IPA.
4. A IA escolhe o sentido pelo contexto, simplifica a definição e escreve a frase B2 e a tradução. Completa os dados que faltarem.
5. O CSV é validado; as linhas válidas são importadas com áudio do Google TTS no baralho escolhido, com o tipo **Basic** e as etiquetas `english` e `import-AAAAMMDD`.

**Unverified** significa que o significado ou a pronúncia precisou ser completado pela IA. Essa indicação aparece **somente no relatório**, nunca nos novos cartões. Frases e traduções são geradas pela IA mesmo quando há referência de dicionário; revise o conteúdo quando necessário. A atribuição às fontes fica na interface.

O relatório separa importadas, já existentes, completadas pela IA, falhas e importações não confirmadas. **Frases adicionadas ao Anki** exibe apenas Fronts cuja importação pôde ser confirmada. Os detalhes técnicos ficam recolhidos. F5 não repete a importação nem abre popups.

Os downloads de palavras pendentes e CSVs são opcionais: os cartões válidos já são enviados diretamente ao Anki. Em caso de falha parcial, confira o relatório e o Anki antes de reenviar o lote.

## O que consome tokens?

- Enviar o arquivo, conferir a prévia, verificar requisitos, escolher baralho, consultar o dicionário, exibir frases e atualizar a página **não fazem chamadas à IA**.
- Conferir grafia e gerar/revisar cartões **usam a IA**, inclusive quando o sistema precisa tentar novamente.
- A conferência de grafia ocorre antes da busca de duplicatas, portanto até uma palavra já existente pode consumir tokens nessa etapa.
- Áudio usa o gTTS, não os tokens do provedor de IA.

## Privacidade e arquivos locais

- O original enviado, `words.txt` e os CSVs existentes do projeto não são modificados pela página. Cada lote roda em uma pasta temporária isolada; o terminal informa onde.
- Baixe os resultados importantes. Histórico e chave de acesso duram enquanto o servidor estiver ligado; arquivos temporários não são um backup permanente.
- `words.txt` é privado e não vem no clone. Ele é necessário apenas para o modo de terminal com lista padrão; crie sua própria lista quando quiser usar esse modo.
- A chave da página é gerada localmente. Nunca publique esse link, capturas com a chave, listas particulares ou arquivos de credenciais.
- O processamento não é totalmente offline: palavras/contextos vão ao provedor de IA; os termos consultados vão à API do dicionário; frases vão ao Google para gerar áudio. Não envie dados pessoais sensíveis.
- Nada no iniciador instala ou autentica OpenCode automaticamente, configura sua conta de IA, altera o firewall ou disponibiliza o Anki na rede.

## Encerrar, atualizar e solucionar problemas

Aguarde o lote terminar, baixe o que deseja guardar e pressione **Ctrl+C** no terminal. Se houver lote ativo, o servidor espera sua conclusão; não force o encerramento.

Após atualizar o código, encerre o servidor sem lote ativo e inicie novamente. **F5 atualiza só a página, não o código Python que já está rodando.**

| Problema | O que fazer |
| --- | --- |
| Python não encontrado | Instale Python; tente os comandos `python3` ou `py` conforme o sistema. |
| Falha ao criar `.venv` | Confira venv/pip. No Linux, pode ser necessário instalar o pacote `python3-venv`. Uma pasta existente incompleta não é apagada automaticamente. |
| Instalação interrompida | Confira a internet e execute `iniciar.py` novamente para concluir. |
| Anki desconectado | Abra o Anki, instale AnkiConnect e reinicie o aplicativo. Depois use **Conferir novamente**. |
| Baralho não aparece | Crie-o no Anki e confira novamente. |
| Basic ausente | Use o guia **Primeira vez? Veja como preparar** na página. |
| OpenCode ausente | Instale o CLI e confira o PATH. No Windows, use o binário nativo `opencode.exe`. |
| Falha da IA | Confira autenticação, modelo e limites no OpenCode. Não coloque chaves no site. |
| Já existe uma página rodando | Use a aba existente ou encerre o servidor anterior antes de iniciar outro. Não há reinício automático de lotes. |
| Porta ocupada | Execute `python iniciar.py --port 8090`. |
| Página pede chave | Abra o link completo mostrado pelo servidor atual, incluindo `#key=`. |
| Linha recusada | Confira o motivo no relatório; as demais podem ter sido importadas. |
| Falha parcial ou resultado incerto | Confira o Anki antes de reenviar, para não confundir geração com importação. |

Outras opções:

```bash
python iniciar.py --check       # diagnóstico sem instalar, abrir navegador ou gerar cartões
python iniciar.py --no-browser  # iniciar e mostrar o link sem abrir navegador
python iniciar.py --yes         # autorizar a preparação do ambiente sem pergunta
```

## Uso pelo terminal (opcional)

Sem outro lote em execução, com os requisitos instalados no Python usado:

```bash
python run.py minha_lista.txt         # gera, importa com áudio e pode limpar essa lista
python run.py minha_lista.txt --keep  # preserva a lista informada
python run.py minha_lista.txt --dry-run  # usa IA e grava CSVs, mas não importa
```

Sem configuração explícita, o destino continua **English Vocabulary** e a busca de duplicatas continua limitada a **English Vocabulary** e **B2 First**. A escolha da página vale para aquele lote, não muda o padrão global dos scripts.

Para tentar acrescentar áudio às notas importadas **hoje no baralho padrão**, feche a janela do Navegador do Anki, mantenha o aplicativo aberto e execute `python import_to_anki.py --audio-only`. Esse comando isolado não usa o baralho escolhido na aba. Para outro destino, defina explicitamente a variável de ambiente `ANKI_IMPORT_DECK` no seu terminal antes de executá-lo.

## Desenvolvimento e testes

```bash
python -B -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/test_web_ui.js
```

Node.js é necessário somente para esses testes da interface, não para usar a página. Os testes usam respostas simuladas, sem gerar cartões nem importar notas na coleção real. A validação de instalação limpa cria um repositório temporário só com os arquivos distribuíveis, clona-o e testa sem seus dados privados.

O bloqueio de instância tem implementações para Linux/macOS e Windows. O workflow de testes no GitHub cobre esses três sistemas; criar o workflow não significa que ele já executou ou passou no GitHub. A execução local só valida nativamente o sistema em que foi realizada.
