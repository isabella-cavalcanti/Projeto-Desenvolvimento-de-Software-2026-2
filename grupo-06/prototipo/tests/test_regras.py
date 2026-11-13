"""Testes das regras de negócio. Cada teste cita a regra que verifica (RNF10).

Executar:  python -m pytest -v
"""
from datetime import date, datetime, timedelta

import pytest

from autofarma import create_app
from autofarma.models import (Classificacao, Cliente, Decisao, Formula, Item, Lote,
                              LoteInsumo, RegistroAuditoria, Resultado,
                              StatusEstoque, StatusIntervencao, StatusLote, Usuario, db)
from autofarma.seed import SENHA_DEMO
from autofarma.servicos import auditoria, estoque, producao, qualidade
from autofarma.servicos.auditoria import RegraDeNegocio


@pytest.fixture
def app():
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite://", "TESTING": True})
    with app.app_context():
        producao.SimuladorDeSensores.anomalia_pendente = False
        yield app


def usuario(login):
    return Usuario.query.filter_by(login=login).one()


def insumo(lote_fornecedor):
    return LoteInsumo.query.filter_by(lote_fornecedor=lote_fornecedor).one()


def nova_ordem():
    ordem = producao.criar_ordem(usuario("planejador"), Formula.query.one())
    producao.iniciar_ordem(ordem.lote)
    db.session.commit()
    return ordem.lote


def fabricar_ate_quarentena(lote):
    simulador = producao.SimuladorDeSensores(semente=1)
    for _ in range(40):
        if lote.status != StatusLote.EM_PRODUCAO:
            break
        producao.executar_ciclo(simulador)
    assert lote.status == StatusLote.EM_QUARENTENA
    return lote


def lote_aprovado():
    lote = fabricar_ate_quarentena(nova_ordem())
    qualidade.avaliar_lote(usuario("analista"), lote, Resultado.APROVADO,
                           SENHA_DEMO, "Análises dentro da especificação.")
    db.session.commit()
    return lote


# --------------------------------------------------------------------- estoque
def test_rn01_insumo_recebido_entra_em_quarentena_e_nao_e_consumido(app):
    paracetamol = Item.query.filter_by(codigo="MP-001").one()
    novo = estoque.receber_insumo(usuario("almoxarife"), paracetamol, "Química Vale",
                                  "QV-TESTE", date.today() + timedelta(days=5), 500)
    assert novo.status == StatusEstoque.QUARENTENA
    # Mesmo vencendo antes de todos, não aparece entre os lotes consumíveis.
    assert novo not in estoque.lotes_disponiveis_fefo(paracetamol)


def test_rn02_consumo_segue_fefo_e_rn10_registra_genealogia(app):
    lote = nova_ordem()
    consumo = {c.lote_insumo.lote_fornecedor: c.quantidade for c in lote.consumos}
    assert consumo["QV-8841"] == 60                    # vence primeiro: esgotado
    assert consumo["QV-9012"] == pytest.approx(23.3)   # completa os 83,3 kg
    assert "AT-2207" not in consumo                    # em quarentena (RN01)
    assert insumo("QV-8841").saldo == 0


def test_rn03_lote_vencido_e_bloqueado_automaticamente(app):
    vencido = insumo("AS-0391")
    assert vencido.status == StatusEstoque.APROVADO
    producao.executar_ciclo()
    assert vencido.status == StatusEstoque.VENCIDO
    assert vencido not in estoque.lotes_disponiveis_fefo(vencido.item)


def test_rf04_falta_de_insumo_suspende_e_o_sistema_retoma_sozinho(app):
    nova_ordem()                      # consome 0,7 kg do único 1,0 kg de estearato aprovado
    segundo = nova_ordem()
    assert segundo.status == StatusLote.AGUARDANDO_MATERIAL
    assert "Estearato" in segundo.intervencoes[0].motivo
    assert not segundo.consumos       # RNF07: nada foi baixado pela metade
    qualidade.avaliar_insumo(usuario("analista"), insumo("QV-9050"), Resultado.APROVADO,
                             SENHA_DEMO, "Laudo conforme.")
    producao.executar_ciclo(producao.SimuladorDeSensores(semente=1))
    assert segundo.status == StatusLote.EM_PRODUCAO
    assert segundo.intervencoes[0].resolvida_por == auditoria.SISTEMA


