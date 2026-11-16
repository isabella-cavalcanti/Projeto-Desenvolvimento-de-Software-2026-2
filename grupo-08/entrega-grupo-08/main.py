"""PharmIntegrated ERP — ponto de entrada.

Para abrir o sistema:   python main.py
Para rodar os testes:   python -m unittest -v testes
Só a API (sem janela):  python -m pharmintegrated.api
"""
from pharmintegrated.gui import executar

if __name__ == "__main__":
    executar()
