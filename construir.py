# construir.py — monta os dois pacotes da demo.
#
# USO:  python construir.py
#
# Ele faz tres coisas, nesta ordem:
#
#   1. COPIA o jogo do projeto para `jogo/`, aqui dentro. A pasta do projeto
#      nunca e tocada: este script so le de la.
#   2. DEIXA DE FORA o que nao pode ser distribuido (ver LISTA_NEGRA).
#   3. CHAMA o PyInstaller duas vezes — um .exe unico para mandar por link,
#      e uma pasta para testar e trocar arquivo sem rebuildar.
#
# Rodar de novo e seguro: ele limpa `jogo/`, `build/` e `dist/` antes.

import os
import shutil
import subprocess
import sys
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
DESTINO = os.path.join(AQUI, 'jogo')

# ⚠ O NOME DO EXECUTAVEL E O DO TITULO DO JOGO, e nao o da pasta do projeto.
# Ele era "Chamado da Meia-Noite.exe" enquanto a janela e a tela de titulo
# diziam "THE MIDNIGHT CALL" — jogo comprado nao tem dois nomes.
NOME = 'The Midnight Call'
PASTA_DEMO = 'The Midnight Call - Demo'
VERSAO = (1, 0, 0, 0)
VERSAO_TEXTO = 'Demo 1.0'
AUTOR = 'Luiz Fernandes'


# ---------------------------------------------------------------------------
# ONDE ESTA O PROJETO
# ---------------------------------------------------------------------------
# 🐛 Isto era um caminho absoluto escrito na mao, e quebrou no dia em que o
# Luiz reorganizou as pastas: o build parou de achar o jogo. Caminho fixo em
# script de build e uma bomba-relogio — funciona ate alguem arrastar uma
# pasta.
#
# Agora ele PROCURA. Um projeto valido e uma pasta que tenha index.html e
# js/main.js dentro; se houver duvida, da para mandar pelo ambiente:
#
#     $env:TMC_PROJETO = "C:\caminho\do\projeto"; python construir.py
# ⚠ RECONHECER PELA IDENTIDADE, NAO PELA FORMA.
#
# 🐛 A primeira versao disto aceitava "qualquer pasta com index.html e
# js/main.js" e ficava com a PRIMEIRA que encontrasse. Na maquina do Luiz
# isso deu em cheio no alvo errado duas vezes:
#
#   1. pegou uma copia VELHA do proprio jogo (DESENVOLVIMENTO/), sem as
#      correcoes — o build saiu inteiro e so quebrou na verificacao;
#   2. e havia OUTRO JOGO na arvore (DUNGEON GOLD) com index.html e
#      js/main.js iguais. Empacotar o jogo errado e um resultado que passa
#      despercebido ate alguem abrir o .exe.
#
# Forma nao identifica nada: metade dos projetos de jogo em HTML tem essa
# forma. Entao a checagem olha O NOME DO JOGO dentro do index.html, e o
# documento mestre, que so existe neste projeto.
MARCA_TITULO = 'the midnight call'
MARCA_ARQUIVO = 'CHAMADO_DA_MEIA_NOITE.md'


def e_o_projeto(caminho):
    idx = os.path.join(caminho, 'index.html')
    if not (os.path.isfile(idx)
            and os.path.isfile(os.path.join(caminho, 'js', 'main.js'))):
        return False
    try:
        with open(idx, 'r', encoding='utf-8', errors='ignore') as f:
            return MARCA_TITULO in f.read(4000).lower()
    except OSError:
        return False


