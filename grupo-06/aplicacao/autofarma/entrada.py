"""Validação dos dados que chegam de formulários e da API.

Todo valor externo passa por aqui antes de chegar à camada de negócio.
Um dado inválido vira uma recusa explicada ao usuário, nunca um erro interno.
"""
import math
import threading
from datetime import date

from .servicos.auditoria import RegraDeNegocio

# A aplicação roda em um único processo com várias threads. Esta trava faz
# com que as operações que alteram dados ocorram uma de cada vez, evitando
# que duas baixas simultâneas do mesmo saldo se sobreponham.
trava = threading.RLock()


def numero(bruto, campo, minimo=None, maximo=1e12, padrao=None):
    """Converte texto em número finito; aceita vírgula ou ponto decimal."""
    texto = str(bruto if bruto is not None else "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    if texto == "":
        if padrao is not None:
            return padrao
        raise RegraDeNegocio(f"Informe um número no campo {campo}.")
    try:
        valor = float(texto)
    except ValueError:
        raise RegraDeNegocio(f"O campo {campo} deve ser um número.")
    if not math.isfinite(valor):
        raise RegraDeNegocio(f"O campo {campo} deve ser um número válido.")
    if minimo is not None and valor < minimo:
        raise RegraDeNegocio(f"O campo {campo} não pode ser menor que {minimo:g}.")
    if abs(valor) > maximo:
        raise RegraDeNegocio(f"O valor do campo {campo} é grande demais.")
    return valor


def inteiro(bruto, campo, minimo=None, maximo=1000000):
    valor = numero(bruto, campo, minimo, maximo)
    if valor != int(valor):
        raise RegraDeNegocio(f"O campo {campo} deve ser um número inteiro.")
    return int(valor)


def data(bruto, campo):
    try:
        return date.fromisoformat(str(bruto or "").strip())
    except ValueError:
        raise RegraDeNegocio(f"Informe uma data válida no campo {campo}.")


def opcao(enumeracao, bruto, campo):
    try:
        return enumeracao[str(bruto or "")]
    except KeyError:
        raise RegraDeNegocio(f"Opção inválida no campo {campo}.")


def texto(bruto, campo, maximo=200):
    valor = str(bruto or "").strip()
    if len(valor) > maximo:
        raise RegraDeNegocio(f"O campo {campo} aceita no máximo {maximo} caracteres.")
    return valor
