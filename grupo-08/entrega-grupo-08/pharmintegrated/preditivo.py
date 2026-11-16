"""Manufatura preditiva (demand-driven manufacturing) — seção 4.3 do artigo.

As dispensações reais registradas nos hospitais/farmácias alimentam o cálculo:

  previsão diária ....... suavização exponencial da demanda dos últimos N dias
  estoque de segurança .. ES = z · σ · √(lead time)            (z = 1,65 → 95% de nível de serviço)
  ponto de reposição .... PR = previsão · lead time + ES
  necessidade ........... previsão · horizonte + ES
  sugestão de produção .. necessidade − (estoque disponível + em quarentena + OPs abertas)
  cobertura ............. estoque disponível ÷ previsão diária   (em dias)

Com isso o sistema sugere novas OPs e reordena a prioridade da fila de produção:
quem tem menor cobertura é produzido primeiro, e itens com estoque excessivo
(baixa rotatividade) não recebem novas OPs — evitando vencimento e descarte (ODS 12).
"""
import math
import statistics
from datetime import date, timedelta

from . import db
from .servicos import AUTENTICO, _abrir_op, _auditar

PARAMETROS = {"dias_historico": 30, "lead_time": 7, "horizonte": 30, "z": 1.65, "alfa": 0.3}


def _suavizar(serie, alfa):
    nivel = serie[0] if serie else 0.0
    for x in serie[1:]:
        nivel = alfa * x + (1 - alfa) * nivel
    return nivel


def calcular(hoje=None, **params):
    p = dict(PARAMETROS, **params)
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=p["dias_historico"])
    resultado = []
    with db.conectar() as con:
        for med in con.execute("SELECT * FROM medicamento ORDER BY nome").fetchall():
            por_dia = {r["dia"]: r["qtd"] for r in con.execute(
                """SELECT substr(data,1,10) AS dia, COUNT(*) AS qtd FROM dispensacao
                   WHERE medicamento_id=? AND resultado=? AND substr(data,1,10) >= ? AND substr(data,1,10) < ?
                   GROUP BY dia""", (med["id"], AUTENTICO, inicio.isoformat(), hoje.isoformat()))}
            serie = [por_dia.get((inicio + timedelta(days=i)).isoformat(), 0) for i in range(p["dias_historico"])]

            media = statistics.mean(serie) if serie else 0
            desvio = statistics.pstdev(serie) if len(serie) > 1 else 0
            previsao = _suavizar(serie, p["alfa"])
            ultimos7 = statistics.mean(serie[-7:]) if serie else 0
            anteriores = statistics.mean(serie[:-7]) if len(serie) > 7 else ultimos7
            if anteriores == 0:
                tendencia = "Estável" if ultimos7 == 0 else "Alta"
            else:
                var = (ultimos7 - anteriores) / anteriores
                tendencia = "Alta" if var > 0.15 else "Queda" if var < -0.15 else "Estável"

            um = lambda sql, *a: con.execute(sql, a).fetchone()[0] or 0  # noqa: E731
            estoque = um("""SELECT COUNT(*) FROM caixa c JOIN lote l ON l.id=c.lote_id
                            WHERE l.medicamento_id=? AND l.status='Aprovado' AND l.validade>=?
                            AND c.status IN ('Aprovado/Estoque','Expedido')""", med["id"], hoje.isoformat())
            quarentena = um("""SELECT COUNT(*) FROM caixa c JOIN lote l ON l.id=c.lote_id
                               WHERE l.medicamento_id=? AND c.status='Em Quarentena'""", med["id"])
            em_producao = um("SELECT SUM(quantidade) FROM ordem_producao WHERE medicamento_id=? AND status='Aberta'",
                             med["id"])

            es = math.ceil(p["z"] * desvio * math.sqrt(p["lead_time"]))
            ponto_reposicao = math.ceil(previsao * p["lead_time"] + es)
            necessidade = math.ceil(previsao * p["horizonte"] + es)
            sugestao = max(0, necessidade - (estoque + quarentena + em_producao))
            cobertura = estoque / previsao if previsao > 0.05 else math.inf

            if previsao <= 0.05:
                situacao, prioridade = "Sem demanda", 5
            elif cobertura < p["lead_time"]:
                situacao, prioridade = "RUPTURA IMINENTE", 1
            elif estoque + quarentena + em_producao < ponto_reposicao:
                situacao, prioridade = "Repor", 2
            elif cobertura > 180:
                situacao, prioridade = "Excesso (baixa rotatividade)", 5
            elif sugestao > 0:
                situacao, prioridade = "Planejar produção", 3
            else:
                situacao, prioridade = "Adequado", 4

            resultado.append({
                "medicamento_id": med["id"], "medicamento": med["nome"],
                "media": media, "previsao": previsao, "tendencia": tendencia,
                "estoque": estoque, "quarentena": quarentena, "em_producao": em_producao,
                "estoque_seguranca": es, "ponto_reposicao": ponto_reposicao,
                "cobertura": cobertura, "sugestao": sugestao,
                "situacao": situacao, "prioridade": prioridade, "serie": serie,
            })
    resultado.sort(key=lambda r: (r["prioridade"], r["cobertura"]))
    return resultado


def gerar_ops_sugeridas(hoje=None):
    """Abre OPs para os itens com sugestão > 0 e reordena a prioridade das OPs abertas."""
    analise = calcular(hoje)
    criadas = []
    with db.conectar() as con:
        for r in analise:
            # Reordena a fila: OPs já abertas assumem a prioridade calculada pela demanda real
            con.execute("UPDATE ordem_producao SET prioridade=? WHERE medicamento_id=? AND status='Aberta'",
                        (r["prioridade"], r["medicamento_id"]))
            tem_formula = con.execute("SELECT 1 FROM formula WHERE medicamento_id=?", (r["medicamento_id"],)).fetchone()
            if r["sugestao"] > 0 and r["prioridade"] <= 3 and tem_formula:
                op_id = _abrir_op(con, r["medicamento_id"], r["sugestao"], "Preditivo", r["prioridade"])
                criadas.append((op_id, r["medicamento"], r["sugestao"], r["situacao"]))
        _auditar(con, "Planejamento preditivo", f"{len(criadas)} OP(s) sugerida(s) e fila de produção reordenada")
    return criadas