def achar_projeto():
    forcado = os.environ.get('TMC_PROJETO')
    if forcado:
        if e_o_projeto(forcado):
            return os.path.abspath(forcado)
        raise SystemExit(f'TMC_PROJETO nao aponta para o projeto: {forcado}')

    achados = []
    vistos = set()
    topo = AQUI
    for _ in range(5):
        topo = os.path.dirname(topo)
        if not topo or topo in vistos:
            break
        vistos.add(topo)
        for raiz, pastas, _arq in os.walk(topo):
            pastas[:] = [p for p in pastas
                         if p not in ('.git', 'node_modules', '__pycache__')]
            # nada que esteja DENTRO desta oficina conta: as copias que o
            # proprio build gerou passariam na checagem e se auto-elegeriam
            if os.path.commonpath([os.path.abspath(raiz), AQUI]) == AQUI:
                continue
            if e_o_projeto(raiz) and raiz not in achados:
                achados.append(raiz)

    if not achados:
        raise SystemExit(
            'Nao achei o projeto do jogo.\n'
            'Aponte na mao:  $env:TMC_PROJETO = "C:\\caminho\\do\\projeto"'
        )

    # Entre varias copias validas, ganha a que tem o documento mestre (a de
    # trabalho) e, dentro dessas, a de `js/main.js` mais recente.
    def peso(p):
        try:
            quando = os.path.getmtime(os.path.join(p, 'js', 'main.js'))
        except OSError:
            quando = 0
        return (os.path.isfile(os.path.join(p, MARCA_ARQUIVO)), quando)

    achados.sort(key=peso, reverse=True)
    if len(achados) > 1:
        print(f'⚠ {len(achados)} copias do jogo encontradas. As outras:')
        for p in achados[1:]:
            print(f'    {p}')
    return achados[0]


PROJETO = achar_projeto()

# O que o jogo precisa para rodar. Nada mais entra: ferramentas, testes,
# documento mestre, roteiro e .git ficam de fora do pacote do jogador.
COPIAR = ['index.html', 'css', 'js', 'assets']

# ---------------------------------------------------------------------------
# O QUE NAO VAI PARA O PACOTE, E POR QUE
# ---------------------------------------------------------------------------
# Os dois arquivos de audio ficam de fora, e por motivos diferentes.
#
# musica-casa.mp3 .. sao 110 MB E veio do YouTube (ver o LEIA-ME.txt de
#                    assets/audio, e a ressalva R-34 do documento mestre).
#                    Distribuir faixa de terceiro nao licenciada e problema
#                    de direitos; 110 MB num pacote de demo e problema de
#                    bom senso. Sem ela, `tocarMusicaArquivo` devolve false
#                    e o piano sintetizado entra no lugar.
#
#                    Para colocar musica na demo: corte 1 a 3 minutos que
#                    fechem em loop, exporte a 128 kbps (~2 MB) e tire o
#                    nome daqui.
#
# narrator.mp3 ..... a DUBLAGEM da abertura. Fora a pedido do Luiz, e com
#                    razao: aquela gravacao NAO corresponde ao roteiro
#                    (bug B-20, aberto desde a sessao 03 — o audio tem
#                    60,76s contra 77s de texto, e a correlacao entre as
#                    duas coisas deu 0,15, ou seja, nenhuma). Numa demo,
#                    uma voz dizendo uma coisa enquanto a legenda diz outra
#                    e pior do que voz nenhuma.
#
#                    A cutscene NAO quebra sem ela: `playNarration` devolve
#                    null, a cena passa a correr pelo cronometro proprio
#                    (`narrTimer` contra NARRATION_END) e as legendas
#                    aparecem nos tempos escritos em js/i18n.js. O carro so
#                    freia quando o texto acaba, igual.
#
#                    Quando a gravacao nova existir, e so tirar o nome
#                    daqui — nao ha codigo para desfazer.
#
# roteiro-narracao.srt ... o texto da narracao, guardado para conferir a
#                    sincronia. E material de oficina, como o LEIA-ME: o
#                    jogo nao le esse arquivo em momento nenhum.
LISTA_NEGRA = {'musica-casa.mp3', 'narrator.mp3',
               'LEIA-ME.txt', 'roteiro-narracao.srt'}


def limpar():
    for pasta in (DESTINO, os.path.join(AQUI, 'build'), os.path.join(AQUI, 'dist')):
        if os.path.isdir(pasta):
            shutil.rmtree(pasta)


def ignorar(diretorio, nomes):
    fora = set()
    for n in nomes:
        if n in LISTA_NEGRA or n.startswith('.'):
            fora.add(n)
    return fora


