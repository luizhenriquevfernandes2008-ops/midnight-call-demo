# lancador.py — o que vira "Chamado da Meia-Noite.exe".
#
# POR QUE ISSO EXISTE
# O jogo e HTML + ES modules. Navegador nenhum carrega modulo por file://,
# entao nao da para simplesmente abrir o index.html num WebView e esperar
# funcionar. O truque de sempre do projeto (o JOGO_OFFLINE.html, que junta
# tudo num arquivo so) resolve isso para quem clica duas vezes num HTML —
# mas para um .exe da para fazer melhor: subir um servidor local de verdade,
# na propria maquina, e abrir uma janela nativa apontando para ele.
#
# O que este arquivo faz, em ordem:
#
#   1. acha a pasta do jogo (dentro do proprio exe, ou ao lado do script);
#   2. sobe um servidor HTTP em 127.0.0.1, numa porta livre sorteada pelo
#      sistema — nada fica exposto para fora da maquina;
#   3. abre uma janela nativa (WebView2, o motor do Edge, que ja vem no
#      Windows 10/11) apontando para esse endereco;
#   4. se a janela nativa nao existir naquela maquina, cai no navegador
#      padrao e avisa o jogador do que aconteceu.
#
# A REGRA DO PROJETO CONTINUA VALENDO: nada disso pode ser obrigatorio para
# o jogo rodar. O index.html com o servidor de desenvolvimento e o
# JOGO_OFFLINE.html continuam funcionando exatamente como antes — este
# arquivo e uma casca por fora, nao uma dependencia.

import os
import socket
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

TITULO = 'The Midnight Call'
LARGURA, ALTURA = 1280, 720      # 16:9, o mesmo formato do canvas (480x270)
MINIMO = (640, 360)


# ---------------------------------------------------------------------------
# TELA CHEIA — por que isto precisa existir do lado de fora do jogo
# ---------------------------------------------------------------------------
# 🐛 O jogo tem a opcao no menu, e ela chamava `requestFullscreen()` do
# navegador. Dentro de um WebView EMBUTIDO isso nao devolve erro, nao
# rejeita a promessa e NAO ACONTECE NADA — a janela continua do mesmo
# tamanho. Testado com clique de verdade.
#
# O motivo: numa janela embutida a pagina nao manda no tamanho dela. Ela
# avisa o programa hospedeiro de que quer tela cheia, e e o hospedeiro que
# tem que esticar. Se ninguem escuta do lado de fora, o pedido morre em
# silencio. Aqui, o hospedeiro somos nos.
#
# O contrato e do JOGO, nao deste arquivo: ele procura por
# `window.__telaCheia = { ativa(), alternar() }` e, se nao achar, usa a API
# do navegador. Ou seja, o jogo continua funcionando sozinho no navegador,
# no servidor de dev e no JOGO_OFFLINE.html — este arquivo so preenche o
# gancho quando existe uma janela de verdade para esticar.
class PonteDeTelaCheia:
    """O objeto que o JavaScript enxerga como `window.pywebview.api`.

    ⚠ OS ATRIBUTOS SAO PRIVADOS (`_`) DE PROPOSITO, E ISSO NAO E ESTILO.
    O pywebview varre os atributos PUBLICOS desta classe para montar o
    espelho dela em JavaScript. Guardando a janela em `self.janela`, ele
    tentava serializar o objeto nativo do Windows inteiro e entrava em
    recursao infinita — o erro era um `AccessibilityObject.Bounds.Empty`
    repetido umas trezentas vezes, terminando em "maximum recursion depth
    exceeded", e a janela nem chegava a abrir.

    Com o underscore, so os metodos atravessam a ponte.
    """

    def __init__(self):
        self._janela = None
        self._cheia = False

    def ligar(self, janela):
        self._janela = janela

    def alternar_tela_cheia(self):
        if self._janela is None:
            return self._cheia
        self._janela.toggle_fullscreen()
        self._cheia = not self._cheia
        return self._cheia

    def tela_cheia_ativa(self):
        return self._cheia


