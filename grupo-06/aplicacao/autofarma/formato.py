"""Formatação de números no padrão brasileiro (1.234,5)."""


def numero(valor):
    texto = f"{valor:,.3f}".rstrip("0").rstrip(".")
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")