# ---------------------------------------------------------------------------
# DE ONDE SAI O CODIGO: DO COMMIT, NAO DO DISCO
# ---------------------------------------------------------------------------
# ⚠ Isto existe por causa de um susto real. No dia em que esta demo foi
# empacotada, outra frente estava implementando o Capitulo 4 NA MESMA PASTA:
# `chapter4.js` e `levels-ch4.js` novos, mais quatro arquivos modificados, o
# ultimo salvo tres minutos depois do build comecar. O pacote pegou o estado
# anterior por SORTE, nao por decisao.
#
# Uma demo publica nao pode sair de uma arvore meio-editada. Ela sai de um
# COMMIT — um estado que alguem declarou pronto. `git archive` extrai
# exatamente os arquivos versionados daquele ponto, sem tocar na pasta de
# trabalho de quem esta programando ao lado.
#
# Para empacotar o que esta no disco mesmo assim (testar uma mudanca antes
# de commitar):  $env:TMC_SUJO = "1"
def fonte_do_jogo():
    if os.environ.get('TMC_SUJO') == '1':
        print('⚠ TMC_SUJO=1 — empacotando a pasta de trabalho, nao um commit.')
        return PROJETO

    git = shutil.which('git')
    if not git or not os.path.isdir(os.path.join(PROJETO, '.git')):
        print('⚠ o projeto nao e um repositorio git — empacotando o disco.')
        return PROJETO

    sujos = subprocess.run([git, '-C', PROJETO, 'status', '--porcelain'],
                           capture_output=True, text=True).stdout.strip()
    ref = subprocess.run([git, '-C', PROJETO, 'log', '-1', '--format=%h %s'],
                         capture_output=True, text=True).stdout.strip()

    fonte = os.path.join(AQUI, 'build', 'fonte')
    if os.path.isdir(fonte):
        shutil.rmtree(fonte)
    os.makedirs(fonte, exist_ok=True)
    pacote = os.path.join(AQUI, 'build', 'fonte.zip')
    r = subprocess.run([git, '-C', PROJETO, 'archive', '--format=zip',
                        '-o', pacote, 'HEAD'], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit('git archive falhou')
    with zipfile.ZipFile(pacote) as z:
        z.extractall(fonte)
    os.remove(pacote)

    print(f'fonte: commit {ref}')
    if sujos:
        n = len(sujos.splitlines())
        print(f'  ({n} arquivo(s) modificado(s) no disco FICARAM DE FORA — '
              f'use TMC_SUJO=1 para incluir)')
    return fonte


def copiar_jogo():
    origem_raiz = fonte_do_jogo()
    os.makedirs(DESTINO, exist_ok=True)
    total = 0
    for item in COPIAR:
        origem = os.path.join(origem_raiz, item)
        alvo = os.path.join(DESTINO, item)
        if os.path.isdir(origem):
            shutil.copytree(origem, alvo, ignore=ignorar)
        elif os.path.isfile(origem):
            shutil.copy2(origem, alvo)
        else:
            raise SystemExit(f'nao achei no projeto: {origem}')
    for raiz, _, arquivos in os.walk(DESTINO):
        for a in arquivos:
            total += os.path.getsize(os.path.join(raiz, a))
    return total


# ---------------------------------------------------------------------------
# A FICHA DO EXECUTAVEL
# ---------------------------------------------------------------------------
# Isto e o que aparece quando alguem clica com o botao direito no arquivo e
# vai em Propriedades > Detalhes. Sem isto, um jogo baixado mostra campos
# VAZIOS ali — e nada denuncia mais rapido que a coisa foi empacotada as
# pressas. Tambem e o texto que o Windows mostra no aviso do SmartScreen, no
# lugar de "Editor: Desconhecido... Programa: Desconhecido".
FICHA = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={VERSAO}, prodvers={VERSAO},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('041604B0', [
        StringStruct('CompanyName', {AUTOR!r}),
        StringStruct('FileDescription', 'The Midnight Call'),
        StringStruct('FileVersion', {'.'.join(map(str, VERSAO))!r}),
        StringStruct('InternalName', 'midnight-call'),
        StringStruct('LegalCopyright', {f'© 2026 {AUTOR}'!r}),
        StringStruct('OriginalFilename', {NOME + '.exe'!r}),
        StringStruct('ProductName', 'The Midnight Call'),
        StringStruct('ProductVersion', {VERSAO_TEXTO!r}),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])
  ]
)
"""


def escrever_ficha():
    """Grava o arquivo de versao que o PyInstaller carimba no .exe."""
    os.makedirs(os.path.join(AQUI, 'build'), exist_ok=True)
    caminho = os.path.join(AQUI, 'build', 'versao.txt')
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(FICHA)
    return caminho


# ---------------------------------------------------------------------------
# TIRAR AS FERRAMENTAS DE DENTRO DO JOGO
# ---------------------------------------------------------------------------
# O menu de titulo tem ARENA DE COMBATE e SALA DE TESTE — duas salas de
# desenvolvimento, uteis para quem faz o jogo e sem sentido nenhum para quem
# baixou uma demo. E o rodape diz "VERSAO DE TESTE 0.1 — FATIA JOGAVEL".
#
# Nada disso quebra o jogo; tudo isso denuncia que ele nao foi terminado. E
# uma demo e justamente uma promessa de que o jogo VAI ser terminado.
#
# ⚠ POR QUE PATCH NA COPIA, E NAO NO PROJETO: quando isto foi escrito, outra
# frente estava implementando o Capitulo 4 nos mesmos arquivos. Mexer no
# projeto seria atropelar o trabalho de alguem. A copia e nossa.
#
# ⚠ E POR QUE ELE EXPLODE SE NAO ACHAR: patch por texto envelhece mal. Se
# alguem renomear a entrada do menu, a substituicao falharia em silencio e a
# demo seguinte sairia com a sala de teste dentro. Errar alto e melhor.
POLIMENTOS = [
    (
        os.path.join('js', 'ui', 'menu.js'),
        "    list.push({ k: 'menu_combat_lab', a: 'combatlab' });\n"
        "    list.push({ k: 'menu_extras', a: 'lab' });\n",
        "    // (a arena de combate e a sala de teste sao ferramentas de\n"
        "    //  desenvolvimento; a demo nao as mostra — ver construir.py)\n",
    ),
    (
        os.path.join('js', 'i18n.js'),
        "  build_tag:      { pt: 'VERSAO DE TESTE 0.1 — FATIA JOGAVEL',\n"
        "                    en: 'TEST BUILD 0.1 — VERTICAL SLICE' },",
        "  build_tag:      { pt: 'DEMO 1.0 — CAPITULOS 1 A 3',\n"
        "                    en: 'DEMO 1.0 — CHAPTERS 1 TO 3' },",
    ),
]


def polir_para_demo():
    for relativo, de, para in POLIMENTOS:
        caminho = os.path.join(DESTINO, relativo)
        with open(caminho, 'r', encoding='utf-8') as f:
            texto = f.read()
        if de not in texto:
            raise SystemExit(
                f'POLIMENTO FALHOU em {relativo}.\n'
                f'Nao achei o trecho esperado:\n\n{de}\n\n'
                'O jogo mudou e este script nao acompanhou. Corrija a lista\n'
                'POLIMENTOS no construir.py — sem isto a demo sai com as\n'
                'ferramentas de desenvolvimento a mostra.'
            )
        with open(caminho, 'w', encoding='utf-8', newline='') as f:
            f.write(texto.replace(de, para))
        print(f'polido: {relativo}')


def pyinstaller(modo, ficha):
    """modo: 'onefile' ou 'onedir'."""
    saida = os.path.join(AQUI, 'dist', modo)
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--clean',
        f'--{modo}',
        '--windowed',                       # sem console preta atras do jogo
        '--name', NOME,
        '--icon', os.path.join(AQUI, 'icone.ico'),
        '--version-file', ficha,
        '--add-data', f'{DESTINO}{os.pathsep}jogo',
        '--distpath', saida,
        '--workpath', os.path.join(AQUI, 'build', modo),
        '--specpath', os.path.join(AQUI, 'build'),
        # O pywebview carrega o backend do Windows por nome, em tempo de
        # execucao. Sem isto o PyInstaller nao ve a dependencia, nao empacota
        # nada dela, e o exe abre direto no navegador achando que a maquina
        # nao tem WebView2.
        '--hidden-import', 'webview.platforms.winforms',
        '--hidden-import', 'clr_loader',
        '--hidden-import', 'pythonnet',
        os.path.join(AQUI, 'lancador.py'),
    ]
    print(f'\n=== PyInstaller ({modo}) ===')
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-4000:])
        print(r.stderr[-4000:])
        raise SystemExit(f'PyInstaller falhou no modo {modo}')
    return saida


def mb(n):
    return f'{n / (1024 * 1024):.1f} MB'


# ---------------------------------------------------------------------------
# A ARRUMACAO FINAL
# ---------------------------------------------------------------------------
# O PyInstaller cospe `dist/onefile/` e `dist/onedir/` — nomes de ferramenta,
# nao de produto. Ninguem manda para um amigo uma pasta chamada "onedir".
#
# Isto reorganiza a saida em duas coisas com cara de jogo, e joga o resto
# para dentro de `dist/_bruto/`, que e onde o lixo do empacotador mora:
#
#   dist/
#     The Midnight Call.exe                   <- o unico arquivo a enviar
#     The Midnight Call - Demo.zip            <- a versao em pasta, zipada
#     _bruto/                                 <- as saidas cruas
def arrumar(saida_onefile, saida_onedir):
    dist = os.path.join(AQUI, 'dist')
    bruto = os.path.join(dist, '_bruto')
    os.makedirs(bruto, exist_ok=True)

    # 1) o exe unico sobe para a raiz de dist/
    exe_final = os.path.join(dist, NOME + '.exe')
    shutil.copy2(os.path.join(saida_onefile, NOME + '.exe'), exe_final)

    # 2) a pasta vira "The Midnight Call - Demo", com o COMO JOGAR dentro
    pronta = os.path.join(dist, PASTA_DEMO)
    if os.path.isdir(pronta):
        shutil.rmtree(pronta)
    shutil.copytree(os.path.join(saida_onedir, NOME), pronta)
    manual = os.path.join(AQUI, 'COMO JOGAR.txt')
    if os.path.isfile(manual):
        shutil.copy2(manual, os.path.join(pronta, 'COMO JOGAR.txt'))

    # 3) o zip, com a pasta dentro (e nao os arquivos soltos, que
    #    explodiriam na area de trabalho de quem extrair sem olhar)
    zipe = os.path.join(dist, PASTA_DEMO)
    if os.path.isfile(zipe + '.zip'):
        os.remove(zipe + '.zip')
    shutil.make_archive(zipe, 'zip', root_dir=dist, base_dir=PASTA_DEMO)

    # 4) as saidas cruas do PyInstaller saem da frente
    for nome in ('onefile', 'onedir'):
        origem = os.path.join(dist, nome)
        destino = os.path.join(bruto, nome)
        if os.path.isdir(destino):
            shutil.rmtree(destino)
        if os.path.isdir(origem):
            shutil.move(origem, destino)

    return exe_final, pronta, zipe + '.zip'


if __name__ == '__main__':
    print(f'projeto: {PROJETO}')
    limpar()
    tamanho = copiar_jogo()
    print(f'jogo copiado: {mb(tamanho)}')
    polir_para_demo()

    ficha = escrever_ficha()
    um = pyinstaller('onefile', ficha)
    pasta = pyinstaller('onedir', ficha)
    exe, pronta, zipe = arrumar(um, pasta)

    print('\n--- pronto, e e isto que se manda ---')
    print(f'  {exe}   ({mb(os.path.getsize(exe))})')
    print(f'  {zipe}   ({mb(os.path.getsize(zipe))})')
    print(f'\n  (a pasta aberta fica em: {pronta})')
