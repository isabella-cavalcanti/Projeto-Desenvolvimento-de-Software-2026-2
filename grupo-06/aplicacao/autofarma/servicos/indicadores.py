"""Indicadores de produção, qualidade e estoque (RF29). Somente leitura."""
from collections import Counter
from datetime import date, timedelta

from ..models import (Classificacao, Expedicao, Intervencao, Item, Leitura, Lote,
                      LoteInsumo, StatusEstoque, StatusIntervencao, StatusLote,
                      TipoIntervencao)
from . import estoque


def calcular(hoje=None):
    hoje = hoje or date.today()
    lotes = Lote.query.all()
    por_status = Counter(l.status for l in lotes)
    concluidos = [l for l in lotes if l.status in (StatusLote.APROVADO, StatusLote.EXPEDIDO,
                                                   StatusLote.REPROVADO, StatusLote.RECOLHIDO,
                                                   StatusLote.VENCIDO, StatusLote.DESCARTADO)]
    aprovados = [l for l in concluidos if any(a.resultado.name == "APROVADO" for a in l.analises)]

    desvios = Intervencao.query.filter_by(tipo=TipoIntervencao.DESVIO_PROCESSO).all()
    resolvidos = [d for d in desvios if d.status == StatusIntervencao.RESOLVIDA]
    tempos = [(d.resolvida_em - d.aberta_em).total_seconds() / 60 for d in resolvidos]
    por_etapa = Counter(d.leitura.etapa.etapa_padrao.nome for d in desvios if d.leitura)
    por_decisao = Counter(d.decisao.value for d in resolvidos)

    leituras = Counter(l.classificacao for l in Leitura.query.all())
    total_leituras = sum(leituras.values())

    insumos = []
    for item in Item.query.filter(Item.tipo != "produto_acabado").order_by(Item.codigo).all():
        saldo = estoque.saldo_aprovado(item, hoje)
        insumos.append({"item": item, "saldo": saldo, "abaixo": saldo < item.estoque_minimo})
    a_vencer = (LoteInsumo.query.filter(LoteInsumo.status == StatusEstoque.APROVADO,
                                        LoteInsumo.saldo > 0,
                                        LoteInsumo.validade <= hoje + timedelta(days=90))
                .order_by(LoteInsumo.validade).all())
    bloqueados = LoteInsumo.query.filter(
        LoteInsumo.saldo > 0,
        LoteInsumo.status.in_([StatusEstoque.VENCIDO, StatusEstoque.REPROVADO,
                               StatusEstoque.BLOQUEADO])).all()

    por_cliente = Counter()
    for e in Expedicao.query.all():
        por_cliente[e.cliente.nome] += e.quantidade

    return {
        "lotes_total": len(lotes),
        "lotes_por_status": [(s, por_status[s]) for s in StatusLote if por_status[s]],
        "taxa_aprovacao": (len(aprovados) / len(concluidos) * 100) if concluidos else None,
        "lotes_concluidos": len(concluidos),
        "desvios_total": len(desvios),
        "desvios_abertos": len(desvios) - len(resolvidos),
        "tempo_medio_resposta": (sum(tempos) / len(tempos)) if tempos else None,
        "desvios_por_etapa": por_etapa.most_common(),
        "desvios_por_decisao": por_decisao.most_common(),
        "leituras_total": total_leituras,
        "leituras": [(c, leituras[c], leituras[c] / total_leituras * 100 if total_leituras else 0)
                     for c in Classificacao],
        "insumos": insumos,
        "a_vencer": a_vencer,
        "bloqueados": bloqueados,
        "expedido_por_cliente": por_cliente.most_common(),
    }
