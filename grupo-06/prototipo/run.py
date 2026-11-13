"""Inicia o protótipo AutoFarma em http://localhost:5000

    python run.py            inicia (cria o banco e o cenário na primeira vez)
    python run.py --zerar    apaga o banco e recria o cenário de demonstração
"""
import os
import sys

from autofarma import create_app

BANCO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "autofarma.db")

if __name__ == "__main__":
    if "--zerar" in sys.argv and os.path.exists(BANCO):
        os.remove(BANCO)
        print("Banco apagado. Cenário de demonstração recriado.")
    create_app().run(debug=False, port=5000)
