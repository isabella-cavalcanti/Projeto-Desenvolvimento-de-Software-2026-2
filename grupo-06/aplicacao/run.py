"""Inicia o AutoFarma em http://localhost:5000

    python run.py            inicia (na primeira vez cria o banco)
    python run.py --zerar    apaga o banco local e recria o cenário de demonstração

Por padrão roda em modo demonstração (AUTOFARMA_DEMO=1): carrega o cenário de
estudo e mostra o simulador no painel. Para uso real, veja "Implantação" no README.
"""
import os
import sys

from autofarma import create_app

BANCO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "autofarma.db")

if __name__ == "__main__":
    if "--zerar" in sys.argv and os.path.exists(BANCO):
        os.remove(BANCO)
        print("Banco apagado. O cenário de demonstração será recriado.")
    app = create_app()
    try:
        from waitress import serve          # servidor de produção, funciona no Windows
        print("AutoFarma em http://localhost:5000")
        serve(app, host="0.0.0.0", port=5000, threads=8)
    except ImportError:
        app.run(debug=False, port=5000, threaded=True)