# O atalho instalado na pagina. Ele guarda o estado numa variavel local
# porque o desenho do menu pergunta isso A CADA QUADRO, e a chamada para o
# Python e assincrona (devolve promessa) — perguntar do outro lado 60 vezes
# por segundo travaria o jogo.
SHIM = """
(function () {
  if (window.__telaCheia) return 'ja instalado';
  window.__telaCheia = {
    _ativa: false,
    ativa: function () { return this._ativa; },
    alternar: function () {
      var eu = this;
      if (!window.pywebview || !window.pywebview.api) return;
      // O estado vira o que o Python DISSER que virou, e nao o que a
      // pagina achou que ia virar. Se a janela recusar, o menu nao mente.
      window.pywebview.api.alternar_tela_cheia().then(function (v) {
        eu._ativa = !!v;
      });
    }
  };
  return 'instalado';
})()
"""


def pasta_do_jogo():
    """Onde estao index.html, js/ e css/.

    Dentro do .exe o PyInstaller descompacta tudo numa pasta temporaria e
    guarda o caminho em sys._MEIPASS. Rodando como script solto, o jogo esta
    na subpasta `jogo/` ao lado deste arquivo.
    """
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    for tentativa in (os.path.join(base, 'jogo'), base):
        if os.path.isfile(os.path.join(tentativa, 'index.html')):
            return tentativa
    raise SystemExit('Nao encontrei o index.html do jogo dentro do pacote.')


class Silencioso(SimpleHTTPRequestHandler):
    """Servidor local. Duas diferencas para o padrao:

    1. NAO ESCREVE NADA no console. O exe roda sem console; um `print` num
       processo sem stdout levanta excecao no Windows e derrubaria o
       servidor no meio de uma partida.
    2. Manda o navegador nao guardar nada em cache. O jogo e servido da
       pasta temporaria do exe, que muda de lugar a cada execucao — cache
       aqui so serviria para misturar versoes.
    """

    # ⚠ `text/javascript` para .js e OBRIGATORIO. Se o servidor devolver
    # outro tipo, o WebView recusa o modulo por checagem de MIME e a tela
    # fica no "carregando..." para sempre, sem erro nenhum visivel.
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map)
    extensions_map.update({
        '.js': 'text/javascript',
        '.mjs': 'text/javascript',
        '.css': 'text/css',
        '.html': 'text/html',
        '.json': 'application/json',
        '.mp3': 'audio/mpeg',
        '.ogg': 'audio/ogg',
        '.wav': 'audio/wav',
        '.m4a': 'audio/mp4',
        '.srt': 'text/plain',
    })

    def log_message(self, *a, **k):
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def subir_servidor(raiz):
    """Sobe o servidor numa porta livre e devolve (endereco, servidor).

    Porta 0 quer dizer "sistema, escolhe uma que esteja livre". Fixar um
    numero daria conflito na maquina de quem ja tem alguma coisa nele — e
    numa demo que outra pessoa vai rodar isso nao pode acontecer.
    """
    handler = partial(Silencioso, directory=raiz)
    servidor = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    servidor.daemon_threads = True
    porta = servidor.socket.getsockname()[1]
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{porta}/index.html', servidor


def esperar_servidor(porta, limite=5.0):
    """So abre a janela depois que o servidor responde de verdade.

    Sem isso, numa maquina lenta, a janela abre antes e mostra a tela de
    "nao consegui conectar" — que e um primeiro contato pessimo com o jogo.
    """
    import time
    fim = time.time() + limite
    while time.time() < fim:
        try:
            with socket.create_connection(('127.0.0.1', porta), 0.25):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def caixa(texto, botoes=0x40):
    """Uma caixa de aviso do proprio Windows. Sem console, e o unico jeito
    de falar com quem esta jogando."""
    try:
        import ctypes
        return ctypes.windll.user32.MessageBoxW(0, texto, TITULO, botoes)
    except Exception:
        return None


