"""Simulador da linha: faz o papel do sistema supervisório da fábrica.

Roda como um processo separado e conversa com o AutoFarma somente pela API,
como um supervisório real faria:

    python simulador.py                     envia leituras normais a cada 2 s
    python simulador.py --anomalia 5        a 5ª leitura sai fora de especificação
    python simulador.py --url http://servidor:8000 --chave MINHA_CHAVE
"""
import argparse
import json
import random
import time
import urllib.error
import urllib.request


def chamar(url, chave, dados=None):
    requisicao = urllib.request.Request(
        url, data=json.dumps(dados).encode() if dados is not None else None,
        headers={"X-API-Key": chave, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(requisicao, timeout=10) as resposta:
            return resposta.status, json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read() or b"{}")


def main():
    opcoes = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    opcoes.add_argument("--url", default="http://localhost:5000")
    opcoes.add_argument("--chave", default="chave-demo")
    opcoes.add_argument("--intervalo", type=float, default=2.0)
    opcoes.add_argument("--anomalia", type=int, default=0,
                        help="número da leitura que sairá fora de especificação")
    opcoes = opcoes.parse_args()
    enviadas = 0
    print(f"Simulador ligado em {opcoes.url}. Ctrl+C para encerrar.")
    while True:
        status, corpo = chamar(f"{opcoes.url}/api/linha", opcoes.chave)
        if status != 200:
            print("Falha ao consultar a linha:", status, corpo)
        elif not corpo["lotes"]:
            print("Nenhum lote em produção (linha parada ou aguardando decisão).")
        for lote in corpo.get("lotes", []) if status == 200 else []:
            for p in lote["parametros"]:
                enviadas += 1
                centro, folga = (p["alerta_min"] + p["alerta_max"]) / 2, (p["alerta_max"] - p["alerta_min"]) / 2
                valor = round(centro + random.uniform(-0.8, 0.8) * folga, 2)
                if enviadas == opcoes.anomalia:
                    valor = round(p["espec_max"] + (p["espec_max"] - p["espec_min"]) * 0.15, 2)
                status_envio, resposta = chamar(f"{opcoes.url}/api/leituras", opcoes.chave,
                                                {"lote": lote["lote"], "parametro": p["id"], "valor": valor})
                print(f'{lote["lote"]} | {lote["etapa"]:<22} | {p["nome"]:<34} {valor:>8} {p["unidade"]:<4} '
                      f'-> {resposta.get("classificacao") or resposta.get("erro")} ({status_envio})')
                if status_envio != 201:
                    break
        time.sleep(opcoes.intervalo)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSimulador encerrado.")