# -------------------------------------------------------------------- produção
def test_rn04_etapas_seguem_a_sequencia_do_roteiro(app):
    lote = nova_ordem()
    assert lote.etapa_atual.etapa_padrao.nome == "Pesagem"
    parametro_da_mistura = lote.etapas[1].etapa_padrao.parametros[0]
    with pytest.raises(RegraDeNegocio, match="RN04"):
        producao.processar_leitura(lote, parametro_da_mistura, 20)


def test_rf07_leitura_em_alerta_nao_para_a_linha(app):
    lote = nova_ordem()
    parametro = lote.etapa_atual.etapa_padrao.parametros[0]   # desvio de pesagem
    leitura = producao.processar_leitura(lote, parametro, 0.40)
    assert leitura.classificacao == Classificacao.ALERTA
    assert lote.status == StatusLote.EM_PRODUCAO


def test_rn05_leitura_fora_de_especificacao_pausa_e_o_sistema_nao_retoma(app):
    lote = nova_ordem()
    parametro = lote.etapa_atual.etapa_padrao.parametros[0]
    producao.processar_leitura(lote, parametro, 0.90)
    assert lote.status == StatusLote.AGUARDANDO_INTERVENCAO
    ciclos = lote.etapa_atual.ciclos
    for _ in range(5):                                         # o motor segue rodando
        producao.executar_ciclo(producao.SimuladorDeSensores(semente=1))
    assert lote.status == StatusLote.AGUARDANDO_INTERVENCAO   # e nada avança
    assert lote.etapa_atual.ciclos == ciclos


def test_rn06_e_rn07_so_o_supervisor_retoma_com_assinatura(app):
    lote = nova_ordem()
    producao.processar_leitura(lote, lote.etapa_atual.etapa_padrao.parametros[0], 0.90)
    intervencao = lote.intervencoes[-1]
    with pytest.raises(RegraDeNegocio, match="RN06"):          # perfil errado
        producao.resolver_intervencao(usuario("almoxarife"), intervencao,
                                      Decisao.RETOMAR, SENHA_DEMO, "ok")
    with pytest.raises(RegraDeNegocio, match="RN07"):          # senha errada
        producao.resolver_intervencao(usuario("supervisor"), intervencao,
                                      Decisao.RETOMAR, "errada", "ok")
    with pytest.raises(RegraDeNegocio, match="RN07"):          # sem justificativa
        producao.resolver_intervencao(usuario("supervisor"), intervencao,
                                      Decisao.RETOMAR, SENHA_DEMO, "  ")
    producao.resolver_intervencao(usuario("supervisor"), intervencao, Decisao.RETOMAR,
                                  SENHA_DEMO, "Balança recalibrada; pesagem conferida.")
    assert lote.status == StatusLote.EM_PRODUCAO


def test_rf09_segregar_reprova_o_lote(app):
    lote = nova_ordem()
    producao.processar_leitura(lote, lote.etapa_atual.etapa_padrao.parametros[0], 0.90)
    producao.resolver_intervencao(usuario("supervisor"), lote.intervencoes[-1],
                                  Decisao.SEGREGAR, SENHA_DEMO, "Erro de pesagem do ativo.")
    assert lote.status == StatusLote.REPROVADO


def test_rn14_intervencao_sem_resposta_e_escalonada(app):
    lote = nova_ordem()
    producao.processar_leitura(lote, lote.etapa_atual.etapa_padrao.parametros[0], 0.90)
    assert producao.verificar_prazos(datetime.now() + timedelta(minutes=14)) == []
    producao.verificar_prazos(datetime.now() + timedelta(minutes=16))
    assert lote.intervencoes[-1].status == StatusIntervencao.ESCALONADA


def test_rf11_lote_concluido_vai_para_quarentena_sem_saldo_disponivel(app):
    lote = fabricar_ate_quarentena(nova_ordem())
    assert all(e.status.name == "CONCLUIDA" for e in lote.etapas)
    assert lote.saldo == 0            # só entra no estoque depois do CQ


# ------------------------------------------------------------------- qualidade
def test_rn08_lote_em_quarentena_nao_pode_ser_expedido(app):
    lote = fabricar_ate_quarentena(nova_ordem())
    with pytest.raises(RegraDeNegocio, match="RN08"):
        estoque.expedir_lote(usuario("almoxarife"), lote, Cliente.query.first(), 100)
    with pytest.raises(RegraDeNegocio, match="RN08"):
        estoque.expedir(usuario("almoxarife"), lote.produto, Cliente.query.first(), 100)


def test_rn13_producao_nao_aprova_lote(app):
    lote = fabricar_ate_quarentena(nova_ordem())
    with pytest.raises(RegraDeNegocio, match="RN06"):
        qualidade.avaliar_lote(usuario("supervisor"), lote, Resultado.APROVADO,
                               SENHA_DEMO, "ok")
    assert lote.status == StatusLote.EM_QUARENTENA


