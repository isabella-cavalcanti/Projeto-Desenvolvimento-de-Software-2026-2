"""Serviço de Qualidade: liberações, rastreabilidade e recall."""
from ..models import (AnaliseQualidade, ConsumoInsumo, Lote, LoteInsumo, Perfil,
                      Recall, Resultado, StatusEstoque, StatusLote, db)
from ..formato import numero
from . import auditoria, estoque
from .auditoria import SISTEMA, RegraDeNegocio


# ------------------------------------------------------------------ liberações
def avaliar_insumo(usuario, lote_insumo, resultado, senha, observacao):
    """RF14: só o CQ tira um insumo da quarentena (RN01, RN06, RN07)."""
    auditoria.exigir_perfil(usuario, Perfil.ANALISTA_CQ)
    auditoria.exigir_assinatura(usuario, senha, observacao)
    if lote_insumo.status != StatusEstoque.QUARENTENA:
        raise RegraDeNegocio(f"O lote {lote_insumo.codigo} não está em quarentena.")
    lote_insumo.status = (StatusEstoque.APROVADO if resultado == Resultado.APROVADO
                          else StatusEstoque.REPROVADO)
    db.session.add(AnaliseQualidade(lote_insumo=lote_insumo, resultado=resultado,
                                    observacao=observacao, analista=usuario.login))
    auditoria.registrar(usuario.login, "AVALIAR_INSUMO", lote_insumo.codigo,
                        f"{resultado.value}: {observacao}")


def avaliar_lote(usuario, lote, resultado, senha, observacao):
    """RF20 e RF21: o CQ aprova ou reprova; aprovado entra no estoque sozinho."""
    auditoria.exigir_perfil(usuario, Perfil.ANALISTA_CQ)  # RN13
    auditoria.exigir_assinatura(usuario, senha, observacao)
    if lote.status != StatusLote.EM_QUARENTENA:
        raise RegraDeNegocio(f"O lote {lote.codigo} não está em quarentena.")
    db.session.add(AnaliseQualidade(lote=lote, resultado=resultado,
                                    observacao=observacao, analista=usuario.login))
    auditoria.registrar(usuario.login, "AVALIAR_LOTE", lote.codigo,
                        f"{resultado.value}: {observacao}")
    if resultado == Resultado.APROVADO:
        lote.status = StatusLote.APROVADO
        estoque.entrada_producao(lote)
    else:
        lote.status = StatusLote.REPROVADO


# ------------------------------------------------------------- rastreabilidade
def rastrear_para_tras(lote):
    """RF22: do produto até os insumos, etapas, leituras e intervenções."""
    return {
        "lote": lote,
        "consumos": lote.consumos,
        "etapas": lote.etapas,
        "intervencoes": lote.intervencoes,
        "analises": lote.analises,
        "expedicoes": lote.expedicoes,
    }


def rastrear_para_frente(lote_insumo):
    """RF22: do insumo até os lotes produzidos e os clientes que os receberam."""
    lotes = [c.lote for c in ConsumoInsumo.query.filter_by(lote_insumo_id=lote_insumo.id)]
    lotes = sorted(set(lotes), key=lambda l: l.id)
    expedicoes = [e for lote in lotes for e in lote.expedicoes]
    clientes = sorted({e.cliente for e in expedicoes}, key=lambda c: c.nome)
    return {"lote_insumo": lote_insumo, "lotes": lotes,
            "expedicoes": expedicoes, "clientes": clientes}


# ----------------------------------------------------------------------- recall
def iniciar_recall(usuario, senha, motivo, lote_insumo=None, lote=None):
    """RF23: a pessoa decide o recall; o sistema acha e bloqueia tudo (RN11).

    A origem pode ser um lote de insumo (atinge todos os lotes que o
    consumiram) ou um único lote de produto.
    """
    auditoria.exigir_perfil(usuario, Perfil.GERENTE_QUALIDADE)
    auditoria.exigir_assinatura(usuario, senha, motivo)
    if (lote_insumo is None) == (lote is None):
        raise RegraDeNegocio("Informe a origem do recall: um lote de insumo ou de produto.")
    if lote_insumo is not None:
        rastro = rastrear_para_frente(lote_insumo)
        origem = lote_insumo.codigo
    else:
        rastro = {"lote_insumo": None, "lotes": [lote], "expedicoes": lote.expedicoes,
                  "clientes": sorted({e.cliente for e in lote.expedicoes},
                                     key=lambda c: c.nome)}
        origem = lote.codigo
    recall = Recall(motivo=motivo, origem_lote_insumo=lote_insumo, origem_lote=lote,
                    iniciado_por=usuario.login)
    auditoria.registrar(usuario.login, "INICIAR_RECALL", origem, motivo)
    if lote_insumo is not None and lote_insumo.status != StatusEstoque.DESCARTADO:
        lote_insumo.status = StatusEstoque.BLOQUEADO
        auditoria.registrar(SISTEMA, "BLOQUEAR_POR_RECALL", lote_insumo.codigo,
                            f"saldo bloqueado: {numero(lote_insumo.saldo)}")
    for afetado in rastro["lotes"]:
        if afetado.status != StatusLote.DESCARTADO:
            afetado.status = StatusLote.RECOLHIDO
            recall.lotes_afetados.append(afetado)
            auditoria.registrar(SISTEMA, "BLOQUEAR_POR_RECALL", afetado.codigo,
                                f"saldo bloqueado: {numero(afetado.saldo)}")
    db.session.add(recall)
    return recall, rastro


def lotes_em_quarentena():
    return Lote.query.filter_by(status=StatusLote.EM_QUARENTENA).all()


def insumos_em_quarentena():
    return LoteInsumo.query.filter_by(status=StatusEstoque.QUARENTENA).all()