def abrir_no_navegador(url, motivo):
    """Plano B: o navegador padrao.

    A janela nativa depende do WebView2, que vem no Windows 10 e 11 mas pode
    faltar numa maquina antiga ou capada. Em vez de morrer com um erro, o
    jogo abre no navegador — e continua sendo o jogo inteiro, pelo mesmo
    servidor local.

    ⚠ E ELE PRECISA TER COMO ACABAR. A primeira versao abria o navegador e
    dava `input()` num programa SEM CONSOLE: a leitura falhava na hora, caia
    num `Event().wait()` e o processo ficava vivo PARA SEMPRE. Quem fechasse
    a aba ficava com um jogo rodando invisivel, sem icone, sem janela, so
    matavel pelo Gerenciador de Tarefas. Numa maquina que ja estava sem
    WebView2, ou seja, no pior dia possivel do jogador.
    """
    caixa(
        'Este computador nao tem o componente que o jogo usa para abrir a\n'
        'janela propria, entao ele vai abrir no seu NAVEGADOR.\n\n'
        'O jogo e exatamente o mesmo, e roda igual.\n\n'
        'Se quiser a janela propria, instale o "Microsoft Edge WebView2\n'
        'Runtime" — e gratuito, e da Microsoft.\n\n'
        f'(detalhe tecnico: {motivo})'
    )
    webbrowser.open(url)
    # A caixa abaixo E o botao de sair. Ela trava aqui ate o jogador clicar,
    # segurando o servidor de pe enquanto ele joga; quando ele clica, a
    # funcao retorna, o servidor cai e o processo termina de verdade.
    caixa(
        'O jogo esta aberto no seu navegador.\n\n'
        'DEIXE ESTA JANELA ABERTA enquanto joga — e ela que mantem o jogo\n'
        'no ar.\n\n'
        'Quando terminar, clique em OK aqui para fechar tudo.'
    )


def main():
    raiz = pasta_do_jogo()
    url, servidor = subir_servidor(raiz)
    esperar_servidor(servidor.socket.getsockname()[1])

    # ⚠ O CAMINHO DO NAVEGADOR PRECISA SER TESTAVEL. Ele so acontece numa
    # maquina sem WebView2, que nao e esta — e caminho de erro que ninguem
    # consegue exercitar e caminho que ninguem sabe se funciona. Com
    # TMC_SEM_JANELA=1 da para forcar o plano B e ver o que o jogador veria.
    if os.environ.get('TMC_SEM_JANELA') == '1':
        abrir_no_navegador(url, 'forcado por TMC_SEM_JANELA=1')
        return

    try:
        import webview
    except Exception as e:
        abrir_no_navegador(url, f'pywebview nao carregou ({e})')
        return

    try:
        ponte = PonteDeTelaCheia()
        janela = webview.create_window(
            TITULO, url,
            width=LARGURA, height=ALTURA,
            min_size=MINIMO,
            background_color='#000000',
            resizable=True,
            text_select=False,
            js_api=ponte,
        )
        ponte.ligar(janela)

        def preparar(j):
            # ⚠ Isto tem que rodar DEPOIS de a pagina carregar, senao o
            # `window.__telaCheia` e instalado num documento que ainda vai
            # ser trocado — e some junto. O `loaded` e quem garante a ordem.
            try:
                j.events.loaded.wait(10)
            except Exception:
                pass
            try:
                j.evaluate_js(SHIM)
            except Exception:
                pass
            # O menu de contexto do WebView (recarregar, imprimir, "salvar
            # imagem como") nao pertence a um jogo. Some com ele.
            try:
                j.evaluate_js(
                    "document.addEventListener('contextmenu',"
                    "function(e){e.preventDefault();});"
                )
            except Exception:
                pass

        webview.start(preparar, janela)
    except Exception as e:
        abrir_no_navegador(url, f'a janela nativa falhou ({e})')
        return
    finally:
        try:
            servidor.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