def test_rf21_aprovacao_da_entrada_automatica_no_estoque(app):
    lote = lote_aprovado()
    assert lote.status == StatusLote.APROVADO
    assert lote.saldo == 8300
    estoque.expedir(usuario("almoxarife"), lote.produto, Cliente.query.first(), 300)
    assert lote.saldo == 8000


def test_rn11_recall_bloqueia_saldos_e_lista_clientes(app):
    lote = lote_aprovado()
    drogaria = Cliente.query.filter_by(nome="Drogaria Central").one()
    hospital = Cliente.query.filter_by(nome="Hospital Santa Clara").one()
    estoque.expedir(usuario("almoxarife"), lote.produto, drogaria, 1000)
    estoque.expedir(usuario("almoxarife"), lote.produto, hospital, 500)
    with pytest.raises(RegraDeNegocio, match="RN06"):          # só a gerência inicia
        qualidade.iniciar_recall(usuario("analista"), SENHA_DEMO, "x",
                                 lote_insumo=insumo("QV-9012"))
    recall, rastro = qualidade.iniciar_recall(
        usuario("gerente"), SENHA_DEMO, "Fornecedor comunicou contaminação do lote.",
        lote_insumo=insumo("QV-9012"))
    assert [l.codigo for l in recall.lotes_afetados] == [lote.codigo]
    assert {c.nome for c in rastro["clientes"]} == {"Drogaria Central", "Hospital Santa Clara"}
    assert lote.status == StatusLote.RECOLHIDO
    assert insumo("QV-9012").status == StatusEstoque.BLOQUEADO
    with pytest.raises(RegraDeNegocio, match="RN08"):          # o saldo ficou preso
        estoque.expedir_lote(usuario("almoxarife"), lote, drogaria, 10)


# ------------------------------------------------------------------- auditoria
def test_rn12_trilha_de_auditoria_e_imutavel_e_detecta_adulteracao(app):
    nova_ordem()
    assert auditoria.verificar_cadeia() == (True, None)
    registro = RegistroAuditoria.query.filter_by(acao="INICIAR_PRODUCAO").one()
    registro.detalhe = "adulterado"
    with pytest.raises(PermissionError, match="RN12"):         # a aplicação recusa
        db.session.commit()
    db.session.rollback()
    # Adulteração feita direto no banco, por fora da aplicação, é detectada.
    db.session.execute(db.text("UPDATE registro_auditoria SET detalhe='x' WHERE id=:i"),
                       {"i": registro.id})
    db.session.commit()
    db.session.expire_all()
    assert auditoria.verificar_cadeia() == (False, registro.id)


def test_rf25_decisoes_automaticas_sao_registradas_como_sistema(app):
    lote = nova_ordem()
    producao.processar_leitura(lote, lote.etapa_atual.etapa_padrao.parametros[0], 0.90)
    pausa = RegistroAuditoria.query.filter_by(acao="PAUSAR_LINHA").one()
    assert pausa.autor == auditoria.SISTEMA
    criacao = RegistroAuditoria.query.filter_by(acao="CRIAR_ORDEM").one()
    assert criacao.autor == "planejador"


def test_rf17_alerta_de_estoque_minimo_apos_o_consumo(app):
    from autofarma.models import Alerta
    nova_ordem()                      # sobra 0,3 kg de estearato; o mínimo é 1 kg
    alerta = Alerta.query.filter_by(tipo="ESTOQUE_MINIMO").filter(
        Alerta.mensagem.like("Estearato%")).one()
    assert "0,3 kg" in alerta.mensagem


def test_rf19_descarte_exige_lote_bloqueado_e_assinatura(app):
    almoxarife = usuario("almoxarife")
    with pytest.raises(RegraDeNegocio, match="RF19"):          # lote aprovado não se descarta
        estoque.descartar_insumo(almoxarife, insumo("QV-9012"), SENHA_DEMO, "teste")
    producao.executar_ciclo()                                  # a rotina bloqueia o vencido
    vencido = insumo("AS-0391")
    with pytest.raises(RegraDeNegocio, match="RN07"):
        estoque.descartar_insumo(almoxarife, vencido, "errada", "Vencido.")
    estoque.descartar_insumo(almoxarife, vencido, SENHA_DEMO, "Vencido em estoque.")
    assert vencido.status == StatusEstoque.DESCARTADO and vencido.saldo == 0
