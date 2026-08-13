# verificar.py — prova que o jogo REALMENTE roda dentro da janela.
#
# Nao adianta o exe abrir: o que importa e o jogo terminar o boot, construir
# as fases e chegar na tela de "aperte uma tecla". Este script sobe o mesmo
# servidor e a mesma janela do lancador, espera o jogo carregar e pergunta
# ao proprio jogo como ele esta. Depois fecha tudo sozinho.
#
# USO:  python verificar.py            (testa a pasta jogo/ deste diretorio)

import json
import sys
import time

import lancador

PRAZO = 40.0          # o boot constroi 33 fases; numa maquina lenta demora
resultado = {}


def interrogar(janela):
    limite = time.time() + PRAZO
    estado = None
    while time.time() < limite:
        try:
            estado = janela.evaluate_js(
                'JSON.stringify({'
                '  temJogo: !!window.game,'
                '  estado: window.game ? window.game.state : null,'
                '  fases: window.game && window.game.levels'
                '         ? Object.keys(window.game.levels).length : 0,'
                '  crash: !document.getElementById("crash").hidden,'
                '  crashTexto: document.getElementById("crash-msg").textContent.slice(0,400),'
                '  boot: (document.getElementById("boot-msg")||{}).textContent'
                '})'
            )
            d = json.loads(estado)
            if d.get('crash'):
                break
            if d.get('temJogo') and d.get('estado') == 'waitkey':
                # chegou na tela inicial: agora confere audio e desenho
                d['audio'] = janela.evaluate_js(
                    'JSON.stringify({'
                    '  ctx: !!(window.AudioContext||window.webkitAudioContext),'
                    '  canvas: (function(){var c=document.getElementById("game");'
                    '           return c ? c.width + "x" + c.height : null;})()'
                    '})'
                )
                # ---- TELA CHEIA ----
                # A opcao existe no menu, mas o que importa e se A JANELA
                # ESTICA. Medido, nao suposto — ver `provar_tela_cheia`.
                d['noMenu'] = janela.evaluate_js(
                    '!!(window.game && window.game.menuOptions &&'
                    ' window.game.menuOptions.rows.some('
                    '   function(r){return r.type === "fullscreen";}))'
                )
                d['telaCheia'] = provar_tela_cheia(janela)
                # a dublagem tem que estar FORA do pacote, e a cutscene tem
                # que continuar de pe sem ela
                d['narracao'] = janela.evaluate_js(
                    'JSON.stringify({url: (window.game||{}).narrationUrl || null})'
                )
                break
        except Exception as e:
            d = {'erro': str(e)}
        time.sleep(0.4)
    resultado.update(d if isinstance(d, dict) else {'bruto': estado})
    janela.destroy()


def provar_tela_cheia(janela):
    """Prova que a JANELA muda de tamanho — nao que a API respondeu.

    🐛 A primeira versao desta verificacao perguntava `fullscreenEnabled` e
    se `requestFullscreen` existia. As duas coisas davam `true` e a tela
    cheia NAO funcionava: num WebView embutido a pagina pede e nada
    acontece. "A API existe" nunca foi "a janela estica".

    Entao agora a medida e a unica que importa: o tamanho da area util da
    pagina, antes e depois. Se ela nao crescer, esta quebrado.
    """
    medir = 'JSON.stringify([window.innerWidth, window.innerHeight])'
    instalado = janela.evaluate_js('window.__telaCheia ? "sim" : "nao"')

    # ⚠ A corrente inteira, e nao so o gancho: usa AS MESMAS funcoes que o
    # menu do jogo usa. Testar `window.__telaCheia.alternar()` direto
    # provaria que a ponte funciona e nao que o jogo chega nela.
    janela.evaluate_js(
        "import('/js/ui/panels.js').then(function(m){window.__pain = m;});")
    for _ in range(40):
        if janela.evaluate_js('!!window.__pain'):
            break
        time.sleep(0.1)
    if not janela.evaluate_js('!!window.__pain'):
        return {'erro': 'nao consegui carregar js/ui/panels.js'}

    alternar = 'window.__pain.alternarTelaCheia()'
    lendo = 'String(window.__pain.telaCheiaAtiva())'

    antes = json.loads(janela.evaluate_js(medir))
    diz_antes = janela.evaluate_js(lendo)
    janela.evaluate_js(alternar)
    time.sleep(1.8)
    dentro = json.loads(janela.evaluate_js(medir))
    diz_ligado = janela.evaluate_js(lendo)

    # ---- O ESC NAO PODE DESFAZER A TELA CHEIA ----
    #
    # Era a segunda reclamacao: no painel de opcoes o Esc VOLTA, entao nao
    # pode ser tambem o que sai da tela cheia — duas coisas na mesma tecla.
    #
    # No .exe isso se resolve sozinho, e da para PROVAR: a tela cheia aqui
    # e estado da JANELA NATIVA, nao da pagina. Com `fullscreenElement`
    # nulo, o navegador nao tem tela cheia nenhuma para o Esc desfazer — o
    # Esc chega no jogo limpo e so fecha o menu.
    dom = janela.evaluate_js('String(!!document.fullscreenElement)')

    janela.evaluate_js(alternar)
    time.sleep(1.8)
    depois = json.loads(janela.evaluate_js(medir))
    diz_desligado = janela.evaluate_js(lendo)
    return {
        'ganchoInstalado': instalado,
        'janela': antes,
        'emTelaCheia': dentro,
        'devolvida': depois,
        'esticou': dentro[0] > antes[0] and dentro[1] > antes[1],
        'voltou': depois == antes,
        'oJogoLe': f'{diz_antes} -> {diz_ligado} -> {diz_desligado}',
        'leituraCerta': (diz_antes == 'false' and diz_ligado == 'true'
                         and diz_desligado == 'false'),
        'domEmTelaCheia': dom,
        'escNaoDesfaz': dom == 'false',
    }


def main():
    raiz = lancador.pasta_do_jogo()
    url, servidor = lancador.subir_servidor(raiz)
    lancador.esperar_servidor(servidor.socket.getsockname()[1])
    print('servindo', raiz)
    print('em', url)

    import webview
    ponte = lancador.PonteDeTelaCheia()
    j = webview.create_window(lancador.TITULO, url, width=1280, height=720,
                              background_color='#000000', js_api=ponte)
    ponte.ligar(j)

    def rotina(janela):
        try:
            janela.events.loaded.wait(10)
        except Exception:
            pass
        try:
            janela.evaluate_js(lancador.SHIM)
        except Exception as e:
            resultado['shim'] = 'falhou: ' + str(e)
        interrogar(janela)

    webview.start(rotina, j)
    servidor.shutdown()

    print('\n--- resultado ---')
    for k, v in resultado.items():
        print(f'  {k}: {v}')

    fs = resultado.get('telaCheia') or {}
    ok = (resultado.get('estado') == 'waitkey'
          and resultado.get('fases', 0) > 0
          and not resultado.get('crash')
          and fs.get('esticou') is True
          and fs.get('voltou') is True
          and fs.get('leituraCerta') is True
          and fs.get('escNaoDesfaz') is True)
    print('\n' + ('O JOGO RODA NA JANELA, E A TELA CHEIA FUNCIONA.'
                  if ok else 'FALHOU.'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
