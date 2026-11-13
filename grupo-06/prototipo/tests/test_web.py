"""Teste de ponta a ponta pela interface web: o roteiro da demonstração.

Recebimento -> ordem -> linha autônoma -> desvio -> decisão humana ->
quarentena -> liberação -> expedição -> recall.
"""
from datetime import date

import pytest

from autofarma import create_app
from autofarma.models import Lote, StatusLote, db
from autofarma.servicos import producao


@pytest.fixture
def cliente():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite://", "TESTING": True})
    producao.SimuladorDeSensores.anomalia_pendente = False
    with app.app_context():
        yield app.test_client()


def entrar(c, login):
    c.get("/logout")
    resposta = c.post("/login", data={"login": login, "senha": "1234"}, follow_redirects=True)
    assert resposta.status_code == 200
    return resposta


def lote():
    db.session.expire_all()
    return Lote.query.one()


def test_paginas_exigem_login(cliente):
    assert cliente.get("/").status_code == 302
    assert "/login" in cliente.get("/estoque").headers["Location"]


def test_roteiro_completo_da_demonstracao(cliente):
    c = cliente
    # 1. O Planejador cria a ordem; o sistema baixa os insumos e assume a linha.
    entrar(c, "planejador")
    pagina = c.post("/ordens", data={"formula": 1}, follow_redirects=True).get_data(as_text=True)
    assert "assumiu a condução do lote" in pagina
    assert lote().status == StatusLote.EM_PRODUCAO

    # 2. Dois ciclos normais; depois uma anomalia pausa a linha.
    c.post("/simulador/ciclo")
    c.post("/simulador/ciclo")
    c.post("/simulador/anomalia")
    c.post("/simulador/ciclo")
    assert lote().status == StatusLote.AGUARDANDO_INTERVENCAO
    assert "1 intervenção pendente" in c.get("/estoque").get_data(as_text=True)  # RNF06

    # 3. O Planejador não pode retomar; o Supervisor pode, com assinatura.
    dados = {"decisao": "RETOMAR", "justificativa": "Balança recalibrada.", "senha": "1234"}
    pagina = c.post("/intervencoes/1/resolver", data=dados, follow_redirects=True).get_data(as_text=True)
    assert "RN06" in pagina
    entrar(c, "supervisor")
    pagina = c.post("/intervencoes/1/resolver", data={**dados, "senha": "errada"},
                    follow_redirects=True).get_data(as_text=True)
    assert "RN07" in pagina
    c.post("/intervencoes/1/resolver", data=dados)
    assert lote().status == StatusLote.EM_PRODUCAO

    # 4. O sistema conduz o restante sozinho até a quarentena.
    for _ in range(30):
        c.post("/api/ciclo")
    assert lote().status == StatusLote.EM_QUARENTENA

    # 5. Tentar expedir antes da liberação é recusado (RN08).
    entrar(c, "almoxarife")
    pagina = c.post("/expedicao/lote/1", data={"cliente": 1, "quantidade": 100},
                    follow_redirects=True).get_data(as_text=True)
    assert "RN08" in pagina

    # 6. O Analista vê o desvio (RN09) e aprova; o estoque recebe o produto.
    entrar(c, "analista")
    pagina = c.get("/qualidade").get_data(as_text=True)
    assert "1 desvio(s) durante a fabricação" in pagina and "Balança recalibrada." in pagina
    c.post("/qualidade/lote/1", data={"resultado": "APROVADO", "senha": "1234",
                                      "observacao": "Análises conformes."})
    assert lote().status == StatusLote.APROVADO and lote().saldo == 8300

    # 7. Expedição para dois clientes.
    entrar(c, "almoxarife")
    c.post("/expedicao", data={"produto": 8, "cliente": 1, "quantidade": 1200})
    c.post("/expedicao", data={"produto": 8, "cliente": 2, "quantidade": 800})
    assert lote().saldo == 6300

    # 8. Recall a partir do insumo: o sistema acha clientes e bloqueia o saldo.
    entrar(c, "gerente")
    pagina = c.get(f"/rastreabilidade?insumo=LI-{date.today().year}-002").get_data(as_text=True)
    assert "Drogaria Central" in pagina and "Hospital Santa Clara" in pagina
    c.post("/recall", data={"insumo": 2, "senha": "1234",
                            "motivo": "Fornecedor comunicou contaminação."})
    assert lote().status == StatusLote.RECOLHIDO

    # 9. A trilha de auditoria continua íntegra.
    assert "Cadeia íntegra" in c.get("/auditoria").get_data(as_text=True)


def test_api_recebe_leitura_e_pausa_a_linha(cliente):
    entrar(cliente, "planejador")
    cliente.post("/ordens", data={"formula": 1})
    codigo = lote().codigo
    resposta = cliente.post("/api/leituras", json={"lote": codigo, "parametro": 1, "valor": 0.1})
    assert resposta.status_code == 201 and resposta.json["classificacao"] == "Conforme"
    resposta = cliente.post("/api/leituras", json={"lote": codigo, "parametro": 1, "valor": 0.9})
    assert resposta.json["status_do_lote"] == "Aguardando Intervenção"
    resposta = cliente.post("/api/leituras", json={"lote": codigo, "parametro": 1, "valor": 0.1})
    assert resposta.status_code == 409    # RN05: linha pausada não aceita seguir
