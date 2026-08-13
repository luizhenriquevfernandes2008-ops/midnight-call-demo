# fazer_icone.py — gera icone.ico sem depender de nada instalado.
#
# Nao ha Pillow nesta maquina e nao vale a pena exigir uma dependencia so
# para desenhar um quadrado. Um .ico pode conter PNGs inteiros dentro dele,
# e PNG e um formato simples o bastante para escrever na mao: cabecalho,
# blocos de pixels crus comprimidos com zlib (que vem na biblioteca padrao)
# e um CRC por bloco.
#
# O DESENHO: um relogio marcando meia-noite, os dois ponteiros de pe, no
# mesmo laranja de brasa do fogo do Capitulo 3 sobre o preto do jogo. Mesma
# regra do resto da arte: retangulos, sem suavizacao, sem gradiente.

import os
import struct
import zlib

TAM = 256
FUNDO = (10, 11, 13)
ARO = (200, 92, 42)
ARO_ESCURO = (120, 52, 24)
PONTEIRO = (232, 226, 214)
MARCA = (90, 78, 66)


def tela(cor):
    return [[cor for _ in range(TAM)] for _ in range(TAM)]


def disco(px, cx, cy, raio_ext, raio_int, cor):
    """Anel preenchido. Sem antialias de proposito — o jogo inteiro e assim."""
    re2, ri2 = raio_ext * raio_ext, raio_int * raio_int
    for y in range(max(0, cy - raio_ext), min(TAM, cy + raio_ext + 1)):
        dy2 = (y - cy) ** 2
        for x in range(max(0, cx - raio_ext), min(TAM, cx + raio_ext + 1)):
            d2 = (x - cx) ** 2 + dy2
            if ri2 <= d2 <= re2:
                px[y][x] = cor


def barra(px, x0, y0, w, h, cor):
    for y in range(max(0, y0), min(TAM, y0 + h)):
        for x in range(max(0, x0), min(TAM, x0 + w)):
            px[y][x] = cor


def png(px):
    cru = b''.join(
        b'\x00' + b''.join(struct.pack('BBB', *px[y][x]) for x in range(TAM))
        for y in range(TAM)
    )

    def bloco(tipo, dados):
        c = tipo + dados
        return struct.pack('>I', len(dados)) + c + struct.pack('>I', zlib.crc32(c))

    return (
        b'\x89PNG\r\n\x1a\n'
        + bloco(b'IHDR', struct.pack('>IIBBBBB', TAM, TAM, 8, 2, 0, 0, 0))
        + bloco(b'IDAT', zlib.compress(cru, 9))
        + bloco(b'IEND', b'')
    )


def ico(dados_png):
    # ICONDIR + uma ICONDIRENTRY. Largura/altura 0 significa 256.
    cabecalho = struct.pack('<HHH', 0, 1, 1)
    entrada = struct.pack('<BBBBHHII', 0, 0, 0, 0, 1, 32, len(dados_png), 22)
    return cabecalho + entrada + dados_png


def desenhar():
    px = tela(FUNDO)
    cx = cy = TAM // 2
    disco(px, cx, cy, 112, 96, ARO_ESCURO)
    disco(px, cx, cy, 108, 98, ARO)
    # as marcas das quatro horas cardeais
    barra(px, cx - 4, cy - 92, 8, 20, MARCA)
    barra(px, cx - 4, cy + 72, 8, 20, MARCA)
    barra(px, cx - 92, cy - 4, 20, 8, MARCA)
    barra(px, cx + 72, cy - 4, 20, 8, MARCA)
    # MEIA-NOITE: os dois ponteiros em pe, um sobre o outro
    barra(px, cx - 5, cy - 74, 10, 76, PONTEIRO)   # minutos
    barra(px, cx - 5, cy - 52, 10, 54, PONTEIRO)   # horas
    barra(px, cx - 8, cy - 8, 16, 16, PONTEIRO)    # eixo
    return px


if __name__ == '__main__':
    saida = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icone.ico')
    with open(saida, 'wb') as f:
        f.write(ico(png(desenhar())))
    print('icone gerado:', saida, os.path.getsize(saida), 'bytes')
